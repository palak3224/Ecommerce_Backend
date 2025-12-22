# routes/notification_routes.py
from flask import Blueprint, request, jsonify
from controllers.notification_controller import NotificationController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin
from http import HTTPStatus
from auth.utils import merchant_role_required

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/api/merchants/notifications', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def get_notifications():
    """
    Get list of notifications for the current merchant
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - in: query
        name: page
        type: integer
        required: false
        default: 1
        description: Page number
      - in: query
        name: per_page
        type: integer
        required: false
        default: 20
        description: Items per page (max 100)
      - in: query
        name: unread_only
        type: boolean
        required: false
        default: false
        description: If true, only return unread notifications
    responses:
      200:
        description: List of notifications retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
            unread_count:
              type: integer
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  type:
                    type: string
                    enum: [reel_liked, merchant_followed]
                  title:
                    type: string
                  message:
                    type: string
                  related_entity_type:
                    type: string
                  related_entity_id:
                    type: integer
                  like_count:
                    type: integer
                    nullable: true
                  last_liked_by_user_name:
                    type: string
                    nullable: true
                  is_read:
                    type: boolean
                  read_at:
                    type: string
                    format: date-time
                    nullable: true
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
            pagination:
              type: object
              properties:
                page:
                  type: integer
                per_page:
                  type: integer
                total:
                  type: integer
                pages:
                  type: integer
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      404:
        description: Merchant profile not found
      500:
        description: Server error
    """
    return NotificationController.get_notifications()


@notification_bp.route('/api/merchants/notifications/unread-count', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def get_unread_count():
    """
    Get unread notification count for the current merchant
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    responses:
      200:
        description: Unread count retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
            unread_count:
              type: integer
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      404:
        description: Merchant profile not found
      500:
        description: Server error
    """
    return NotificationController.get_unread_count()


@notification_bp.route('/api/merchants/notifications/<int:notification_id>/read', methods=['PUT', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def mark_notification_as_read(notification_id):
    """
    Mark a notification as read
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - in: path
        name: notification_id
        type: integer
        required: true
        description: Notification ID to mark as read
    responses:
      200:
        description: Notification marked as read successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      404:
        description: Notification not found
      500:
        description: Server error
    """
    return NotificationController.mark_as_read(notification_id)


@notification_bp.route('/api/merchants/notifications/mark-all-read', methods=['PUT', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def mark_all_notifications_as_read():
    """
    Mark all notifications as read for the current merchant
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    responses:
      200:
        description: All notifications marked as read successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      404:
        description: Merchant profile not found
      500:
        description: Server error
    """
    return NotificationController.mark_all_as_read()


@notification_bp.route('/api/merchants/notifications/<int:notification_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def delete_notification(notification_id):
    """
    Delete a notification
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - in: path
        name: notification_id
        type: integer
        required: true
        description: Notification ID to delete
    responses:
      200:
        description: Notification deleted successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      404:
        description: Notification not found
      500:
        description: Server error
    """
    return NotificationController.delete_notification(notification_id)


@notification_bp.route('/api/merchants/notifications/bulk-delete', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def bulk_delete_notifications():
    """
    Delete multiple notifications
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - notification_ids
          properties:
            notification_ids:
              type: array
              items:
                type: integer
              description: Array of notification IDs to delete
    responses:
      200:
        description: Notifications deleted successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
      400:
        description: Invalid request (missing or invalid notification_ids)
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      500:
        description: Server error
    """
    return NotificationController.bulk_delete_notifications()


@notification_bp.route('/api/merchants/notifications/cleanup', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def cleanup_old_notifications():
    """
    Cleanup old read notifications
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - in: query
        name: days_old
        type: integer
        required: false
        default: 90
        description: Delete read notifications older than this many days (30-365)
    responses:
      200:
        description: Old notifications cleaned up successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
      401:
        description: Unauthorized (authentication required)
      403:
        description: Merchant access required
      500:
        description: Server error
    """
    return NotificationController.cleanup_old_notifications()

