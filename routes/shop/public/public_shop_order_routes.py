# routes/shop/public/public_shop_order_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from controllers.shop.public.public_shop_order_controller import PublicShopOrderController
from models.enums import OrderStatusEnum

# Create blueprint for shop order routes
public_shop_order_bp = Blueprint('public_shop_order', __name__)

@public_shop_order_bp.route('/shops/<int:shop_id>/orders', methods=['POST'])
@jwt_required()
def create_shop_order(shop_id):
    """
    Create a new shop order
    ---
    tags:
      - Shop Orders
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - shipping_address_id
              - payment_method
            properties:
              shipping_address_id:
                type: integer
                description: User's shipping address ID
              billing_address_id:
                type: integer
                description: User's billing address ID (optional, defaults to shipping)
              payment_method:
                type: string
                enum: [CREDIT_CARD, DEBIT_CARD, PAYPAL, BANK_TRANSFER, COD]
                description: Payment method
              currency:
                type: string
                default: USD
                description: Currency code
              shipping_method_name:
                type: string
                default: Standard Shipping
                description: Shipping method name
              customer_notes:
                type: string
                description: Customer notes for the order
    responses:
      201:
        description: Order created successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: object
              properties:
                order_id:
                  type: string
                shop_id:
                  type: integer
                user_id:
                  type: integer
                order_status:
                  type: string
                total_amount:
                  type: string
                items:
                  type: array
                  items:
                    type: object
      400:
        description: Bad request - validation error
      401:
        description: Unauthorized
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        response = PublicShopOrderController.create_shop_order(shop_id, data)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@public_shop_order_bp.route('/shops/<int:shop_id>/orders', methods=['GET'])
@jwt_required()
def get_user_shop_orders(shop_id):
    """
    Get user's orders for a specific shop
    ---
    tags:
      - Shop Orders
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
      - name: page
        in: query
        type: integer
        default: 1
        description: Page number for pagination
      - name: per_page
        in: query
        type: integer
        default: 10
        description: Number of orders per page
    responses:
      200:
        description: Orders retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: object
              properties:
                orders:
                  type: array
                  items:
                    type: object
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
                    has_next:
                      type: boolean
                    has_prev:
                      type: boolean
      401:
        description: Unauthorized
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Limit per_page to prevent abuse
        per_page = min(per_page, 50)
        
        response = PublicShopOrderController.get_user_shop_orders(shop_id, page, per_page)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@public_shop_order_bp.route('/shops/<int:shop_id>/orders/<string:order_id>', methods=['GET'])
@jwt_required()
def get_shop_order_details(shop_id, order_id):
    """
    Get detailed information for a specific shop order
    ---
    tags:
      - Shop Orders
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
      - name: order_id
        in: path
        type: string
        required: true
        description: Order ID
    responses:
      200:
        description: Order details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: object
              properties:
                order_id:
                  type: string
                shop_id:
                  type: integer
                user_id:
                  type: integer
                order_status:
                  type: string
                order_date:
                  type: string
                  format: date-time
                total_amount:
                  type: string
                items:
                  type: array
                  items:
                    type: object
                status_history:
                  type: array
                  items:
                    type: object
                shipping_address_details:
                  type: object
                billing_address_details:
                  type: object
      401:
        description: Unauthorized
      404:
        description: Shop or order not found
      500:
        description: Internal server error
    """
    try:
        response = PublicShopOrderController.get_shop_order_details(shop_id, order_id)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Admin/Superadmin routes for managing shop orders
@public_shop_order_bp.route('/admin/shop-orders', methods=['GET'])
@jwt_required()
def get_all_shop_orders():
    """
    Get all shop orders (Superadmin access)
    ---
    tags:
      - Shop Orders - Admin
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
        default: 20
        description: Number of orders per page
      - name: shop_id
        in: query
        type: integer
        description: Filter by specific shop ID
      - name: status
        in: query
        type: string
        enum: [PENDING_PAYMENT, PAID, PROCESSING, SHIPPED, DELIVERED, CANCELLED, REFUNDED]
        description: Filter by order status
    responses:
      200:
        description: All shop orders retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: object
              properties:
                orders:
                  type: array
                  items:
                    type: object
                pagination:
                  type: object
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin access required
      500:
        description: Internal server error
    """
    try:
        # Note: Add admin role check at middleware level
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        shop_id = request.args.get('shop_id', type=int)
        status = request.args.get('status')
        
        # Limit per_page to prevent abuse
        per_page = min(per_page, 100)
        
        # Convert status string to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = OrderStatusEnum(status)
            except ValueError:
                return jsonify({'success': False, 'message': f'Invalid status: {status}'}), 400
        
        response = PublicShopOrderController.get_all_shop_orders(page, per_page, shop_id, status_enum)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@public_shop_order_bp.route('/admin/shop-orders/<string:order_id>/status', methods=['PUT'])
@jwt_required()
def update_shop_order_status(order_id):
    """
    Update shop order status (Admin access)
    ---
    tags:
      - Shop Orders - Admin
    security:
      - Bearer: []
    parameters:
      - name: order_id
        in: path
        type: string
        required: true
        description: Order ID
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - status
            properties:
              status:
                type: string
                enum: [PENDING_PAYMENT, PAID, PROCESSING, SHIPPED, DELIVERED, CANCELLED, REFUNDED]
                description: New order status
              notes:
                type: string
                description: Optional notes for status change
    responses:
      200:
        description: Order status updated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            data:
              type: object
      400:
        description: Bad request - invalid status
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin access required
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        # Note: Add admin role check at middleware level
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'message': 'Status is required'}), 400
        
        try:
            new_status = OrderStatusEnum(data['status'])
        except ValueError:
            return jsonify({'success': False, 'message': f'Invalid status: {data["status"]}'}), 400
        
        notes = data.get('notes')
        response = PublicShopOrderController.update_order_status(order_id, new_status, notes)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
