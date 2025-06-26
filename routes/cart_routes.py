from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from controllers.cart_controller import CartController
from auth.utils import role_required
from auth.models.models import UserRole
import logging

logger = logging.getLogger(__name__)

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_cart():
    """
    Get the current user's cart
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    responses:
      200:
        description: Cart retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                cart_id:
                  type: integer
                user_id:
                  type: integer
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      cart_item_id:
                        type: integer
                      product_id:
                        type: integer
                      quantity:
                        type: integer
                      selected_attributes:
                        type: object
                        description: Selected attributes for the product
                        example: {"1": "red", "2": ["small", "medium"]}
      400:
        description: Error retrieving cart
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        cart = CartController.get_cart(user_id)
        return jsonify({
            'status': 'success',
            'data': cart.serialize()
        })
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@cart_bp.route('/add', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def add_to_cart():
    """
    Add a product to the user's cart
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
            - quantity
          properties:
            product_id:
              type: integer
              description: ID of the product to add
            quantity:
              type: integer
              description: Quantity of the product to add
              minimum: 1
            selected_attributes:
              type: object
              description: Selected attributes for the product (optional)
              example: {"1": "red", "2": ["small", "medium"]}
    responses:
      200:
        description: Product added to cart successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                cart_id:
                  type: integer
                user_id:
                  type: integer
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      cart_item_id:
                        type: integer
                      product_id:
                        type: integer
                      quantity:
                        type: integer
                      selected_attributes:
                        type: object
      400:
        description: Invalid request or product not available
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'product_id' not in data or 'quantity' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        product_id = data['product_id']
        quantity = data['quantity']
        selected_attributes = data.get('selected_attributes', {})
        
        cart = CartController.add_to_cart(user_id, product_id, quantity, selected_attributes)
        return jsonify({
            'status': 'success',
            'data': cart.serialize()
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error adding item to cart: {str(e)}'
        }), 500

@cart_bp.route('/update/<int:cart_item_id>', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value])
def update_cart_item(cart_item_id):
    """
    Update the quantity of an item in the cart
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: cart_item_id
        type: integer
        required: true
        description: ID of the cart item to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - quantity
          properties:
            quantity:
              type: integer
              description: New quantity for the cart item
              minimum: 1
    responses:
      200:
        description: Cart item updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                cart_item_id:
                  type: integer
                product_id:
                  type: integer
                quantity:
                  type: integer
      400:
        description: Invalid request or cart item not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'quantity' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing quantity field'
            }), 400
        
        quantity = data['quantity']
        cart_item = CartController.update_cart_item(cart_item_id, quantity)
        return jsonify({
            'status': 'success',
            'data': cart_item.serialize()
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error updating cart item: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error updating cart item: {str(e)}'
        }), 500

@cart_bp.route('/remove/<int:cart_item_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def remove_from_cart(cart_item_id):
    """
    Remove an item from the cart
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: cart_item_id
        type: integer
        required: true
        description: ID of the cart item to remove
    responses:
      200:
        description: Item removed from cart successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Item removed from cart successfully
      400:
        description: Invalid request or cart item not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        CartController.remove_from_cart(cart_item_id)
        return jsonify({
            'status': 'success',
            'message': 'Item removed from cart successfully'
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error removing from cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error removing item from cart: {str(e)}'
        }), 500

@cart_bp.route('/clear', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def clear_cart():
    """
    Remove all items from the user's cart
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    responses:
      200:
        description: Cart cleared successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Cart cleared successfully
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        CartController.clear_cart(user_id)
        return jsonify({
            'status': 'success',
            'message': 'Cart cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error clearing cart: {str(e)}'
        }), 500

@cart_bp.route('/items', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_cart_items():
    """
    Get all items in the user's cart with detailed product information
    ---
    tags:
      - Cart
    security:
      - Bearer: []
    responses:
      200:
        description: Cart items retrieved successfully
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
                  cart_item_id:
                    type: integer
                  product_id:
                    type: integer
                  merchant_id:
                    type: integer
                  quantity:
                    type: integer
                  selected_attributes:
                    type: object
                    description: Selected attributes for the product
                    example: {"1": "red", "2": ["small", "medium"]}
                  product:
                    type: object
                    properties:
                      name:
                        type: string
                      price:
                        type: number
                        format: float
                      image_url:
                        type: string
                      stock:
                        type: integer
                      is_deleted:
                        type: boolean
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        user_id = get_jwt_identity()
        cart_items = CartController.get_cart_items(user_id)
        
        # Format the response to match frontend expectations
        formatted_items = [{
            'cart_item_id': item.cart_item_id,
            'product_id': item.product_id,
            'merchant_id': item.merchant_id,
            'quantity': item.quantity,
            'selected_attributes': item.get_selected_attributes(),
            'product': {
                'name': item.product_name,
                'price': float(item.product_price),
                'original_price': float(item.product_price),  # Use stored price as original
                'special_price': float(item.product_special_price) if item.product_special_price else None,
                'image_url': item.product_image_url,
                'stock': item.product_stock_qty,
                'is_deleted': item.product.is_deleted if hasattr(item.product, 'is_deleted') else False
            }
        } for item in cart_items]

        return jsonify({
            'status': 'success',
            'data': formatted_items
        }), 200
    except Exception as e:
        logger.error(f"Error getting cart items: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve cart items: {str(e)}'
        }), 500 