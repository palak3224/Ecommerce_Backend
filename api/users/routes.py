from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from auth.utils import user_role_required
from common.decorators import rate_limit, cache_response

# Create users blueprint
users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
@user_role_required
@cache_response(timeout=60, key_prefix='user_profile')
def get_profile():
    """Get user profile."""
    user_id = get_jwt_identity()
    # In a real implementation, fetch user profile from database
    # This is a placeholder
    return {"message": f"User profile for ID: {user_id}"}, 200

@users_bp.route('/orders', methods=['GET'])
@jwt_required()
@user_role_required
@cache_response(timeout=60, key_prefix='user_orders')
def get_orders():
    """Get user orders."""
    user_id = get_jwt_identity()
    # In a real implementation, fetch user orders from database
    # This is a placeholder
    return {"message": f"Orders for user ID: {user_id}"}, 200

@users_bp.route('/cart', methods=['GET'])
@jwt_required()
@user_role_required
def get_cart():
    """Get user shopping cart."""
    user_id = get_jwt_identity()
    # In a real implementation, fetch user cart from database
    # This is a placeholder
    return {"message": f"Cart for user ID: {user_id}"}, 200