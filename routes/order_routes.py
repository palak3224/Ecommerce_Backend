from flask import Blueprint, request, jsonify
from controllers.order_controller import OrderController
from models.enums import OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum
from auth.utils import role_required
from auth.models.models import UserRole
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.order import Order, OrderItem
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from common.database import db
from flask_cors import cross_origin
import logging

logger = logging.getLogger(__name__)

order_bp = Blueprint('order', __name__, url_prefix='/api/orders')

@order_bp.route('', methods=['POST'])
@order_bp.route('/', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def create_order():
    """
    Create a new order.
    
    Request Body:
    {
        "items": [
            {
                "product_id": 1,
                "merchant_id": 1,
                "product_name_at_purchase": "Product Name",
                "sku_at_purchase": "SKU123",
                "quantity": 2,
                "unit_price_at_purchase": "10.00",
                "item_subtotal_amount": "20.00",
                "final_price_for_item": "20.00"
            }
        ],
        "subtotal_amount": "20.00",
        "discount_amount": "0.00",
        "tax_amount": "2.00",
        "shipping_amount": "5.00",
        "total_amount": "27.00",
        "currency": "USD",
        "payment_method": "credit_card",  # Must be one of: credit_card, debit_card, cash_on_delivery
        "payment_card_id": 1,  # Required if payment_method is credit_card or debit_card
        "shipping_address_id": 1,
        "billing_address_id": 1,
        "shipping_method_name": "Standard Shipping",
        "customer_notes": "Please deliver in the evening",
        "internal_notes": "Handle with care"
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "order_id": "123",
            "user_id": 1,
            "order_status": "processing",
            "payment_status": "paid",
            "total_amount": "27.00",
            "items": [...],
            "status_history": [...]
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        order_data = request.get_json()
        
        if not order_data:
            return jsonify({
                'status': 'error',
                'message': 'No order data provided'
            }), 400

        # Validate payment method
        payment_method = order_data.get('payment_method')
        if not payment_method:
            return jsonify({
                'status': 'error',
                'message': 'Payment method is required'
            }), 400

        try:
            # Validate that the payment method is a valid enum value
            payment_method_enum = PaymentMethodEnum(payment_method)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': f'Invalid payment method. Must be one of: {[method.value for method in PaymentMethodEnum]}'
            }), 400

        # Validate payment card for card payments
        if payment_method_enum in [PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.DEBIT_CARD]:
            if not order_data.get('payment_card_id'):
                return jsonify({
                    'status': 'error',
                    'message': 'Payment card ID is required for card payments'
                }), 400
            
        result = OrderController.create_order(user_id, order_data)
        return jsonify({
            'status': 'success',
            'data': result
        }), 201
        
    except ValueError as ve:
        logger.error(f"Validation error creating order: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<string:order_id>', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value, UserRole.ADMIN.value, UserRole.MERCHANT.value])
def get_order(order_id):
    """
    Get detailed information about a specific order
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - in: path
        name: order_id
        type: string
        required: true
        description: ID of the order to retrieve
    responses:
      200:
        description: Order details retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                order_id:
                  type: string
                user_id:
                  type: integer
                order_status:
                  type: string
                  enum: [PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
                payment_status:
                  type: string
                  enum: [PENDING, PAID, FAILED, REFUNDED]
                total_amount:
                  type: number
                  format: float
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      product_id:
                        type: integer
                      product_name:
                        type: string
                      quantity:
                        type: integer
                      unit_price:
                        type: number
                        format: float
                shipping_address:
                  type: object
                  properties:
                    address_line1:
                      type: string
                    city:
                      type: string
                    state:
                      type: string
                    postal_code:
                      type: string
                    country:
                      type: string
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have permission to view this order
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        order = OrderController.get_order(order_id)
        
        if not order:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        # Check if user has permission to view this order
        if user_id != order['user_id'] and not request.user.is_admin and not request.user.is_merchant:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized access'
            }), 403
            
        return jsonify({
            'status': 'success',
            'data': order
        })
        
    except Exception as e:
        logger.error(f"Error getting order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/user', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_user_orders():
    """
    Get all orders for the authenticated user
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        default: 1
        description: Page number for pagination
      - name: per_page
        in: query
        type: integer
        required: false
        default: 10
        description: Number of items per page
      - name: status
        in: query
        type: string
        required: false
        description: Filter orders by status (PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)
    responses:
      200:
        description: List of user's orders retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                orders:
                  type: array
                  items:
                    type: object
                    properties:
                      order_id:
                        type: string
                      order_date:
                        type: string
                        format: date-time
                      order_status:
                        type: string
                        enum: [PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
                      total_amount:
                        type: number
                        format: float
                      item_count:
                        type: integer
                pagination:
                  type: object
                  properties:
                    total:
                      type: integer
                    pages:
                      type: integer
                    current_page:
                      type: integer
                    per_page:
                      type: integer
      401:
        description: Unauthorized - Invalid or missing token
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status')
        
        result = OrderController.get_user_orders(user_id, page, per_page, status)
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error getting user orders: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<string:order_id>/status', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value, UserRole.ADMIN.value, UserRole.MERCHANT.value])
def update_order_status(order_id):
    """
    Update the status of an existing order
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - in: path
        name: order_id
        type: string
        required: true
        description: ID of the order to update
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
                enum: [PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
                description: New status for the order
              notes:
                type: string
                description: Optional notes about the status change
    responses:
      200:
        description: Order status updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                order_id:
                  type: string
                order_status:
                  type: string
                  enum: [PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
                status_history:
                  type: array
                  items:
                    type: object
                    properties:
                      status:
                        type: string
                      changed_at:
                        type: string
                        format: date-time
                      changed_by:
                        type: integer
                      notes:
                        type: string
      400:
        description: Invalid request - Missing or invalid status
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have permission to update this order
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Status is required'
            }), 400
            
        try:
            new_status = OrderStatusEnum(data['status'])
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid order status'
            }), 400
            
        result = OrderController.update_order_status(
            order_id,
            new_status,
            get_jwt_identity(),
            data.get('notes')
        )
        
        if not result:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<string:order_id>/payment', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value, UserRole.ADMIN.value])
