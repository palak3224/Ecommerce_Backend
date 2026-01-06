from flask import Blueprint, request, jsonify
from controllers.recommendation_controller import RecommendationController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin
from http import HTTPStatus

recommendation_bp = Blueprint('recommendation', __name__)


@recommendation_bp.route('/api/reels/feed/recommended', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_recommended_feed():
    """
    Get personalized recommendation feed (requires authentication)
    ---
    tags:
      - Recommendations
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
        description: Personalized recommendation feed
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return RecommendationController.get_recommended_feed()


@recommendation_bp.route('/api/reels/feed/trending', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_trending_feed():
    """
    Get trending reels feed (public, optional authentication for is_liked)
    ---
    tags:
      - Recommendations
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
        name: time_window
        type: string
        required: false
        default: 24h
        enum: [24h, 7d, 30d]
        description: Time window for trending calculation
    responses:
      200:
        description: Trending reels feed
      500:
        description: Server error
    """
    return RecommendationController.get_trending_feed()


@recommendation_bp.route('/api/reels/feed/following', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_following_feed():
    """
    Get reels from followed merchants (requires authentication)
    ---
    tags:
      - Recommendations
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
        description: Reels from followed merchants
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return RecommendationController.get_following_feed()

