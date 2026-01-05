from datetime import datetime, timedelta, timezone
import cloudinary
import cloudinary.uploader
import uuid
from flask import current_app, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from authlib.integrations.flask_client import OAuth

from common.database import db
from auth.models import User, MerchantProfile, RefreshToken, EmailVerification, UserRole, AuthProvider, PhoneVerification
from auth.utils import validate_google_token, normalize_phone_number, validate_phone_number
from auth.twilio_service import send_otp_sms
from common.cache import cached, get_redis_client
from auth.email_utils import send_verification_email, send_password_reset_email

# Initialize OAuth
oauth = OAuth()

def register_user(data):
    """Register a new user."""
    try:
        # Check if user already exists
        if User.get_by_email(data['email']):
            db.session.rollback()  # Ensure clean state
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
        db.session.add(user)
        db.session.flush()  # Flush to get user.id without committing
        
        # Create email verification token (inline to avoid premature commit)
        expires_at = datetime.utcnow() + timedelta(days=1)
        token = str(uuid.uuid4())
        verification = EmailVerification(
            token=token,
            user_id=user.id,
            expires_at=expires_at
        )
        db.session.add(verification)
        
        # Commit everything together in a single transaction
        db.session.commit()
        
        # Send verification email (after successful commit)
        # Wrap in try-except to prevent email failures from blocking registration
        try:
            send_verification_email(user, token)
        except Exception as email_error:
            # Log the error but don't fail the registration
            current_app.logger.error(f"Failed to send verification email to {user.email}: {str(email_error)}")
        
        return {
            "message": "User registered successfully. Please check your email to verify your account.",
            "user_id": user.id
        }, 201
    except IntegrityError as e:
        db.session.rollback()
        error_str = str(e).lower()
        # Check if it's a duplicate email constraint violation
        if 'email' in error_str or 'unique constraint' in error_str or 'duplicate' in error_str:
            current_app.logger.warning(f"Duplicate email attempt during user registration: {data.get('email')}")
            return {"error": "Email already registered"}, 409
        current_app.logger.error(f"Database error during user registration: {str(e)}")
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
            db.session.rollback()  # Ensure clean state
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
        
        # Use session.add instead of save() to delay commit until everything is ready
        db.session.add(user)
        db.session.flush()  # Flush to get user.id without committing
        
        # Create merchant profile
        merchant = MerchantProfile(
            user_id=user.id,
            business_name=data['business_name'],
            business_description=data.get('business_description'),
            business_email=data['business_email'],
            business_phone=data.get('business_phone', data.get('phone')),
            business_address=data.get('business_address'),
            country_code=data['country_code'],
            state_province=data['state_province'],
            city=data['city'],
            postal_code=data['postal_code']
        )
        
        # Initialize required documents based on country
        merchant.update_required_documents()
        db.session.add(merchant)
        
        # Create email verification token (inline to avoid premature commit)
        expires_at = datetime.utcnow() + timedelta(days=1)
        token = str(uuid.uuid4())
        verification = EmailVerification(
            token=token,
            user_id=user.id,
            expires_at=expires_at
        )
        db.session.add(verification)
        
        # Commit everything together in a single transaction
        db.session.commit()
        
        # Send verification email (after successful commit)
        # Wrap in try-except to prevent email failures from blocking registration
        try:
            send_verification_email(user, token)
        except Exception as email_error:
            # Log the error but don't fail the registration
            current_app.logger.error(f"Failed to send verification email to {user.email}: {str(email_error)}")
        
        return {
            "message": "Merchant registered successfully. Please check your email to verify your account.",
            "user_id": user.id,
            "merchant_id": merchant.id
        }, 201
    except IntegrityError as e:
        db.session.rollback()
        error_str = str(e).lower()
        # Check if it's a duplicate email constraint violation
        if 'email' in error_str or 'unique constraint' in error_str or 'duplicate' in error_str:
            current_app.logger.warning(f"Duplicate email attempt during merchant registration: {data.get('business_email')}")
            return {"error": "Business email already registered"}, 409
        current_app.logger.error(f"Database error during merchant registration: {str(e)}")
        return {"error": "Database error occurred", "details": str(e)}, 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return {"error": "Registration failed", "details": str(e)}, 500
    

