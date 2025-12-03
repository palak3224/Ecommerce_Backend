from flask import Blueprint, request, jsonify
from controllers.follow_controller import FollowController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin
from http import HTTPStatus

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

