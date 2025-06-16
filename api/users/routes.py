from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

from auth.utils import user_role_required
from common.decorators import rate_limit, cache_response
from auth.models import User
from common.database import db
from common.cache import get_redis_client
from auth.controllers import get_user_profile, update_user_profile, upload_profile_image


# Schema definitions
class UpdateUserProfileSchema(Schema):
    first_name = fields.Str(validate=validate.Length(min=1, max=100))
    last_name = fields.Str(validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(max=20))

# Create users blueprint
users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get the logged-in user's profile."""
    try:
        # FIX: Convert the string identity from JWT to an integer
        user_id = int(get_jwt_identity())
        # Call the controller function
        response, status_code = get_user_profile(user_id)
        return jsonify(response), status_code
    except Exception as e:
        current_app.logger.error(f"Error in get_profile route: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update the logged-in user's profile."""
    try:
        schema = UpdateUserProfileSchema()
        data = schema.load(request.json)
        user_id = int(get_jwt_identity())
        response, status_code = update_user_profile(user_id, data)
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error in update_profile route: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

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



@users_bp.route('/profile/image', methods=['POST'])
@jwt_required()
def upload_profile_image_route():
    """Upload or update user profile image."""
    try:
        user_id = int(get_jwt_identity())
        response, status_code = upload_profile_image(user_id)
        return jsonify(response), status_code
    except Exception as e:
        current_app.logger.error(f"Error in upload_profile_image_route: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500
