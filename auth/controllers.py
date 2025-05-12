from datetime import datetime, timedelta
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from authlib.integrations.flask_client import OAuth

from common.database import db
from auth.models import User, MerchantProfile, RefreshToken, EmailVerification, UserRole, AuthProvider
from auth.utils import validate_google_token
from common.cache import cached
from auth.email_utils import send_verification_email, send_password_reset_email

# Initialize OAuth
oauth = OAuth()

def register_user(data):
    """Register a new user."""
    try:
        # Check if user already exists
        if User.get_by_email(data['email']):
            return {"error": "Email already registered"}, 409
        
        # Create new user
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data.get('phone'),
            role=UserRole.USER
        )
        user.set_password(data['password'])
        user.save()
        
        # Create email verification token
        expires_at = datetime.utcnow() + timedelta(days=1)
        token = EmailVerification.create_token(user.id, expires_at)
        
        # Send verification email
        send_verification_email(user, token)
        
        return {
            "message": "User registered successfully. Please check your email to verify your account.",
            "user_id": user.id
        }, 201
    except IntegrityError:
        db.session.rollback()
        return {"error": "Database error occurred"}, 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return {"error": "Registration failed"}, 500

def register_merchant(data):
    """Register a new merchant."""
    try:
        # Check if user already exists with business email
        if User.get_by_email(data['business_email']):
            return {"error": "Business email already registered"}, 409
        
        # Create new user with merchant role
        user = User(
            email=data['business_email'],  # Use business email as primary email
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data.get('phone'),
            role=UserRole.MERCHANT
        )
        user.set_password(data['password'])
        user.save()
        
        # Create merchant profile
        merchant = MerchantProfile(
            user_id=user.id,
            business_name=data['business_name'],
            business_description=data.get('business_description'),
            business_email=data['business_email'],
            business_phone=data.get('business_phone', data.get('phone')),
            business_address=data.get('business_address')
        )
        merchant.save()
        
        # Create email verification token
        expires_at = datetime.utcnow() + timedelta(days=1)
        token = EmailVerification.create_token(user.id, expires_at)
        
        # Send verification email
        send_verification_email(user, token)
        
        return {
            "message": "Merchant registered successfully. Please check your email to verify your account.",
            "user_id": user.id,
            "merchant_id": merchant.id
        }, 201
    except IntegrityError:
        db.session.rollback()
        return {"error": "Database error occurred"}, 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return {"error": "Registration failed"}, 500
    

def login_user(data):
    """Login a user with email and password."""
    try:
        login_email = data['email']
        password = data['password']
        
        # Check if this is a business email login
        if 'business_email' in data:
            # First check if this is a merchant's business email
            merchant = MerchantProfile.query.filter_by(business_email=login_email).first()
            if merchant:
                # Get the associated user account
                user = User.get_by_id(merchant.user_id)
                if not user or not user.check_password(password):
                    return {"error": "Invalid business email or password"}, 401
                
                if not user.is_active:
                    return {"error": "Account is disabled"}, 403
                
                # Update last login timestamp
                user.update_last_login()
                
                # Generate tokens
                access_token = create_access_token(identity=str(user.id))
                refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
                refresh_token = RefreshToken.create_token(user.id, refresh_expires)
                
                return {
                    "message": "Merchant login successful",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "role": user.role.value
                    }
                }, 200
        
        # Regular user login with email
        user = User.get_by_email(login_email)
        if not user or not user.check_password(password):
            return {"error": "Invalid email or password"}, 401
        
        if not user.is_active:
            return {"error": "Account is disabled"}, 403
        
        # Update last login timestamp
        user.update_last_login()
        
        # Generate tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token = RefreshToken.create_token(user.id, refresh_expires)
        
        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return {"error": "Login failed"}, 500
    
def refresh_access_token(token):
    """Refresh access token using refresh token."""
    try:
        # Validate refresh token
        refresh_token = RefreshToken.get_by_token(token)
        if not refresh_token:
            return {"error": "Invalid refresh token"}, 401
        
        if refresh_token.expires_at < datetime.utcnow():
            refresh_token.revoke()
            return {"error": "Refresh token expired"}, 401
        
        # Generate new access token
        access_token = create_access_token(identity=str(refresh_token.user_id))
        
        return {
            "access_token": access_token
        }, 200
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return {"error": "Failed to refresh token"}, 500

def logout_user(token):
    """Logout a user by revoking refresh token."""
    try:
        # Find and revoke refresh token
        refresh_token = RefreshToken.get_by_token(token)
        if refresh_token:
            refresh_token.revoke()
        
        return {"message": "Logout successful"}, 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return {"error": "Logout failed"}, 500