def update_payment_status(order_id):
    """
    Update the payment status of an existing order
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - in: path
        name: order_id
        type: string
        required: true
        description: ID of the order to update payment status
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - payment_status
            properties:
              payment_status:
                type: string
                enum: [PENDING, PAID, FAILED, REFUNDED]
                description: New payment status for the order
              transaction_id:
                type: string
                description: Optional transaction ID from payment gateway
              gateway_name:
                type: string
                description: Optional name of the payment gateway used
    responses:
      200:
        description: Payment status updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                order_id:
                  type: string
                payment_status:
                  type: string
                  enum: [PENDING, PAID, FAILED, REFUNDED]
                transaction_id:
                  type: string
                gateway_name:
                  type: string
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid payment status
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have permission to update this order
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        # Validate required fields
        if 'payment_status' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Payment status is required'
            }), 400

        # Validate payment status
        try:
            payment_status = PaymentStatusEnum(data['payment_status'])
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': f'Invalid payment status. Must be one of: {[status.value for status in PaymentStatusEnum]}'
            }), 400

        # Get the current user
        user_id = get_jwt_identity()
        
        # Get the order to check ownership
        order = OrderController.get_order(order_id)
        if not order:
            return jsonify({
                'status': 'error',
                'message': f'Order not found with ID: {order_id}'
            }), 404

        # Check if user has permission to update this order
        if str(order['user_id']) != str(user_id) and not request.user.is_admin:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized to update this order'
            }), 403

        # Update payment status
        try:
            result = OrderController.update_payment_status(
                order_id,
                payment_status,
                data.get('transaction_id'),
                data.get('gateway_name')
            )
            
            return jsonify({
                'status': 'success',
                'data': result
            })
            
        except ValueError as ve:
            return jsonify({
                'status': 'error',
                'message': str(ve)
            }), 404
        except Exception as e:
            logger.error(f"Error updating payment status: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f"Error in update_payment_status route: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@order_bp.route('/<string:order_id>/cancel', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value, UserRole.ADMIN.value])
def cancel_order(order_id):
    """
    Cancel an existing order
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - in: path
        name: order_id
        type: string
        required: true
        description: ID of the order to cancel
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              notes:
                type: string
                description: Optional notes explaining the reason for cancellation
    responses:
      200:
        description: Order cancelled successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                order_id:
                  type: string
                order_status:
                  type: string
                  example: CANCELLED
                cancelled_at:
                  type: string
                  format: date-time
                cancelled_by:
                  type: integer
                cancellation_notes:
                  type: string
      400:
        description: Invalid request - Order cannot be cancelled
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have permission to cancel this order
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        result = OrderController.cancel_order(
            order_id,
            get_jwt_identity(),
            data.get('notes') if data else None
        )
        
        if not result:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except ValueError as e:
        logger.error(f"Error cancelling order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Admin and Merchant routes
@order_bp.route('/admin', methods=['GET'])
@jwt_required()
@role_required([UserRole.ADMIN.value, UserRole.MERCHANT.value])
def get_all_orders():
    """
    Get all orders in the system (admin) or orders for a specific merchant
    ---
    tags:
      - Orders
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        default: 1
        description: Page number for pagination
      - name: per_page
        in: query
        type: integer
        required: false
        default: 10
        description: Number of items per page
      - name: status
        in: query
        type: string
        required: false
        description: Filter orders by status (PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)
      - name: merchant_id
        in: query
        type: integer
        required: false
        description: Filter orders by merchant ID (admin only)
    responses:
      200:
        description: List of orders retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                orders:
                  type: array
                  items:
                    type: object
                    properties:
                      order_id:
                        type: string
                      user_id:
                        type: integer
                      merchant_id:
                        type: integer
                      order_date:
                        type: string
                        format: date-time
                      order_status:
                        type: string
                        enum: [PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
                      payment_status:
                        type: string
                        enum: [PENDING, PAID, FAILED, REFUNDED]
                      total_amount:
                        type: number
                        format: float
                      item_count:
                        type: integer
                pagination:
                  type: object
                  properties:
                    total:
                      type: integer
                    pages:
                      type: integer
                    current_page:
                      type: integer
                    per_page:
                      type: integer
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      500:
        description: Internal server error
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status')
        merchant_id = request.args.get('merchant_id')
        
        # If user is merchant, only show their orders
        if request.user.is_merchant:
            merchant_id = request.user.merchant_profile.id
        
        result = OrderController.get_all_orders(page, per_page, status, merchant_id)
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error getting all orders: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/statistics/trendy-products', methods=['GET'])
@cross_origin()
def get_trendy_products():
    """
    Get statistics for trendy products based on order history
    ---
    tags:
      - Orders
    parameters:
      - in: query
        name: days
        type: integer
        required: false
        default: 30
        description: Number of days to look back for orders
      - in: query
        name: limit
        type: integer
        required: false
        default: 10
        description: Maximum number of products to return
    responses:
      200:
        description: List of trendy products with their order statistics
        schema:
          type: object
          properties:
            products:
              type: array
              items:
                type: object
                properties:
                  product_id:
                    type: integer
                  total_ordered:
                    type: integer
                  order_count:
                    type: integer
      500:
        description: Internal server error
    """
    try:
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        # Calculate the date to look back from
        lookback_date = datetime.utcnow() - timedelta(days=days)
        
        # Query to get product statistics
        product_stats = db.session.query(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label('total_ordered'),
            func.count(OrderItem.order_id).label('order_count')
        ).join(
            OrderItem.order
        ).filter(
            OrderItem.product_id.isnot(None),
            Order.order_status == 'completed',
            Order.order_date >= lookback_date
        ).group_by(
            OrderItem.product_id
        ).order_by(
            desc('total_ordered')
        ).limit(limit).all()
        
        # Format the response
        result = [{
            'product_id': stat[0],
            'total_ordered': stat[1],
            'order_count': stat[2]
        } for stat in product_stats]
        
        return jsonify({
            'status': 'success',
            'data': {
                'products': result,
                'period_days': days,
                'total_products': len(result)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting trendy products statistics: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<string:order_id>/track', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value, UserRole.ADMIN.value, UserRole.MERCHANT.value])
def track_order(order_id):
    """
    Track an order and get detailed information including product details and images.
    
    ---
    tags:
      - Orders
    parameters:
      - in: path
        name: order_id
        type: string
        required: true
        description: The ID of the order to track
    responses:
      200:
        description: Order tracking information
        schema:
          type: object
          properties:
            status:
              type: string
            data:
              type: object
              properties:
                order_id:
                  type: string
                order_status:
                  type: string
                order_date:
                  type: string
                total_amount:
                  type: string
                currency:
                  type: string
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      product_name:
                        type: string
                      quantity:
                        type: integer
                      unit_price:
                        type: string
                      total_price:
                        type: string
                      product_image:
                        type: string
                      item_status:
                        type: string
                status_history:
                  type: array
                  items:
                    type: object
                    properties:
                      status:
                        type: string
                      changed_at:
                        type: string
                      notes:
                        type: string
      404:
        description: Order not found
      403:
        description: Unauthorized access
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        
        # Get tracking information
        tracking_info = OrderController.track_order(order_id)
        
        if not tracking_info:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        # Check if user has permission to view this order
        order = Order.query.get(order_id)
        if not order:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        if (str(order.user_id) != str(user_id) and 
            not request.user.is_admin and 
            not request.user.is_merchant):
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized access'
            }), 403
            
        return jsonify({
            'status': 'success',
            'data': tracking_info
        })
        
    except ValueError as ve:
        logger.error(f"Validation error tracking order: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error tracking order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 