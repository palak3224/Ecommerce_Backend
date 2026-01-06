# controllers/notification_controller.py
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from models.merchant_notification import MerchantNotification
from auth.models.models import User, MerchantProfile
from services.notification_cleanup_service import NotificationCleanupService
from http import HTTPStatus


class NotificationController:
    """Controller for merchant notifications."""
    
    @staticmethod
    def get_notifications():
        """
        Get paginated notifications for the current merchant.
        
        Returns:
            JSON response with notifications and pagination
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
            
            # Get and validate query parameters
            try:
                page = request.args.get('page', 1, type=int)
                per_page = request.args.get('per_page', 20, type=int)
            except (ValueError, TypeError):
                page = 1
                per_page = 20
            
            # Validate pagination parameters
            page = max(1, page) if page else 1
            per_page = max(1, min(100, per_page)) if per_page else 20
            
            unread_only = request.args.get('unread_only', 'false').lower() == 'true'
            
            # Get notifications
            notifications, total, total_pages = MerchantNotification.get_merchant_notifications(
                merchant.id,
                page=page,
                per_page=per_page,
                unread_only=unread_only
            )
            
            # Get unread count
            unread_count = MerchantNotification.get_unread_count(merchant.id)
            
            # Serialize notifications
            notifications_data = [n.serialize() for n in notifications]
            
            return jsonify({
                'status': 'success',
                'unread_count': unread_count,
                'data': notifications_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': total_pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get notifications failed: {str(e)}")
            return jsonify({'error': f'Failed to get notifications: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_unread_count():
        """
        Get unread notification count for the current merchant.
        
        Returns:
            JSON response with unread count
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
            
            # Get unread count
            unread_count = MerchantNotification.get_unread_count(merchant.id)
            
            return jsonify({
                'status': 'success',
                'unread_count': unread_count
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get unread count failed: {str(e)}")
            return jsonify({'error': f'Failed to get unread count: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def mark_as_read(notification_id):
        """
        Mark a notification as read.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            JSON response with success/error
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
            
            # Get notification
            notification = MerchantNotification.query.filter_by(
                id=notification_id,
                merchant_id=merchant.id
            ).first()
            
            if not notification:
                return jsonify({'error': 'Notification not found'}), HTTPStatus.NOT_FOUND
            
            # Mark as read
            notification.mark_as_read()
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Notification marked as read'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Mark notification as read failed: {str(e)}")
            return jsonify({'error': f'Failed to mark notification as read: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def mark_all_as_read():
        """
        Mark all notifications as read for the current merchant.
        
        Returns:
            JSON response with success/error
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
            
            # Mark all as read
            count = MerchantNotification.mark_all_as_read(merchant.id)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'{count} notifications marked as read'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Mark all notifications as read failed: {str(e)}")
            return jsonify({'error': f'Failed to mark all notifications as read: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def delete_notification(notification_id):
        """
        Delete a notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            JSON response with success/error
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
            
            # Get notification
            notification = MerchantNotification.query.filter_by(
                id=notification_id,
                merchant_id=merchant.id
            ).first()
            
            if not notification:
                return jsonify({'error': 'Notification not found'}), HTTPStatus.NOT_FOUND
            
            # Delete notification
            db.session.delete(notification)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Notification deleted successfully'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Delete notification failed: {str(e)}")
            return jsonify({'error': f'Failed to delete notification: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def bulk_delete_notifications():
        """
        Delete multiple notifications for the current merchant.
        
        Returns:
            JSON response with success/error
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
            
            # Get notification IDs from request body
            data = request.get_json()
            if not data or 'notification_ids' not in data:
                return jsonify({'error': 'notification_ids array is required'}), HTTPStatus.BAD_REQUEST
            
            notification_ids = data.get('notification_ids', [])
            if not isinstance(notification_ids, list) or len(notification_ids) == 0:
                return jsonify({'error': 'notification_ids must be a non-empty array'}), HTTPStatus.BAD_REQUEST
            
            # Validate all IDs are integers
            try:
                notification_ids = [int(id) for id in notification_ids]
            except (ValueError, TypeError):
                return jsonify({'error': 'All notification_ids must be valid integers'}), HTTPStatus.BAD_REQUEST
            
            # Bulk delete notifications
            count = MerchantNotification.bulk_delete(merchant.id, notification_ids)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'{count} notification(s) deleted successfully'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Bulk delete notifications failed: {str(e)}")
            return jsonify({'error': f'Failed to delete notifications: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def cleanup_old_notifications():
        """
        Cleanup old read notifications (admin/maintenance endpoint).
        Only deletes read notifications older than specified days.
        
        Returns:
            JSON response with success/error
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
            
            # Get parameters
            try:
                days_old = request.args.get('days_old', 90, type=int)
                batch_size = request.args.get('batch_size', 100, type=int)
                max_batches = request.args.get('max_batches', 10, type=int)
            except (ValueError, TypeError):
                days_old = 90
                batch_size = 100
                max_batches = 10
            
            days_old = max(30, min(365, days_old))  # Between 30 and 365 days
            batch_size = max(10, min(500, batch_size))  # Between 10 and 500
            max_batches = max(1, min(50, max_batches))  # Between 1 and 50
            
            # Use incremental cleanup service for better performance
            result = NotificationCleanupService.cleanup_incremental(
                days_old=days_old,
                batch_size=batch_size,
                max_batches=max_batches
            )
            
            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': f'{result["total_deleted"]} old notification(s) cleaned up successfully',
                    'data': {
                        'total_deleted': result['total_deleted'],
                        'batches_processed': result['batches_processed'],
                        'cutoff_date': result['cutoff_date']
                    }
                }), HTTPStatus.OK
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Cleanup partially completed: {result.get("error", "Unknown error")}',
                    'data': {
                        'total_deleted': result.get('total_deleted', 0),
                        'batches_processed': result.get('batches_processed', 0)
                    }
                }), HTTPStatus.PARTIAL_CONTENT
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Cleanup old notifications failed: {str(e)}")
            return jsonify({'error': f'Failed to cleanup notifications: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

