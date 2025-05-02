import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename

from auth.models import User, UserRole, RefreshToken

def generate_email_verification_link(token, base_url):
    """Generate email verification link."""
    return f"{base_url}/verify-email/{token}"

def upload_to_cloudinary(file, folder, public_id=None):
    """Upload a file to Cloudinary."""
    try:
        # Validate file type
        if not file:
            return None, "No file provided"
        
        # Get file extension
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if file_ext not in current_app.config['ALLOWED_IMAGE_EXTENSIONS']:
            return None, f"Invalid file type. Allowed types: {', '.join(current_app.config['ALLOWED_IMAGE_EXTENSIONS'])}"
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder=folder,
            public_id=public_id,
            resource_type="auto",
            unique_filename=True,
            overwrite=True
        )
        
        return upload_result, None
    except Exception as e:
        current_app.logger.error(f"Cloudinary upload error: {str(e)}")
        return None, str(e)

def delete_from_cloudinary(public_id):
    """Delete a file from Cloudinary."""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result, None
    except Exception as e:
        current_app.logger.error(f"Cloudinary delete error: {str(e)}")
        return None, str(e)

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