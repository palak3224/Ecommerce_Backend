from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, create_refresh_token
from marshmallow import Schema, fields, validate, ValidationError, validates_schema

from auth.controllers import (
    register_user, register_merchant, login_user, refresh_access_token,
    logout_user, verify_email, google_auth, get_current_user,
    request_password_reset, reset_password
)
from auth.utils import user_role_required, merchant_role_required, admin_role_required
from auth.models import User, MerchantProfile

# Schema definitions
class RegisterUserSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    phone = fields.Str()

class RegisterMerchantSchema(Schema):
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    phone = fields.Str()
    business_name = fields.Str(required=True)
    business_description = fields.Str()
    business_email = fields.Email(required=True)
    business_phone = fields.Str()
    business_address = fields.Str()

class LoginSchema(Schema):
    email = fields.Email(required=False)
    business_email = fields.Email(required=False)
    password = fields.Str(required=True, validate=validate.Length(min=8))

    @validates_schema
    def validate_email_or_business_email(self, data, **kwargs):
        if not data.get('email') and not data.get('business_email'):
            raise ValidationError("Either email or business_email is required")

class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)

class GoogleAuthSchema(Schema):
    id_token = fields.Str(required=True)

class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)

class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))

# Create auth blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    try:
        # Validate request data
        schema = RegisterUserSchema()
        data = schema.load(request.json)
        
        # Register user
        response, status_code = register_user(data)
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/register/merchant', methods=['POST'])
def register_merchant_route():
    """Register a new merchant."""
    try:
        # Validate request data
        schema = RegisterMerchantSchema()
        data = schema.load(request.json)
        
        # Register merchant
        response, status_code = register_merchant(data)
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login a user."""
    try:
        # Validate request data
        schema = LoginSchema()
        data = schema.load(request.json)
        
        # Check if this is a business email or regular email login
        if data.get('business_email'):
            data['email'] = data.get('business_email')
            # Flag to indicate this is a business email login
            data['business_email'] = True
        
        # Login user
        response, status_code = login_user(data)
        
        if status_code == 200:
            # Get merchant profile if user is a merchant
            user_id = response.get('user', {}).get('id')
            if user_id:
                merchant = MerchantProfile.get_by_user_id(user_id)
                if merchant:
                    response['merchant'] = {
                        'id': merchant.id,
                        'user_id': merchant.user_id,
                        'business_name': merchant.business_name,
                        'business_description': merchant.business_description,
                        'business_email': merchant.business_email,
                        'business_phone': merchant.business_phone,
                        'business_address': merchant.business_address,
                        'gstin': merchant.gstin,
                        'pan_number': merchant.pan_number,
                        'store_url': merchant.store_url,
                        'logo_url': merchant.logo_url,
                        'logo_public_id': merchant.logo_public_id,
                        'verification_status': merchant.verification_status.value if merchant.verification_status else None,
                        'verification_submitted_at': merchant.verification_submitted_at.isoformat() if merchant.verification_submitted_at else None,
                        'verification_completed_at': merchant.verification_completed_at.isoformat() if merchant.verification_completed_at else None,
                        'verification_notes': merchant.verification_notes,
                        'is_verified': merchant.is_verified,
                        'created_at': merchant.created_at.isoformat(),
                        'updated_at': merchant.updated_at.isoformat()
                    }
        
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    
@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token."""
    try:
        # Validate request data
        schema = RefreshTokenSchema()
        data = schema.load(request.json)
        
        # Refresh token
        response, status_code = refresh_access_token(data['refresh_token'])
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout a user."""
    try:
        # Validate request data
        schema = RefreshTokenSchema()
        data = schema.load(request.json)
        
        # Logout user
        response, status_code = logout_user(data['refresh_token'])
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email_route(token):
    """Verify user email and return tokens for automatic login."""
    try:
        # Verify email and get response
        response, status_code = verify_email(token)
        
        if status_code != 200:
            return jsonify(response), status_code
            
        # Get user from database
        user_id = response.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID not found in verification response"}), 400
            
        user = User.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        # Generate tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            "message": "Email verified successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_verified": True
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@auth_bp.route('/google', methods=['POST'])
def google_auth_route():
    """Authenticate with Google OAuth."""
    try:
        # Validate request data
        schema = GoogleAuthSchema()
        data = schema.load(request.json)
        
        # Authenticate with Google
        response, status_code = google_auth(data)
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """Get current user information."""
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Invalid token identity"}), 401
            
        response, status_code = get_current_user(user_id)
        return jsonify(response), status_code
    except Exception as e:
        current_app.logger.error(f"Error in /me endpoint: {str(e)}")
        if "Invalid token" in str(e):
            return jsonify({"error": "Invalid or expired token"}), 401
        return jsonify({"error": "Failed to get user information"}), 500

@auth_bp.route('/password/reset-request', methods=['POST'])
def password_reset_request():
    """Request password reset."""
    try:
        # Validate request data
        schema = PasswordResetRequestSchema()
        data = schema.load(request.json)
        
        # Request password reset
        response, status_code = request_password_reset(data['email'])
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@auth_bp.route('/password/reset', methods=['POST'])
def password_reset():
    """Reset password with token."""
    try:
        # Validate request data
        schema = PasswordResetSchema()
        data = schema.load(request.json)
        
        # Reset password
        response, status_code = reset_password(data['token'], data['new_password'])
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400