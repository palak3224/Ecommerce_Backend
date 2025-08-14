"""
Shop Review Routes
---
This blueprint handles creation, retrieval, and deletion of shop product reviews by users.
All endpoints are JWT-protected except for public product review listing.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest
import logging

from auth.utils import role_required
from auth.models.models import UserRole
from controllers.shop.shop_review_controller import ShopReviewController

logger = logging.getLogger(__name__)

shop_review_bp = Blueprint('shop_review', __name__, url_prefix='/api/shop-reviews')


@shop_review_bp.route('', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def create_shop_review():
        """
        Create a new shop product review
        ---
        tags:
            - Shop Reviews
        security:
            - Bearer: []
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        required:
                            - shop_order_id
                            - shop_product_id
                            - rating
                            - title
                            - body
                        properties:
                            shop_order_id:
                                type: string
                                description: ID of the delivered shop order containing the product
                            shop_product_id:
                                type: integer
                                description: Product ID being reviewed
                            rating:
                                type: integer
                                minimum: 1
                                maximum: 5
                                description: Star rating (1-5)
                            title:
                                type: string
                                description: Review title
                            body:
                                type: string
                                description: Review body text
                            images:
                                type: array
                                items:
                                    type: string
                                description: Optional list of base64 data URLs for images. Max 5 images, each < 5 MB.
        responses:
            201:
                description: Review created successfully
                schema:
                    type: object
                    properties:
                        status:
                            type: string
                        data:
                            type: object
            400:
                description: Bad request
            401:
                description: Unauthorized
            500:
                description: Internal server error
        """
        try:
            user_id = get_jwt_identity()
            review_data = request.get_json()
            if not review_data:
                raise BadRequest('No review data provided')

            result = ShopReviewController.create_review(user_id, review_data)
            return jsonify({'status': 'success', 'data': result}), 201
        except BadRequest as e:
            logger.warning(f"Bad request creating shop review: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error creating shop review: {e}")
            return jsonify({'status': 'error', 'message': 'An unexpected error occurred while creating the review'}), 500


@shop_review_bp.route('/product/<int:shop_product_id>', methods=['GET'])
def get_shop_product_reviews(shop_product_id: int):
        """
        Get reviews for a shop product
        ---
        tags:
            - Shop Reviews
        parameters:
            - name: shop_product_id
                in: path
                type: integer
                required: true
                description: Product ID
            - name: page
                in: query
                type: integer
                default: 1
                description: Page number for pagination
            - name: per_page
                in: query
                type: integer
                default: 10
                description: Number of reviews per page (max 50)
        responses:
            200:
                description: Reviews retrieved successfully
                schema:
                    type: object
                    properties:
                        status:
                            type: string
                        data:
                            type: object
            400:
                description: Bad request
            500:
                description: Internal server error
        """
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            if page < 1:
                raise BadRequest('Page number must be greater than 0')
            if per_page < 1 or per_page > 50:
                raise BadRequest('Items per page must be between 1 and 50')

            result = ShopReviewController.get_product_reviews(shop_product_id, page, per_page)
            return jsonify({'status': 'success', 'data': result}), 200
        except BadRequest as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error getting shop product reviews: {e}")
            return jsonify({'status': 'error', 'message': 'An unexpected error occurred while retrieving product reviews'}), 500


@shop_review_bp.route('/user', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_user_shop_reviews():
        """
        Get reviews written by the current user
        ---
        tags:
            - Shop Reviews
        security:
            - Bearer: []
        parameters:
            - name: page
                in: query
                type: integer
                default: 1
                description: Page number for pagination
            - name: per_page
                in: query
                type: integer
                default: 10
                description: Number of reviews per page (max 50)
        responses:
            200:
                description: User reviews retrieved successfully
                schema:
                    type: object
                    properties:
                        status:
                            type: string
                        data:
                            type: object
            400:
                description: Bad request
            401:
                description: Unauthorized
            500:
                description: Internal server error
        """
        try:
            user_id = get_jwt_identity()
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            if page < 1:
                raise BadRequest('Page number must be greater than 0')
            if per_page < 1 or per_page > 50:
                raise BadRequest('Items per page must be between 1 and 50')

            result = ShopReviewController.get_user_reviews(user_id, page, per_page)
            return jsonify({'status': 'success', 'data': result}), 200
        except BadRequest as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error getting user shop reviews: {e}")
            return jsonify({'status': 'error', 'message': 'An unexpected error occurred while retrieving user reviews'}), 500


@shop_review_bp.route('/<int:review_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def delete_user_shop_review(review_id: int):
        """
        Delete a user’s shop product review
        ---
        tags:
            - Shop Reviews
        security:
            - Bearer: []
        parameters:
            - name: review_id
                in: path
                type: integer
                required: true
                description: Review ID to delete
        responses:
            200:
                description: Review deleted successfully
                schema:
                    type: object
                    properties:
                        status:
                            type: string
            400:
                description: Bad request
            401:
                description: Unauthorized
            500:
                description: Internal server error
        """
        try:
            user_id = get_jwt_identity()
            ok = ShopReviewController.delete_review(review_id, user_id)
            if ok:
                return jsonify({'status': 'success'}), 200
            return jsonify({'status': 'error', 'message': 'Failed to delete review'}), 500
        except BadRequest as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error deleting shop review: {e}")
            return jsonify({'status': 'error', 'message': 'An unexpected error occurred while deleting the review'}), 500
