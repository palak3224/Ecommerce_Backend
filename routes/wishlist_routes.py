from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from controllers.wishlist_controller import WishlistController
from auth.utils import role_required
from auth.models.models import UserRole
import logging

logger = logging.getLogger(__name__)

wishlist_bp = Blueprint('wishlist', __name__, url_prefix='/api/wishlist')

# Get user's wishlist
@wishlist_bp.route('', methods=['GET'])
@wishlist_bp.route('/', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_wishlist():
    """
    Get the authenticated user's wishlist
    ---
    tags:
      - Wishlist
    security:
      - Bearer: []
    responses:
      200:
        description: Wishlist retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: array
              items:
                type: object
                properties:
                  wishlist_item_id:
                    type: integer
                  user_id:
                    type: integer
                  product_id:
                    type: integer
                  product:
                    type: object
                    properties:
                      product_id:
                        type: integer
                      name:
                        type: string
                      description:
                        type: string
                      price:
                        type: number
                        format: float
                      stock:
                        type: integer
                      merchant_id:
                        type: integer
                      category_id:
                        type: integer
                      created_at:
                        type: string
                        format: date-time
                      updated_at:
                        type: string
                        format: date-time
                  added_at:
                    type: string
                    format: date-time
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return WishlistController.get_wishlist(user_id)
    except Exception as e:
        logger.error(f"Error getting wishlist: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

# Add product to wishlist
@wishlist_bp.route('', methods=['POST'])
@wishlist_bp.route('/', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def add_to_wishlist():
    """
    Add a product to the authenticated user's wishlist
    ---
    tags:
      - Wishlist
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - product_id
            properties:
              product_id:
                type: integer
                description: ID of the product to add to wishlist
    responses:
      200:
        description: Product added to wishlist successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Product added to wishlist successfully
            data:
              type: object
              properties:
                wishlist_item_id:
                  type: integer
                user_id:
                  type: integer
                product_id:
                  type: integer
                added_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid product_id
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      404:
        description: Product not found
      409:
        description: Product already in wishlist
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return WishlistController.add_to_wishlist(user_id)
    except Exception as e:
        logger.error(f"Error adding to wishlist: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

# Remove product from wishlist
@wishlist_bp.route('/<int:wishlist_item_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def remove_from_wishlist(wishlist_item_id):
    """
    Remove a product from the authenticated user's wishlist
    ---
    tags:
      - Wishlist
    security:
      - Bearer: []
    parameters:
      - name: wishlist_item_id
        in: path
        type: integer
        required: true
        description: ID of the wishlist item to remove
    responses:
      200:
        description: Product removed from wishlist successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Product removed from wishlist successfully
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role or does not own this wishlist item
      404:
        description: Wishlist item not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return WishlistController.remove_from_wishlist(user_id, wishlist_item_id)
    except Exception as e:
        logger.error(f"Error removing from wishlist: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

# Clear entire wishlist
@wishlist_bp.route('/clear', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def clear_wishlist():
    """
    Remove all products from the authenticated user's wishlist
    ---
    tags:
      - Wishlist
    security:
      - Bearer: []
    responses:
      200:
        description: Wishlist cleared successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Wishlist cleared successfully
            data:
              type: object
              properties:
                items_removed:
                  type: integer
                  description: Number of items removed from wishlist
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return WishlistController.clear_wishlist(user_id)
    except Exception as e:
        logger.error(f"Error clearing wishlist: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400 