def login_user(data):
    """Login a user with email and password."""
    try:
        login_email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        is_business_login = 'business_email' in data and data['business_email'] is True
        
        current_app.logger.info(f"Login attempt - Email: {login_email}, Is Business Login: {is_business_login}")
        
        user_to_check = None
        merchant_profile = None
        
        if is_business_login:
            current_app.logger.info(f"Business login attempt for email: {login_email}")
            merchant_profile = MerchantProfile.query.filter_by(business_email=login_email).first()
            
            if merchant_profile:
                current_app.logger.info(f"Merchant profile found - ID: {merchant_profile.id}, User ID: {merchant_profile.user_id}")
                user_to_check = User.get_by_id(merchant_profile.user_id)
                if user_to_check:
                    current_app.logger.info(f"User found for merchant - User ID: {user_to_check.id}, Role: {user_to_check.role.value if user_to_check.role else 'None'}, Active: {user_to_check.is_active}, Email Verified: {user_to_check.is_email_verified}")
                else:
                    current_app.logger.warning(f"User not found for merchant profile ID: {merchant_profile.id}, User ID: {merchant_profile.user_id}")
            else:
                current_app.logger.warning(f"Merchant profile not found for business_email: {login_email}")
        else:
            current_app.logger.info(f"Regular login attempt for email: {login_email}")
            user_to_check = User.get_by_email(login_email)
            if user_to_check:
                current_app.logger.info(f"User found - User ID: {user_to_check.id}, Role: {user_to_check.role.value if user_to_check.role else 'None'}, Active: {user_to_check.is_active}, Email Verified: {user_to_check.is_email_verified}")
                # Prevent merchant login via regular login
                if user_to_check.role == UserRole.MERCHANT:
                    current_app.logger.warning(f"Merchant attempted to login via regular login - User ID: {user_to_check.id}")
                    return {"error": "Merchants must sign in through the merchant dashboard."}, 403
            else:
                current_app.logger.warning(f"User not found for email: {login_email}")
        
        if not user_to_check:
            current_app.logger.error(f"Login failed - User not found for email: {login_email}, Is Business Login: {is_business_login}")
            return {"error": "Invalid email or password"}, 401
        
        # Check password
        password_check_result = user_to_check.check_password(password)
        current_app.logger.info(f"Password check result for User ID {user_to_check.id}: {password_check_result}")
        
        if not password_check_result:
            current_app.logger.error(f"Login failed - Invalid password for User ID: {user_to_check.id}, Email: {login_email}")
            return {"error": "Invalid email or password"}, 401
        
        if not user_to_check.is_active:
            current_app.logger.warning(f"Login failed - Account disabled for User ID: {user_to_check.id}, Email: {login_email}")
            return {"error": "Account is disabled"}, 403
        
        # Email verification check
        if not user_to_check.is_email_verified:
            current_app.logger.warning(f"Login failed - Email not verified for User ID: {user_to_check.id}, Email: {login_email}")
            return {"error_code": "EMAIL_NOT_VERIFIED", "message": "Please verify your email address to log in.", "email": user_to_check.email}, 403
        
        current_app.logger.info(f"Login successful - User ID: {user_to_check.id}, Email: {login_email}, Role: {user_to_check.role.value if user_to_check.role else 'None'}")
        
        user_to_check.update_last_login()
        additional_claims = {"role": user_to_check.role.value}
        access_token = create_access_token(identity=str(user_to_check.id), additional_claims=additional_claims)
        refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token_str = RefreshToken.create_token(user_to_check.id, refresh_expires)
        login_message = "Merchant login successful" if is_business_login and user_to_check.role == UserRole.MERCHANT else "Login successful"
        return {
            "message": login_message,
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "user": {
                "id": user_to_check.id,
                "email": user_to_check.email,
                "first_name": user_to_check.first_name,
                "last_name": user_to_check.last_name,
                "role": user_to_check.role.value,
                "is_email_verified": user_to_check.is_email_verified
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Login error - Email: {data.get('email', 'N/A')}, Is Business Login: {data.get('business_email', False)}, Error: {str(e)}", exc_info=True)
        return {"error": "Login failed", "details": str(e) if current_app.debug else None}, 500
    
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
        # Find verification token - query directly to handle is_used check manually
        verification = EmailVerification.query.filter_by(token=token).first()
        
        if not verification:
            return {"error": "Invalid verification token"}, 400
        
        # If token is already used, check if user is verified
        if verification.is_used:
            user = User.get_by_id(verification.user_id)
            if user and user.is_email_verified:
                # Idempotency: Return success if already verified
                return {
                    "message": "Email already verified",
                    "user_id": user.id
                }, 200
            else:
                return {"error": "Verification token already used"}, 400
        
        if verification.expires_at < datetime.utcnow():
            return {"error": "Verification token expired"}, 400
        
        # Update user email verification status
        user = User.get_by_id(verification.user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        user.is_email_verified = True
        
        # Mark verification token as used
        verification.is_used = True
        
        # If user is a merchant, update merchant verification status
        if user.role == UserRole.MERCHANT:
            merchant_profile = MerchantProfile.get_by_user_id(user.id)
            if merchant_profile:
                # Only update if not already verified to avoid overwriting other statuses
                if merchant_profile.verification_status != 'approved': 
                    merchant_profile.verification_status = 'email_verified'
                    merchant_profile.is_verified = True
        
        db.session.commit()
        
        return {
            "message": "Email verified successfully",
            "user_id": user.id
        }, 200
    except Exception as e:
        db.session.rollback()
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
        # Prevent merchant login via Google on regular login
        if user and user.role == UserRole.MERCHANT:
            return {"error": "Merchants must sign in through the merchant dashboard."}, 403
        # Update user's Google ID if needed
        if user.provider_user_id != google_id:
            user.provider_user_id = google_id
            user.auth_provider = AuthProvider.GOOGLE
            db.session.commit()
        # Update last login timestamp
        user.update_last_login()
        # Generate tokens
        access_token = create_access_token(identity=str(user.id))
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
            "profile_img": user.profile_img,
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
    
def resend_verification_email_controller(email_address):
    """Handles resending of verification email with rate limiting."""
    try:
        user = User.get_by_email(email_address)
        if not user:
            return {"message": "If your email is registered and not verified, a new verification link has been sent."}, 200
        if user.role == UserRole.SUPER_ADMIN:
            return {"message": "This action is not applicable for super administrators."}, 200
        if user.is_email_verified:
            return {"message": "Your email address is already verified."}, 200
        redis_client = get_redis_client(current_app)
        if not redis_client:
            current_app.logger.error("Redis client not available for rate limiting resend verification email.")
        attempts_key = f"rate_limit:resend_verify_email_attempts:{email_address}"
        last_attempt_ts_key = f"rate_limit:resend_verify_email_last_ts:{email_address}"
        last_attempt_date_key = f"rate_limit:resend_verify_email_last_date:{email_address}"
        pipe = redis_client.pipeline()
        pipe.get(attempts_key)
        pipe.get(last_attempt_ts_key)
        pipe.get(last_attempt_date_key)
        attempts_raw, last_attempt_ts_raw, last_attempt_date_raw = pipe.execute()
        attempts = int(attempts_raw) if attempts_raw else 0
        last_attempt_ts = float(last_attempt_ts_raw) if last_attempt_ts_raw else 0
        last_attempt_date_str = last_attempt_date_raw.decode('utf-8') if last_attempt_date_raw else None
        current_time_utc = datetime.utcnow()
        current_timestamp = current_time_utc.timestamp()
        current_date_str = current_time_utc.date().isoformat()
        if last_attempt_date_str != current_date_str:
            attempts = 0
            pipe = redis_client.pipeline()
            pipe.set(attempts_key, 0)
            pipe.set(last_attempt_date_key, current_date_str)
            pipe.expire(attempts_key, 86400 * 2)
            pipe.expire(last_attempt_date_key, 86400 * 2)
            pipe.expire(last_attempt_ts_key, 86400 * 2)
            pipe.execute()
        rate_limit_tiers = [ (0, 0), (1, 30), (2, 60), (3, 60) ]
        max_attempts_per_day = 4
        if attempts >= max_attempts_per_day:
            tomorrow_utc = current_time_utc.date() + timedelta(days=1)
            next_day_start_utc = datetime.combine(tomorrow_utc, datetime.min.time(), tzinfo=timezone.utc)
            retry_after = (next_day_start_utc - current_time_utc).total_seconds()
            return {"error_code": "RATE_LIMIT_EXCEEDED", "message": "You have reached the maximum number of resend attempts for today.", "retry_after": int(retry_after)}, 429
        current_tier_delay = rate_limit_tiers[attempts][1] if attempts < len(rate_limit_tiers) else rate_limit_tiers[-1][1]
        if last_attempt_ts > 0 and (current_timestamp - last_attempt_ts < current_tier_delay):
            retry_after_seconds = current_tier_delay - (current_timestamp - last_attempt_ts)
            return {"error_code": "RATE_LIMIT_APPLIED", "message": "Please wait before trying again.", "retry_after": int(retry_after_seconds) + 1}, 429
        EmailVerification.query.filter_by(user_id=user.id, is_used=False).update({"is_used": True})
        new_expires_at = datetime.utcnow() + timedelta(days=1)
        new_token = EmailVerification.create_token(user.id, new_expires_at)
        email_sent_successfully = send_verification_email(user, new_token)
        if email_sent_successfully:
            pipe = redis_client.pipeline()
            pipe.set(attempts_key, attempts + 1)
            pipe.set(last_attempt_ts_key, current_timestamp)
            pipe.set(last_attempt_date_key, current_date_str)
            pipe.expire(attempts_key, 86400 * 2)
            pipe.expire(last_attempt_date_key, 86400 * 2)
            pipe.expire(last_attempt_ts_key, 86400 * 2)
            pipe.execute()
            return {"message": "A new verification link has been sent to your email address."}, 200
        else:
            current_app.logger.error(f"Email sending itself failed for {email_address} during resend.")
            return {"error_code": "EMAIL_SEND_FAILED", "message": "Failed to send verification email. Please try again later."}, 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Resend verification email controller error for {email_address}: {str(e)}")
        return {"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}, 500


def get_user_profile(user_id):
    """Get a user's profile information by their ID."""
    try:
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        # Format date_of_birth for response (DD-MM-YYYY)
        date_of_birth_str = None
        if user.date_of_birth:
            date_of_birth_str = user.date_of_birth.strftime('%d-%m-%Y')
        
        return {
            "profile": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "date_of_birth": date_of_birth_str,
                "gender": user.gender,
                "profile_img": user.profile_img,
                "is_email_verified": user.is_email_verified,
                "is_phone_verified": user.is_phone_verified,
                "role": user.role.value,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "auth_provider": user.auth_provider.value if user.auth_provider else 'local'
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Error in get_user_profile controller for user {user_id}: {e}", exc_info=True)
        return {"error": "Could not retrieve profile"}, 500

def update_user_profile(user_id, data):
    """Update a user's profile information. Email and phone cannot be updated through this endpoint."""
    try:
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Fields that are NOT allowed to be updated
        restricted_fields = ['email', 'phone', 'id', 'password_hash', 'role', 'is_active', 
                            'is_email_verified', 'is_phone_verified', 'auth_provider', 
                            'provider_user_id', 'created_at', 'updated_at']
        
        # Check if user is trying to update restricted fields
        restricted_attempted = [field for field in data.keys() if field in restricted_fields]
        if restricted_attempted:
            return {"error": f"Cannot update restricted fields: {', '.join(restricted_attempted)}"}, 400
        
        # Allowed fields to update
        allowed_fields = ['first_name', 'last_name', 'date_of_birth', 'gender']
        
        # Update allowed fields
        for field, value in data.items():
            if field in allowed_fields and hasattr(user, field):
                if field == 'date_of_birth' and value:
                    # Convert DD-MM-YYYY string to Date object
                    try:
                        date_obj = datetime.strptime(value, '%d-%m-%Y').date()
                        setattr(user, field, date_obj)
                    except ValueError:
                        return {"error": "Invalid date format. Use DD-MM-YYYY format"}, 400
                elif field == 'date_of_birth' and value is None:
                    # Allow clearing the date
                    setattr(user, field, None)
                else:
                    setattr(user, field, value)
        
        db.session.commit()
        redis = get_redis_client()
        if redis:
            redis.delete(f"user_profile:{user_id}")
            redis.delete(f"user:{user_id}")
        
        # Format date_of_birth for response (DD-MM-YYYY)
        date_of_birth_str = None
        if user.date_of_birth:
            date_of_birth_str = user.date_of_birth.strftime('%d-%m-%Y')
        
        return {
            "message": "Profile updated successfully",
            "profile": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_of_birth": date_of_birth_str,
                "gender": user.gender
            }
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user profile for {user_id}: {e}", exc_info=True)
        return {"error": "Profile update failed"}, 500

def upload_profile_image(user_id):
    """Handles profile image upload for a user directly."""
    try:
        if 'profile_image' not in request.files:
            return {"error": "No file part in the request"}, 400
        file = request.files['profile_image']
        if file.filename == '':
            return {"error": "No file selected for uploading"}, 400
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Delete old profile image from S3 if it exists
        if user.profile_img:
            try:
                from services.s3_service import get_s3_service
                s3_service = get_s3_service()
                s3_service.delete_profile_image(user.profile_img)
            except Exception as e:
                current_app.logger.warning(f"Failed to delete old profile image from S3: {str(e)}")
        
        # Upload to S3
        from services.s3_service import get_s3_service
        s3_service = get_s3_service()
        upload_result = s3_service.upload_profile_image(file, user_id)
        
        secure_url = upload_result.get('url')
        if not secure_url:
            return {"error": "Failed to get URL from S3 upload result"}, 500
        
        user.profile_img = secure_url
        db.session.commit()
        redis_client = get_redis_client()
        if redis_client:
            redis_client.delete(f"user_profile:{user_id}")
            redis_client.delete(f"user_profile:{user.id}") # Duplicated cache key, fixing
        return {
            "message": "Profile image uploaded successfully",
            "profile_img_url": user.profile_img
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile image upload error for user {user_id}: {e}", exc_info=True)
        return {"error": "An internal error occurred during file upload"}, 500
    


def change_password(user_id, old_password, new_password):
    """
    Change a logged-in user's password.
    Requires the old password for verification.
    """
    try:
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404

        if user.auth_provider != AuthProvider.LOCAL:
            return {"error": "Password change is not available for social login accounts."}, 400

        if not user.check_password(old_password):
            return {"error": "Incorrect current password"}, 401
        
        # Password validation (you might want to add more robust validation here)
        if len(new_password) < 8:
            return {"error": "New password must be at least 8 characters long"}, 400
        if old_password == new_password:
            return {"error": "New password cannot be the same as the old password"}, 400

        user.set_password(new_password)
        
        # For enhanced security, revoke all existing refresh tokens for the user
        RefreshToken.revoke_all_for_user(user.id)
        
        db.session.commit()
        
        return {"message": "Password changed successfully"}, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing password for user {user_id}: {e}", exc_info=True)
        return {"error": "An internal error occurred while changing the password"}, 500


def send_phone_otp(phone_number):
    """
    Send OTP to phone number for sign-up or login.
    Only for regular users, not merchants.
    """
    try:
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone_number)
        if not normalized_phone:
            return {"error": "Invalid phone number format. Please use E.164 format (e.g., +1234567890)"}, 400
        
        # Check if user exists (for login flow)
        existing_user = User.get_by_phone(normalized_phone)
        
        # If user exists, check if they are a merchant (merchants cannot use phone login)
        if existing_user and existing_user.role == UserRole.MERCHANT:
            return {"error": "Merchants cannot use phone number login"}, 403
        
        # Generate OTP
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        if existing_user:
            # Login flow - user exists
            otp = PhoneVerification.create_otp(existing_user.id, normalized_phone, expires_at)
        else:
            # Sign-up flow - user doesn't exist
            otp = PhoneVerification.create_otp_for_signup(normalized_phone, expires_at)
        
        # Send OTP via Twilio
        success, message = send_otp_sms(normalized_phone, otp)
        
        if not success:
            return {"error": message}, 500
        
        return {
            "message": "OTP sent successfully",
            "expires_in": 600  # 10 minutes in seconds
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error sending phone OTP: {str(e)}")
        return {"error": "Failed to send OTP"}, 500


def verify_phone_otp_signup(phone_number, otp, first_name, last_name):
    """
    Verify OTP and create new user account.
    Only for regular users, not merchants.
    """
    try:
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone_number)
        if not normalized_phone:
            return {"error": "Invalid phone number format"}, 400
        
        # Validate name fields
        if not first_name or not last_name:
            return {"error": "First name and last name are required"}, 400
        
        # Check if phone already registered
        existing_user = User.get_by_phone(normalized_phone)
        if existing_user:
            return {"error": "Phone number already registered"}, 409
        
        # Verify OTP
        verification = PhoneVerification.verify_otp_by_phone(normalized_phone, otp)
        if not verification:
            return {"error": "Invalid or expired OTP"}, 400
        
        # Create new user
        # Generate temporary email for phone-only users (email field is required in DB)
        # User can update email later
        temp_email = f"phone_{normalized_phone.replace('+', '')}@temp.aoin.com"
        
        user = User(
            phone=normalized_phone,
            first_name=first_name,
            last_name=last_name,
            email=temp_email,  # Temporary email, user can update later
            role=UserRole.USER,  # Only regular users, not merchants
            auth_provider=AuthProvider.PHONE.value,  # Use lowercase 'phone' string to match database enum
            is_phone_verified=True,
            is_email_verified=False,
            password_hash=None  # No password for phone auth
        )
        user.save()
        
        # Update verification record with user_id
        verification.user_id = user.id
        db.session.commit()
        
        # Generate tokens
        additional_claims = {"role": user.role.value}
        access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token_str = RefreshToken.create_token(user.id, refresh_expires)
        
        return {
            "message": "Account created successfully",
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "user": {
                "id": user.id,
                "phone": user.phone,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "is_phone_verified": user.is_phone_verified
            }
        }, 201
        
    except IntegrityError:
        db.session.rollback()
        return {"error": "Phone number already registered"}, 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in phone sign-up: {str(e)}")
        return {"error": "Failed to create account"}, 500


def verify_phone_otp_login(phone_number, otp):
    """
    Verify OTP and login existing user.
    Only for regular users, not merchants.
    """
    try:
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone_number)
        if not normalized_phone:
            return {"error": "Invalid phone number format"}, 400
        
        # Find user
        user = User.get_by_phone(normalized_phone)
        if not user:
            return {"error": "Phone number not registered"}, 404
        
        # Check if user is merchant (merchants cannot use phone login)
        if user.role == UserRole.MERCHANT:
            return {"error": "Merchants cannot use phone number login"}, 403
        
        # Check if user is active
        if not user.is_active:
            return {"error": "Account is disabled"}, 403
        
        # Verify OTP
        verification = PhoneVerification.verify_otp_by_phone(normalized_phone, otp)
        if not verification:
            return {"error": "Invalid or expired OTP"}, 400
        
        # Update user's phone verification status and last login
        user.is_phone_verified = True
        user.update_last_login()
        
        # Generate tokens
        additional_claims = {"role": user.role.value}
        access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        refresh_expires = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token_str = RefreshToken.create_token(user.id, refresh_expires)
        
        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "user": {
                "id": user.id,
                "phone": user.phone,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "is_phone_verified": user.is_phone_verified
            }
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error in phone login: {str(e)}")
        return {"error": "Login failed"}, 500
