import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from auth.models import User, UserRole, RefreshToken

def generate_email_verification_link(token, base_url):
    """Generate email verification link."""
    return f"{base_url}/verify-email/{token}"

def role_required(required_roles):
    """Decorator to check if user has required role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Verify JWT token
            verify_jwt_in_request()
            
            # Get current user identity
            current_user_id = get_jwt_identity()
            
            # Get user from database
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            # Check if user has required role
            if user.role.value not in required_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def user_role_required(fn):
    """Decorator for endpoints that require user role."""
    return role_required([UserRole.USER.value])(fn)

def merchant_role_required(fn):
    """Decorator for endpoints that require merchant role."""
    return role_required([UserRole.MERCHANT.value])(fn)

def admin_role_required(fn):
    """Decorator for endpoints that require admin role."""
    return role_required([UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value])(fn)

def super_admin_role_required(fn):
    """Decorator for endpoints that require super admin role."""
    return role_required([UserRole.SUPER_ADMIN.value])(fn)

def get_google_provider_cfg():
    """Get Google OAuth provider configuration."""
    import requests
    try:
        return requests.get(current_app.config['GOOGLE_DISCOVERY_URL']).json()
    except Exception as e:
        current_app.logger.error(f"Error fetching Google provider config: {str(e)}")
        return None

def validate_google_token(token):
    """Validate Google OAuth token."""
    try:
        idinfo = jwt.decode(
            token, 
            options={"verify_signature": False},
            algorithms=["RS256"]
        )
        
        # Verify token is issued by Google
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            return None
        
        # Verify audience is our app
        if idinfo['aud'] != current_app.config['GOOGLE_CLIENT_ID']:
            return None
        
        # Check token expiry
        if datetime.fromtimestamp(idinfo['exp']) < datetime.utcnow():
            return None
        
        return idinfo
    except Exception as e:
        current_app.logger.error(f"Error validating Google token: {str(e)}")
        return None