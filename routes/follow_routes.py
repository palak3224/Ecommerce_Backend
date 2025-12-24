from flask import Blueprint, request, jsonify
from controllers.follow_controller import FollowController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin
from http import HTTPStatus
from auth.utils import merchant_role_required

follow_bp = Blueprint('follow', __name__)


@follow_bp.route('/api/merchants/<int:merchant_id>/follow', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def follow_merchant(merchant_id):
    """
    Follow a merchant
    ---
    tags:
      - Follow
    security:
      - Bearer: []
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID to follow
    responses:
      201:
        description: Merchant followed successfully
      400:
        description: Already following or invalid input
      401:
        description: Unauthorized (authentication required)
      404:
        description: Merchant not found
      500:
        description: Server error
    """
    return FollowController.follow_merchant(merchant_id)


@follow_bp.route('/api/merchants/<int:merchant_id>/unfollow', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def unfollow_merchant(merchant_id):
    """
    Unfollow a merchant
    ---
    tags:
      - Follow
    security:
      - Bearer: []
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID to unfollow
    responses:
      200:
        description: Merchant unfollowed successfully
      400:
        description: Not following or invalid input
      401:
        description: Unauthorized (authentication required)
      404:
        description: Merchant not found
      500:
        description: Server error
    """
    return FollowController.unfollow_merchant(merchant_id)


@follow_bp.route('/api/merchants/following', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_following():
    """
    Get list of followed merchants
    ---
    tags:
      - Follow
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
    responses:
      200:
        description: List of followed merchants
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return FollowController.get_followed_merchants()


@follow_bp.route('/api/merchants/followers', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
@merchant_role_required
def get_merchant_followers():
    """
    Get list of followers for the current merchant
    ---
    tags:
      - Follow
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
    responses:
      200:
        description: List of followers retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
            total_followers:
              type: integer
            data:
              type: array
              items:
                type: object
                properties:
                  user_id:
                    type: integer
                  first_name:
                    type: string
                  last_name:
                    type: string
                  profile_img:
                    type: string
                  followed_at:
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
    return FollowController.get_merchant_followers()


@follow_bp.route('/api/merchants/<int:merchant_id>/followers/count', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_merchant_follower_count(merchant_id):
    """
    Get follower count for a merchant (public endpoint).
    ---
    tags:
      - Follow
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID
    responses:
      200:
        description: Follower count retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
            merchant_id:
              type: integer
            follower_count:
              type: integer
      404:
        description: Merchant not found
      500:
        description: Server error
    """
    return FollowController.get_merchant_follower_count(merchant_id)
