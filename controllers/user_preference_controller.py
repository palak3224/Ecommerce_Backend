from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from common.cache import get_redis_client
from models.user_blocked_merchant import UserBlockedMerchant
from models.user_hidden_category import UserHiddenCategory
from models.user_merchant_follow import UserMerchantFollow
from models.category import Category
from auth.models.models import User, MerchantProfile
from http import HTTPStatus


class UserPreferenceController:
    """Controller for per-user reel "not interested" preferences.

    Lets a user hide a vendor's reels or a category's reels from their own
    reel feeds. These are user-scoped signals only and do not affect other
    users, product browsing, search or ordering.
    """

    @staticmethod
    def _invalidate_feed_cache(user_id):
        """Invalidate the user's recommended/following feed caches (best effort)."""
        try:
            redis_client = get_redis_client(current_app)
            if redis_client:
                for prefix in (f"feed:recommended:{user_id}:*", f"feed:following:{user_id}:*"):
                    keys = redis_client.keys(prefix)
                    if keys:
                        redis_client.delete(*keys)
        except Exception:
            pass  # Silently fail if cache invalidation fails

    # ------------------------------------------------------------------ #
    # Vendor ("not interested in this vendor")
    # ------------------------------------------------------------------ #
    @staticmethod
    def block_merchant(merchant_id):
        """Mark a vendor as 'not interested' for the current user."""
        try:
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND

            merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND

            if UserBlockedMerchant.is_blocked(current_user_id, merchant_id):
                return jsonify({
                    'status': 'success',
                    'message': 'Vendor already marked as not interested',
                    'data': {'merchant_id': merchant_id}
                }), HTTPStatus.OK

            UserBlockedMerchant.block(current_user_id, merchant_id)

            # Blocking and following are contradictory states: auto-unfollow.
            unfollowed = UserMerchantFollow.unfollow(current_user_id, merchant_id)

            db.session.commit()
            UserPreferenceController._invalidate_feed_cache(current_user_id)

            return jsonify({
                'status': 'success',
                'message': 'Vendor marked as not interested. Their reels are hidden from your feeds.',
                'data': {
                    'merchant_id': merchant_id,
                    'business_name': merchant.business_name,
                    'auto_unfollowed': bool(unfollowed)
                }
            }), HTTPStatus.CREATED

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Block merchant failed: {str(e)}")
            return jsonify({'error': f'Failed to mark vendor as not interested: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def unblock_merchant(merchant_id):
        """Undo 'not interested' for a vendor."""
        try:
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND

            removed = UserBlockedMerchant.unblock(current_user_id, merchant_id)
            if not removed:
                return jsonify({
                    'error': 'This vendor is not in your not-interested list',
                    'data': {'merchant_id': merchant_id}
                }), HTTPStatus.BAD_REQUEST

            db.session.commit()
            UserPreferenceController._invalidate_feed_cache(current_user_id)

            return jsonify({
                'status': 'success',
                'message': 'Vendor restored to your feeds',
                'data': {'merchant_id': merchant_id}
            }), HTTPStatus.OK

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unblock merchant failed: {str(e)}")
            return jsonify({'error': f'Failed to restore vendor: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------ #
    # Category ("not interested in this category")
    # ------------------------------------------------------------------ #
    @staticmethod
    def hide_category(category_id):
        """Mark a category as 'not interested' for the current user."""
        try:
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND

            category = Category.query.filter_by(category_id=category_id).first()
            if not category:
                return jsonify({'error': 'Category not found'}), HTTPStatus.NOT_FOUND

            if UserHiddenCategory.is_hidden(current_user_id, category_id):
                return jsonify({
                    'status': 'success',
                    'message': 'Category already marked as not interested',
                    'data': {'category_id': category_id}
                }), HTTPStatus.OK

            UserHiddenCategory.hide(current_user_id, category_id)
            db.session.commit()
            UserPreferenceController._invalidate_feed_cache(current_user_id)

            return jsonify({
                'status': 'success',
                'message': 'Category marked as not interested. Its reels are hidden from your feeds.',
                'data': {
                    'category_id': category_id,
                    'category_name': category.name
                }
            }), HTTPStatus.CREATED

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Hide category failed: {str(e)}")
            return jsonify({'error': f'Failed to mark category as not interested: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def unhide_category(category_id):
        """Undo 'not interested' for a category."""
        try:
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND

            removed = UserHiddenCategory.unhide(current_user_id, category_id)
            if not removed:
                return jsonify({
                    'error': 'This category is not in your not-interested list',
                    'data': {'category_id': category_id}
                }), HTTPStatus.BAD_REQUEST

            db.session.commit()
            UserPreferenceController._invalidate_feed_cache(current_user_id)

            return jsonify({
                'status': 'success',
                'message': 'Category restored to your feeds',
                'data': {'category_id': category_id}
            }), HTTPStatus.OK

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unhide category failed: {str(e)}")
            return jsonify({'error': f'Failed to restore category: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------ #
    # Listing (settings screen)
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_not_interested():
        """List the current user's blocked vendors and hidden categories."""
        try:
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND

            blocked = UserBlockedMerchant.get_blocked(current_user_id)
            blocked_data = []
            for b in blocked:
                merchant = b.merchant
                blocked_data.append({
                    'merchant_id': b.merchant_id,
                    'business_name': merchant.business_name if merchant else None,
                    'profile_img': merchant.profile_img if merchant else None,
                    'created_at': b.created_at.isoformat() if b.created_at else None
                })

            hidden = UserHiddenCategory.get_hidden(current_user_id)
            hidden_data = []
            for h in hidden:
                category = h.category
                hidden_data.append({
                    'category_id': h.category_id,
                    'category_name': category.name if category else None,
                    'created_at': h.created_at.isoformat() if h.created_at else None
                })

            return jsonify({
                'status': 'success',
                'data': {
                    'blocked_merchants': blocked_data,
                    'hidden_categories': hidden_data
                }
            }), HTTPStatus.OK

        except Exception as e:
            current_app.logger.error(f"Get not-interested list failed: {str(e)}")
            return jsonify({'error': f'Failed to get not-interested list: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
