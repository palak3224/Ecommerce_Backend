from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

from auth.utils import user_role_required
from common.decorators import rate_limit, cache_response
from auth.models import User
from common.database import db
from common.cache import get_redis_client
from auth.controllers import upload_profile_image, get_current_user


# Schema definitions
class UpdateUserProfileSchema(Schema):
    first_name = fields.Str(validate=validate.Length(min=1, max=100))
    last_name = fields.Str(validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(max=20))

# Create users blueprint
users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
# @user_role_required
@cache_response(timeout=60, key_prefix='user_profile')
def get_profile():
    """Get user profile."""
    user_id = get_jwt_identity()
    user = User.get_by_id(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "profile": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "profile_img": user.profile_img,
            "is_email_verified": user.is_email_verified,
            "is_phone_verified": user.is_phone_verified,
            "role": user.role.value,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }
    }), 200

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
@user_role_required
def update_profile():
    """Update user profile."""
    try:
        # Validate request data
        schema = UpdateUserProfileSchema()
        data = schema.load(request.json)
        
        user_id = get_jwt_identity()
        user = User.get_by_id(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Update profile fields
        for field, value in data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        db.session.commit()

        # --- ADD CACHE INVALIDATION ---
        redis = get_redis_client()
        if redis:
            redis.delete(f"user_profile:{user_id}")
            redis.delete(f"user:{user_id}")
        
        return jsonify({
            "message": "Profile updated successfully",
            "profile": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "profile_img": user.profile_img
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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
@user_role_required
def upload_profile_image_route():
    """
    Upload or update user profile image.
    Expects a multipart/form-data request with a file part named 'profile_image'.
    """
    user_id = get_jwt_identity()
    # Call the controller function that now contains all the logic
    response, status_code = upload_profile_image(user_id)
    return jsonify(response), status_code