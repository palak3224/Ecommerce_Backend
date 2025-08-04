from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from controllers.shop.public.public_shop_cart import PublicShopCartController
from auth.utils import role_required
from auth.models.models import UserRole
import logging

logger = logging.getLogger(__name__)

public_shop_cart_bp = Blueprint('public_shop_cart', __name__)

@public_shop_cart_bp.route('/<int:shop_id>', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_shop_cart(shop_id):
    """
    Get the current user's cart for a specific shop
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
    responses:
      200:
        description: Shop cart retrieved successfully
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
                shop_id:
                  type: integer
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      cart_item_id:
                        type: integer
                      shop_product_id:
                        type: integer
                      quantity:
                        type: integer
                      selected_attributes:
                        type: object
                        description: Selected attributes for the product
                        example: {"1": "red", "2": ["small", "medium"]}
      400:
        description: Error retrieving shop cart
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
        success, cart_data = PublicShopCartController.get_cart_details(user_id, shop_id)
        return jsonify({
            'status': 'success',
            'data': cart_data
        })
    except Exception as e:
        logger.error(f"Error getting shop cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@public_shop_cart_bp.route('/<int:shop_id>/add', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def add_to_shop_cart(shop_id):
    """
    Add a shop product to the user's cart
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - shop_product_id
            - quantity
          properties:
            shop_product_id:
              type: integer
              description: ID of the shop product to add
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
        description: Product added to shop cart successfully
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
                shop_id:
                  type: integer
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      cart_item_id:
                        type: integer
                      shop_product_id:
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
        
        # Debug logging
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.get_data(as_text=True)}")
        logger.info(f"Parsed JSON data: {data}")
        
        if not data or 'shop_product_id' not in data or 'quantity' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        shop_product_id = data['shop_product_id']
        quantity = data['quantity']
        selected_attributes = data.get('selected_attributes', {})
        
        cart = PublicShopCartController.add_to_cart(user_id, shop_id, shop_product_id, quantity, selected_attributes)
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
        logger.error(f"Error adding to shop cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error adding item to shop cart: {str(e)}'
        }), 500

@public_shop_cart_bp.route('/<int:shop_id>/update/<int:cart_item_id>', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value])
def update_shop_cart_item(shop_id, cart_item_id):
    """
    Update the quantity of an item in the shop cart
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
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
        description: Shop cart item updated successfully
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
                shop_product_id:
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
        cart_item = PublicShopCartController.update_cart_item(cart_item_id, quantity)
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
        logger.error(f"Error updating shop cart item: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error updating shop cart item: {str(e)}'
        }), 500

@public_shop_cart_bp.route('/<int:shop_id>/remove/<int:cart_item_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def remove_from_shop_cart(shop_id, cart_item_id):
    """
    Remove an item from the shop cart
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: path
        name: cart_item_id
        type: integer
        required: true
        description: ID of the cart item to remove
    responses:
      200:
        description: Item removed from shop cart successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Item removed from shop cart successfully
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
        PublicShopCartController.remove_from_cart(cart_item_id)
        return jsonify({
            'status': 'success',
            'message': 'Item removed from shop cart successfully'
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error removing from shop cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error removing item from shop cart: {str(e)}'
        }), 500

@public_shop_cart_bp.route('/<int:shop_id>/clear', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def clear_shop_cart(shop_id):
    """
    Remove all items from the user's shop cart
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
    responses:
      200:
        description: Shop cart cleared successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Shop cart cleared successfully
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
        PublicShopCartController.clear_cart(user_id, shop_id)
        return jsonify({
            'status': 'success',
            'message': 'Shop cart cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing shop cart: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error clearing shop cart: {str(e)}'
        }), 500

@public_shop_cart_bp.route('/<int:shop_id>/items', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_shop_cart_items(shop_id):
    """
    Get all items in the user's shop cart with detailed product information
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
    responses:
      200:
        description: Shop cart items retrieved successfully
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
                  shop_product_id:
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
        cart_items = PublicShopCartController.get_cart_items(user_id, shop_id)
        
        # Format the response to match frontend expectations
        formatted_items = [{
            'cart_item_id': item.cart_item_id,
            'shop_product_id': item.shop_product_id,
            'quantity': item.quantity,
            'selected_attributes': item.get_selected_attributes(),
            'product': {
                'name': item.product_name,
                'price': float(item.product_price),
                'original_price': float(item.product_price),  # Use stored price as original
                'special_price': float(item.product_special_price) if item.product_special_price else None,
                'image_url': item.product_image_url,
                'stock': item.product_stock_qty,
                'is_deleted': False
            }
        } for item in cart_items]

        return jsonify({
            'status': 'success',
            'data': formatted_items
        }), 200
    except Exception as e:
        logger.error(f"Error getting shop cart items: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve shop cart items: {str(e)}'
        }), 500

@public_shop_cart_bp.route('/user/carts', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_user_shop_carts():
    """
    Get all shop carts for the current user across different shops
    ---
    tags:
      - Shop Cart
    security:
      - Bearer: []
    responses:
      200:
        description: User shop carts retrieved successfully
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
                  cart_id:
                    type: integer
                  user_id:
                    type: integer
                  shop_id:
                    type: integer
                  items:
                    type: array
                    items:
                      type: object
                      properties:
                        cart_item_id:
                          type: integer
                        shop_product_id:
                          type: integer
                        quantity:
                          type: integer
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
        carts = PublicShopCartController.get_user_carts(user_id)
        return jsonify({
            'status': 'success',
            'data': carts
        }), 200
    except Exception as e:
        logger.error(f"Error getting user shop carts: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve user shop carts: {str(e)}'
        }), 500
