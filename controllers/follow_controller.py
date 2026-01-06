from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from common.cache import get_redis_client
from models.user_merchant_follow import UserMerchantFollow
from models.merchant_notification import MerchantNotification
from auth.models.models import User, MerchantProfile
from sqlalchemy import desc
from datetime import datetime, timezone
from http import HTTPStatus


class FollowController:
    """Controller for merchant follow/unfollow operations."""
    
    @staticmethod
    def follow_merchant(merchant_id):
        """
        Follow a merchant.
        
        Args:
            merchant_id: Merchant ID to follow
            
        Returns:
            JSON response with success/error
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Check if merchant exists
            merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
            
            # Prevent self-follow
            if merchant.user_id == current_user_id:
                return jsonify({
                    'error': 'You cannot follow yourself',
                    'data': {
                        'merchant_id': merchant_id,
                        'business_name': merchant.business_name
                    }
                }), HTTPStatus.BAD_REQUEST
            
            # Check if already following
            if UserMerchantFollow.is_following(current_user_id, merchant_id):
                return jsonify({
                    'error': 'You are already following this merchant',
                    'data': {
                        'merchant_id': merchant_id,
                        'business_name': merchant.business_name
                    }
                }), HTTPStatus.BAD_REQUEST
            
            # Create follow record
            follow = UserMerchantFollow.follow(current_user_id, merchant_id)
            if follow:
                # Create notification for merchant
                # Use savepoint to ensure notification failure doesn't affect follow operation
                savepoint = db.session.begin_nested()
                try:
                    user_name = f"{user.first_name} {user.last_name}".strip()
                    MerchantNotification.create_follow_notification(
                        merchant_id=merchant_id,
                        follower_user_id=current_user_id,
                        follower_name=user_name
                    )
                    savepoint.commit()
                except Exception as e:
                    savepoint.rollback()
                    current_app.logger.warning(f"Failed to create notification for merchant follow: {str(e)}")
                    # Don't fail the follow operation if notification creation fails
                
                # Commit all changes together (follow + notification if successful)
                db.session.commit()
                
                # Invalidate recommendation cache
                try:
                    redis_client = get_redis_client(current_app)
                    if redis_client:
                        # Invalidate user's recommendation and following feeds
                        pattern = f"feed:recommended:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                        pattern = f"feed:following:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                except Exception:
                    pass  # Silently fail if cache invalidation fails
                
                return jsonify({
                    'status': 'success',
                    'message': 'Merchant followed successfully',
                    'data': {
                        'merchant_id': merchant_id,
                        'business_name': merchant.business_name,
                        'followed_at': follow.followed_at.isoformat() if follow.followed_at else None
                    }
                }), HTTPStatus.CREATED
            else:
                return jsonify({'error': 'Failed to follow merchant'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Follow merchant failed: {str(e)}")
            return jsonify({'error': f'Failed to follow merchant: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def unfollow_merchant(merchant_id):
        """
        Unfollow a merchant.
        
        Args:
            merchant_id: Merchant ID to unfollow
            
        Returns:
            JSON response with success/error
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Check if merchant exists
            merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
            
            # Check if following
            if not UserMerchantFollow.is_following(current_user_id, merchant_id):
                return jsonify({
                    'error': 'You are not following this merchant',
                    'data': {
                        'merchant_id': merchant_id,
                        'business_name': merchant.business_name
                    }
                }), HTTPStatus.BAD_REQUEST
            
            # Remove follow record
            removed = UserMerchantFollow.unfollow(current_user_id, merchant_id)
            if removed:
                db.session.commit()
                
                # Invalidate recommendation cache
                try:
                    redis_client = get_redis_client(current_app)
                    if redis_client:
                        # Invalidate user's recommendation and following feeds
                        pattern = f"feed:recommended:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                        pattern = f"feed:following:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                except Exception:
                    pass  # Silently fail if cache invalidation fails
                
                return jsonify({
                    'status': 'success',
                    'message': 'Merchant unfollowed successfully'
                }), HTTPStatus.OK
            else:
                return jsonify({'error': 'Failed to unfollow merchant'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unfollow merchant failed: {str(e)}")
            return jsonify({'error': f'Failed to unfollow merchant: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_followed_merchants():
        """
        Get list of merchants that the current user follows.
        
        Returns:
            JSON response with paginated list of followed merchants
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get all follows for user
            follows = UserMerchantFollow.get_followed_merchants(current_user_id)
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Calculate pagination
            total = len(follows)
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            start = (page - 1) * per_page
            end = start + per_page
            paginated_follows = follows[start:end]
            
            # Serialize merchant data
            merchants_data = []
            for follow in paginated_follows:
                merchant = follow.merchant
                if merchant:
                    merchants_data.append({
                        'merchant_id': merchant.id,
                        'business_name': merchant.business_name,
                        'followed_at': follow.followed_at.isoformat() if follow.followed_at else None
                    })
            
            return jsonify({
                'status': 'success',
                'data': merchants_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get followed merchants failed: {str(e)}")
            return jsonify({'error': f'Failed to get followed merchants: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_merchant_followers():
        """
        Get list of followers for the current merchant.
        
        Returns:
            JSON response with paginated list of followers and total count
        """
        try:
            # Get current user (merchant)
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get merchant profile
            merchant = MerchantProfile.get_by_user_id(current_user_id)
            if not merchant:
                return jsonify({'error': 'Merchant profile not found'}), HTTPStatus.NOT_FOUND
            
            # Get all followers for this merchant
            follows = UserMerchantFollow.get_merchant_followers(merchant.id)
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Calculate pagination
            total = len(follows)
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            start = (page - 1) * per_page
            end = start + per_page
            paginated_follows = follows[start:end]
            
            # Serialize follower data with basic user details
            followers_data = []
            for follow in paginated_follows:
                follower_user = follow.user
                if follower_user:
                    followers_data.append({
                        'user_id': follower_user.id,
                        'first_name': follower_user.first_name,
                        'last_name': follower_user.last_name,
                        'profile_img': follower_user.profile_img,
                        'followed_at': follow.followed_at.isoformat() if follow.followed_at else None
                    })
            
            return jsonify({
                'status': 'success',
                'total_followers': total,
                'data': followers_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get merchant followers failed: {str(e)}")
            return jsonify({'error': f'Failed to get merchant followers: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_merchant_follower_count(merchant_id):
        """
        Get follower count for a merchant (public endpoint).
        
        Args:
            merchant_id: Merchant ID to get follower count for
            
        Returns:
            JSON response with follower count
        """
        try:
            # Check if merchant exists
            merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
            
            # Get follower count
            follower_count = UserMerchantFollow.query.filter_by(merchant_id=merchant_id).count()
            
            return jsonify({
                'status': 'success',
                'merchant_id': merchant_id,
                'follower_count': follower_count
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get merchant follower count failed: {str(e)}")
            return jsonify({'error': f'Failed to get follower count: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

