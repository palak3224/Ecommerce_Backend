from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from models.reel import Reel
from models.user_reel_like import UserReelLike
from services.recommendation_service import RecommendationService
from auth.models.models import User
from sqlalchemy import desc
from http import HTTPStatus


class RecommendationController:
    """Controller for recommendation feed operations."""
    
    @staticmethod
    def get_recommended_feed():
        """
        Get personalized recommendation feed for authenticated user.
        
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Get personalized feed
            reels, feed_info = RecommendationService.get_personalized_feed(
                current_user_id, page=page, per_page=per_page
            )
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Serialize reels with is_liked status
            reels_data = []
            for reel in reels:
                reel_data = reel.serialize(include_reasons=False, include_product=True, include_merchant=True, fields=fields)
                # Check if user has liked this reel (only if fields not specified or is_liked in fields)
                if not fields or 'is_liked' in fields:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel.reel_id)
                    reel_data['is_liked'] = is_liked
                reels_data.append(reel_data)
            
            # Calculate total (approximate - could be improved with better counting)
            # For now, we'll use a simple estimate
            total = len(reels) if page == 1 else page * per_page
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                },
                'feed_info': feed_info
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get recommended feed failed: {str(e)}")
            return jsonify({'error': f'Failed to get recommended feed: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_trending_feed():
        """
        Get trending reels feed (public, optional auth for is_liked).
        
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get optional user ID for is_liked status
            current_user_id = None
            try:
                current_user_id = get_jwt_identity()
            except Exception:
                pass  # User not authenticated - that's okay
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Time window (24h, 7d, 30d)
            time_window = request.args.get('time_window', '24h')
            time_window_hours_map = {
                '24h': 24,
                '7d': 168,  # 7 days
                '30d': 720  # 30 days
            }
            time_window_hours = time_window_hours_map.get(time_window, 24)
            
            # Get trending reels
            trending_reels = RecommendationService.get_trending_reels(
                limit=per_page * 2,  # Get more to account for pagination
                time_window_hours=time_window_hours
            )
            
            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            paginated_reels = trending_reels[start:end]
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Serialize reels with is_liked status if authenticated
            reels_data = []
            for reel in paginated_reels:
                reel_data = reel.serialize(include_reasons=False, include_product=True, include_merchant=True, fields=fields)
                # Check if user has liked this reel (if authenticated and fields allow)
                if not fields or 'is_liked' in fields:
                    if current_user_id:
                        is_liked = UserReelLike.user_has_liked(current_user_id, reel.reel_id)
                        reel_data['is_liked'] = is_liked
                    else:
                        reel_data['is_liked'] = False
                reels_data.append(reel_data)
            
            # Calculate pagination
            total = len(trending_reels)
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            
            from datetime import datetime, timezone
            feed_info = {
                'feed_type': 'trending',
                'time_window': time_window,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                },
                'feed_info': feed_info
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get trending feed failed: {str(e)}")
            return jsonify({'error': f'Failed to get trending feed: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_following_feed():
        """
        Get reels from followed merchants only (requires authentication).
        
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Get followed merchant reels
            followed_reels = RecommendationService.get_followed_merchant_reels(
                current_user_id, limit=per_page * 2  # Get more for pagination
            )
            
            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            paginated_reels = followed_reels[start:end]
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Serialize reels with is_liked status
            reels_data = []
            for reel in paginated_reels:
                reel_data = reel.serialize(include_reasons=False, include_product=True, include_merchant=True, fields=fields)
                # Check if user has liked this reel (only if fields not specified or is_liked in fields)
                if not fields or 'is_liked' in fields:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel.reel_id)
                    reel_data['is_liked'] = is_liked
                reels_data.append(reel_data)
            
            # Calculate pagination
            total = len(followed_reels)
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            
            # Get followed merchants count
            from models.user_merchant_follow import UserMerchantFollow
            followed_merchants_count = len(UserMerchantFollow.get_followed_merchants(current_user_id))
            
            feed_info = {
                'feed_type': 'following',
                'followed_merchants_count': followed_merchants_count,
                'generated_at': None  # Could add timestamp if needed
            }
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                },
                'feed_info': feed_info
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get following feed failed: {str(e)}")
            return jsonify({'error': f'Failed to get following feed: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