def verify_email(token):
    """Verify user email with token."""
    try:
        # Find verification token
        verification = EmailVerification.get_by_token(token)
        if not verification:
            return {"error": "Invalid verification token"}, 400
        
        if verification.expires_at < datetime.utcnow():
            return {"error": "Verification token expired"}, 400
        
        # Update user email verification status
        user = User.get_by_id(verification.user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        user.is_email_verified = True
        
        # Mark verification token as used
        verification.is_used = True
        db.session.commit()  # Commit both changes
        
        # If user is a merchant, update merchant verification status
        if user.role == UserRole.MERCHANT:
            merchant_profile = MerchantProfile.get_by_user_id(user.id)
            if merchant_profile:
                merchant_profile.verification_status = 'email_verified'
                merchant_profile.is_verified = True
        
        verification.use()
        db.session.commit()
        
        return {
            "message": "Email verified successfully",
            "user_id": user.id
        }, 200
    except Exception as e:
        current_app.logger.error(f"Email verification error: {str(e)}")
        return {"error": "Email verification failed"}, 500
    


def google_auth(token_data):
    """Authenticate with Google OAuth."""
    try:
        # Validate Google token
        google_info = validate_google_token(token_data['id_token'])
        if not google_info:
            return {"error": "Invalid Google token"}, 401
        
        # Get user info from Google token
        google_id = google_info['sub']
        email = google_info['email']
        first_name = google_info.get('given_name', '')
        last_name = google_info.get('family_name', '')
        
        # Check if user exists with this Google ID
        user = User.get_by_provider_id(AuthProvider.GOOGLE, google_id)
        
        # If not, check by email
        if not user:
            user = User.get_by_email(email)
            
            # If user exists with this email but different auth provider
            if user and user.auth_provider != AuthProvider.GOOGLE:
                return {"error": "Email already registered with different authentication method"}, 409
            
            # Create new user if not exists
            if not user:
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role=UserRole.USER,
                    auth_provider=AuthProvider.GOOGLE,
                    provider_user_id=google_id,
                    is_email_verified=True  # Email verified by Google
                )
                user.save()
        
        # Update user's Google ID if needed
        if user.provider_user_id != google_id:
            user.provider_user_id = google_id
            user.auth_provider = AuthProvider.GOOGLE
            db.session.commit()
        
        # Update last login timestamp
        user.update_last_login()
        
        # Generate tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token = RefreshToken.create_token(user.id, refresh_expires)
        
        return {
            "message": "Google authentication successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Google auth error: {str(e)}")
        return {"error": "Google authentication failed"}, 500

@cached(timeout=300, key_prefix='user')
def get_current_user(user_id):
    """Get current user information."""
    try:
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        user_data = {
            "id": str(user.id),  # Convert UUID to string
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role.value,
            "is_email_verified": user.is_email_verified,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat(),
        }
        
        # Add merchant profile data if applicable
        if user.role == UserRole.MERCHANT and user.merchant_profile:
            user_data["merchant"] = {
                "id": str(user.merchant_profile.id),  # Convert UUID to string
                "business_name": user.merchant_profile.business_name,
                "business_description": user.merchant_profile.business_description,
                "is_verified": user.merchant_profile.is_verified,
                "verification_status": user.merchant_profile.verification_status.value if user.merchant_profile.verification_status else None,
                "store_url": user.merchant_profile.store_url
            }
        
        return user_data, 200
    except Exception as e:
        current_app.logger.error(f"Get user error: {str(e)}")
        return {"error": "Failed to get user information"}, 500

def request_password_reset(email):
    """Request password reset for a user."""
    try:
        user = User.get_by_email(email)
        if not user:
            # Don't reveal if email exists for security
            return {"message": "If your email is registered, you will receive a password reset link"}, 200
        
        if user.auth_provider != AuthProvider.LOCAL:
            return {"error": "Please use your social login provider to access your account"}, 400
        
        # Create reset token
        expires_at = datetime.utcnow() + timedelta(hours=1)
        token = EmailVerification.create_token(user.id, expires_at)
        
        # Send password reset email and check result
        email_sent = send_password_reset_email(user, token)
        if not email_sent:
            current_app.logger.error(f"Failed to send password reset email to {email}")
            return {"error": "Failed to send password reset email. Please try again later."}, 500
        
        return {
            "message": "If your email is registered, you will receive a password reset link"
        }, 200
    except Exception as e:
        current_app.logger.error(f"Password reset request error: {str(e)}")
        return {"error": "Failed to process password reset request"}, 500
    
def reset_password(token, new_password):
    """Reset user password with token."""
    try:
        # Find verification token
        verification = EmailVerification.get_by_token(token)
        if not verification:
            return {"error": "Invalid reset token"}, 400
        
        if verification.expires_at < datetime.utcnow():
            return {"error": "Reset token expired"}, 400
        
        # Update user password
        user = User.get_by_id(verification.user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        user.set_password(new_password)
        verification.use()
        
        # Revoke all refresh tokens for security
        RefreshToken.revoke_all_for_user(user.id)
        
        db.session.commit()
        
        return {"message": "Password reset successfully"}, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password reset error: {str(e)}")
        return {"error": "Failed to reset password"}, 500