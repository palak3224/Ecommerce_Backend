from flask import Blueprint, request, jsonify
from controllers.reels_controller import ReelsController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin
from common.decorators import rate_limit
from http import HTTPStatus

reels_bp = Blueprint('reels', __name__)


@reels_bp.route('/api/reels', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
@rate_limit(limit=10, per=3600, key_prefix='reel_upload')  # 10 uploads per hour
def upload_reel():
    """
    Upload a new reel
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: video
        type: file
        required: true
        description: Video file (MP4, MOV, AVI, MKV, max 100MB, max 60s)
      - in: formData
        name: product_id
        type: integer
        required: true
        description: Product ID (must be approved product with stock > 0)
      - in: formData
        name: description
        type: string
        required: true
        description: Reel description (max 5000 characters)
    responses:
      201:
        description: Reel uploaded successfully
      400:
        description: Invalid input
      403:
        description: Forbidden (not a merchant)
      500:
        description: Server error
    """
    return ReelsController.upload_reel()


@reels_bp.route('/api/reels/<int:reel_id>', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_reel(reel_id):
    """
    Get a single reel by ID (automatically tracks view)
    ---
    tags:
      - Reels
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
      - in: query
        name: track_view
        type: boolean
        required: false
        default: true
        description: Whether to increment view count
      - in: query
        name: view_duration
        type: integer
        required: false
        description: View duration in seconds (for tracking watch time, optional)
    responses:
      200:
        description: Reel data
      404:
        description: Reel not found
    """
    track_view = request.args.get('track_view', 'true').lower() == 'true'
    view_duration = request.args.get('view_duration', type=int)
    return ReelsController.get_reel(reel_id, track_view=track_view, view_duration=view_duration)


@reels_bp.route('/api/reels/merchant/my', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_my_reels():
    """
    Get current merchant's reels
    ---
    tags:
      - Reels
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
        name: include_all
        type: boolean
        required: false
        default: false
        description: Include all reels including non-visible ones
      - in: query
        name: category_id
        type: integer
        required: false
        description: Filter by category ID
      - in: query
        name: start_date
        type: string
        required: false
        description: Start date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
      - in: query
        name: end_date
        type: string
        required: false
        description: End date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
      - in: query
        name: sort_by
        type: string
        required: false
        default: newest
        enum: [newest, likes, views, shares]
        description: Sort field
    responses:
      200:
        description: List of merchant's reels
      403:
        description: Forbidden (not a merchant)
    """
    include_all = request.args.get('include_all', 'false').lower() == 'true'
    return ReelsController.get_merchant_reels(merchant_id=None, include_all=include_all)


@reels_bp.route('/api/reels/merchant/<int:merchant_id>', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_merchant_public_reels(merchant_id):
    """
    Get public reels for a merchant
    ---
    tags:
      - Reels
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID
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
        description: List of merchant's public reels
      404:
        description: Merchant not found
    """
    return ReelsController.get_merchant_reels(merchant_id=merchant_id, include_all=False)


@reels_bp.route('/api/reels/public', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_public_reels():
    """
    Get public visible reels (for feed)
    ---
    tags:
      - Reels
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
        description: List of public visible reels
    """
    return ReelsController.get_public_reels()


@reels_bp.route('/api/reels/<int:reel_id>', methods=['PUT', 'OPTIONS'])
@cross_origin()
@jwt_required()
def update_reel(reel_id):
    """
    Update reel description
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            description:
              type: string
              required: true
              description: New description (max 5000 characters)
    responses:
      200:
        description: Reel updated successfully
      400:
        description: Invalid input
      403:
        description: Forbidden (not owner)
      404:
        description: Reel not found
    """
    return ReelsController.update_reel(reel_id)


@reels_bp.route('/api/reels/<int:reel_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@jwt_required()
def delete_reel(reel_id):
    """
    Delete a reel
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
    responses:
      200:
        description: Reel deleted successfully
      403:
        description: Forbidden (not owner)
      404:
        description: Reel not found
    """
    return ReelsController.delete_reel(reel_id)


@reels_bp.route('/api/reels/products/available', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_available_products():
    """
    Get merchant's approved products with stock > 0 that can be used for reel upload
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    responses:
      200:
        description: List of available products
      403:
        description: Forbidden (not a merchant)
    """
    return ReelsController.get_available_products()


@reels_bp.route('/api/reels/<int:reel_id>/like', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def like_reel(reel_id):
    """
    Like a reel (increment like count, requires authentication)
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
    responses:
      200:
        description: Reel liked successfully
      400:
        description: Already liked or reel not available
      401:
        description: Unauthorized (authentication required)
      404:
        description: Reel not found
    """
    return ReelsController.like_reel(reel_id)


@reels_bp.route('/api/reels/<int:reel_id>/unlike', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def unlike_reel(reel_id):
    """
    Unlike a reel (decrement like count, requires authentication)
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
    responses:
      200:
        description: Reel unliked successfully
      400:
        description: Not liked yet
      401:
        description: Unauthorized (authentication required)
      404:
        description: Reel not found
    """
    return ReelsController.unlike_reel(reel_id)


@reels_bp.route('/api/reels/<int:reel_id>/share', methods=['POST', 'OPTIONS'])
@cross_origin()
def share_reel(reel_id):
    """
    Share a reel (increment share count)
    ---
    tags:
      - Reels
    parameters:
      - in: path
        name: reel_id
        type: integer
        required: true
        description: Reel ID
    responses:
      200:
        description: Reel share tracked successfully
      404:
        description: Reel not found
    """
    return ReelsController.share_reel(reel_id)


@reels_bp.route('/api/reels/user/stats', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_user_reel_stats():
    """
    Get user's reel interaction statistics
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    responses:
      200:
        description: User reel statistics
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return ReelsController.get_user_reel_stats()


@reels_bp.route('/api/reels/merchant/my/analytics', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_merchant_reel_analytics():
    """
    Get merchant's reel analytics with aggregated stats and per-reel statistics
    ---
    tags:
      - Reels
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
        name: start_date
        type: string
        required: false
        description: Start date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
      - in: query
        name: end_date
        type: string
        required: false
        description: End date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
      - in: query
        name: sort_by
        type: string
        required: false
        default: created_at
        enum: [created_at, views, likes, shares, engagement]
        description: Sort field for reel stats
    responses:
      200:
        description: Merchant reel analytics
      401:
        description: Unauthorized (authentication required)
      403:
        description: Forbidden (not a merchant)
      500:
        description: Server error
    """
    return ReelsController.get_merchant_reel_analytics()


@reels_bp.route('/api/reels/user/shared', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_user_shared_reels():
    """
    Get reels that the current user has shared
    ---
    tags:
      - Reels
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
        description: List of shared reels
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return ReelsController.get_user_shared_reels()


@reels_bp.route('/api/reels/search', methods=['GET', 'OPTIONS'])
@cross_origin()
def search_reels():
    """
    Search reels by description, product name, or merchant name
    ---
    tags:
      - Reels
    parameters:
      - in: query
        name: q
        type: string
        required: true
        description: Search query (searches in reel description)
      - in: query
        name: category_id
        type: integer
        required: false
        description: Filter by category ID
      - in: query
        name: merchant_id
        type: integer
        required: false
        description: Filter by merchant ID
      - in: query
        name: start_date
        type: string
        required: false
        description: Start date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
      - in: query
        name: end_date
        type: string
        required: false
        description: End date filter (ISO format, e.g., 2024-01-01T00:00:00Z)
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
        description: Search results
      400:
        description: Invalid search query or filters
      500:
        description: Server error
    """
    return ReelsController.search_reels()


@reels_bp.route('/api/reels/batch/delete', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
@rate_limit(limit=5, per=3600, key_prefix='reel_batch_delete')  # 5 batch operations per hour
def batch_delete_reels():
    """
    Delete multiple reels in a batch operation
    ---
    tags:
      - Reels
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - reel_ids
          properties:
            reel_ids:
              type: array
              items:
                type: integer
              description: Array of reel IDs to delete (max 50)
    responses:
      200:
        description: Batch delete completed
      400:
        description: Invalid input
      403:
        description: Forbidden (not a merchant or unauthorized)
      500:
        description: Server error
    """
    return ReelsController.batch_delete_reels()

