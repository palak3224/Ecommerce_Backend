from flask import Blueprint, request, jsonify
from controllers.order_controller import OrderController
from models.enums import OrderStatusEnum, PaymentStatusEnum
from auth.utils import role_required
from auth.models.models import UserRole
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger(__name__)

order_bp = Blueprint('order', __name__, url_prefix='/api/orders')

@order_bp.route('', methods=['POST'])
@order_bp.route('/', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def create_order():
    try:
        user_id = get_jwt_identity()
        order_data = request.get_json()
        
        if not order_data:
            return jsonify({
                'status': 'error',
                'message': 'No order data provided'
            }), 400
            
        result = OrderController.create_order(user_id, order_data)
        return jsonify({
            'status': 'success',
            'data': result
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_order(order_id):
    try:
        user_id = get_jwt_identity()
        order = OrderController.get_order(order_id)
        
        if not order:
            return jsonify({
                'status': 'error',
                'message': 'Order not found'
            }), 404
            
        if user_id != order['user_id'] and not request.user.is_admin:
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
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        result = OrderController.get_user_orders(user_id, page, per_page)
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

@order_bp.route('/<int:order_id>/status', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value])
def update_order_status(order_id):
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

@order_bp.route('/<int:order_id>/payment', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value])
def update_payment_status(order_id):
    try:
        data = request.get_json()
        if not data or 'payment_status' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Payment status is required'
            }), 400
            
        try:
            payment_status = PaymentStatusEnum(data['payment_status'])
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid payment status'
            }), 400
            
        result = OrderController.update_payment_status(
            order_id,
            payment_status,
            data.get('transaction_id'),
            data.get('gateway_name')
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
        logger.error(f"Error updating payment status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@order_bp.route('/<int:order_id>/cancel', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def cancel_order(order_id):
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

# Admin routes
@order_bp.route('/admin', methods=['GET'])
@jwt_required()
@role_required([UserRole.ADMIN.value])
def get_all_orders():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status')
        
        # TODO: Implement admin order listing with filters
        return jsonify({
            'status': 'error',
            'message': 'Not implemented yet'
        }), 501
        
    except Exception as e:
        logger.error(f"Error getting all orders: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 