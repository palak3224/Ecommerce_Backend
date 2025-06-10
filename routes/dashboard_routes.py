from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from auth.utils import role_required
from auth.models.models import UserRole
from controllers.merchant.dashboard_controller import MerchantDashboardController
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/recent-orders', methods=['GET'])
@jwt_required()
@role_required([UserRole.MERCHANT.value])
def get_recent_orders():
    """
    Get recent orders for merchant dashboard (e.g., last 5 orders).
    """
    try:
        user_id = get_jwt_identity()
        recent_orders = MerchantDashboardController.get_recent_orders(user_id)

        return jsonify({
            'status': 'success',
            'data': recent_orders
        }), 200

    except ValueError as ve:
        logger.error(f"Validation error getting recent orders: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400

    except Exception as e:
        logger.error(f"Error fetching recent orders: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }), 500
    


@dashboard_bp.route('/monthly-summary', methods=['GET'])
@jwt_required()
@role_required([UserRole.MERCHANT.value])
def get_monthly_summary():
    """
    Get merchant's monthly dashboard summary including total sales, total orders,
    average order value, and their percentage changes from the previous month.
    """
    try:
        user_id = get_jwt_identity()
        summary = MerchantDashboardController.get_monthly_summary(user_id)

        return jsonify({
            'status': 'success',
            'data': summary
        }), 200

    except ValueError as ve:
        logger.error(f"Validation error getting monthly summary: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400

    except Exception as e:
        logger.error(f"Error fetching monthly summary: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }), 500
    

@dashboard_bp.route('/sales-data', methods=['GET'])
@jwt_required()
@role_required([UserRole.MERCHANT.value])
def get_sales_data():
    try:
        user_id = get_jwt_identity()
        sales_data = MerchantDashboardController.get_sales_data(user_id)
        return jsonify({'status': 'success', 'data': sales_data}), 200
    except Exception as e:
        logger.error(f"Error fetching sales data: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred'}), 500   
    


@dashboard_bp.route("/top-products", methods=["GET"])
@jwt_required()
@role_required([UserRole.MERCHANT.value])
def get_top_products():
    """
    Get top selling products for merchant dashboard.
    """
    try:
        user_id = get_jwt_identity()
        products = MerchantDashboardController.get_top_products(user_id)

        return jsonify({
            'status': 'success',
            'data': products
        }), 200

    except ValueError as ve:
        logger.error(f"Validation error getting top products: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400

    except Exception as e:
        logger.error(f"Error fetching top products: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }), 500