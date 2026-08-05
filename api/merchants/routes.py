from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from marshmallow import Schema, fields, validate, ValidationError
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging

from auth.utils import merchant_role_required
from common.decorators import rate_limit, cache_response
from auth.models import User, MerchantProfile
from models.user_merchant_follow import UserMerchantFollow
from auth.models.merchant_document import VerificationStatus, DocumentType, MerchantDocument
from auth.models.country_config import CountryConfig, CountryCode
from models.merchant_intro_video import MerchantIntroVideo
from controllers.merchant.merchant_intro_video_controller import (
    MerchantIntroVideoController,
    IntroVideoError,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_VIDEO_SIZE,
    MAX_VIDEO_DURATION_SECONDS,
    MAX_TITLE_CHARS,
    MAX_CAPTION_CHARS,
)
from common.database import db
from common.text_sanitize import sanitize_plain_text, sanitize_url, validate_text_length
from http import HTTPStatus

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Schema definitions
class CreateMerchantProfileSchema(Schema):
    business_name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    business_description = fields.Str(required=True)
    business_email = fields.Email(required=True)
    business_phone = fields.Str(required=True)
    business_address = fields.Str(required=True)
    country_code = fields.Str(required=True, validate=validate.OneOf([code.value for code in CountryCode]))
    
    # Common fields
    bank_account_number = fields.Str(validate=validate.Length(min=9, max=18))
    bank_name = fields.Str(validate=validate.Length(max=100))
    bank_branch = fields.Str(validate=validate.Length(max=100))
    bank_iban = fields.Str(validate=validate.Length(max=34))

    # India-specific fields
    gstin = fields.Str(validate=validate.Length(max=15))
    pan_number = fields.Str(validate=validate.Length(max=10))
    bank_ifsc_code = fields.Str(validate=validate.Length(min=11, max=11))

    # Global fields
    tax_id = fields.Str(validate=validate.Length(max=50))
    vat_number = fields.Str(validate=validate.Length(max=50))
    sales_tax_number = fields.Str(validate=validate.Length(max=50))
    bank_swift_code = fields.Str(validate=validate.Length(max=11))
    bank_routing_number = fields.Str(validate=validate.Length(max=20))

class UpdateProfileSchema(Schema):
    business_name = fields.Str(validate=validate.Length(min=2, max=200))
    business_description = fields.Str()
    # REMOVED: business_email and business_phone (cannot be updated directly)
    business_address = fields.Str()
    username = fields.Str(validate=validate.Regexp(r'^[a-zA-Z0-9_]{3,30}$', error="Username must be 3-30 characters, alphanumeric and underscores only"), allow_none=True)
    profile_img = fields.Str(allow_none=True)  # Profile image URL

    # Public bio. Length/format are enforced after sanitisation (see
    # _apply_bio_updates) so the limit is measured against the stored value,
    # not the raw input.
    bio = fields.Str(allow_none=True)
    bio_link = fields.Str(allow_none=True)
    bio_link_label = fields.Str(allow_none=True)

    # Country and Region Information
    country_code = fields.Str(validate=validate.OneOf([code.value for code in CountryCode]))
    state_province = fields.Str()
    city = fields.Str()
    postal_code = fields.Str()
    
    # Common fields
    bank_account_number = fields.Str(validate=validate.Length(min=9, max=18))
    bank_name = fields.Str(validate=validate.Length(max=100))
    bank_branch = fields.Str(validate=validate.Length(max=100))
    bank_iban = fields.Str(validate=validate.Length(max=34))
    
    # India-specific fields
    gstin = fields.Str(validate=validate.Length(max=15))
    pan_number = fields.Str(validate=validate.Length(max=10))
    bank_ifsc_code = fields.Str(validate=validate.Length(max=11))
    
    # Global fields
    tax_id = fields.Str(validate=validate.Length(max=50))
    vat_number = fields.Str(validate=validate.Length(max=50))
    sales_tax_number = fields.Str(validate=validate.Length(max=50))
    bank_swift_code = fields.Str(validate=validate.Length(max=11))
    bank_routing_number = fields.Str(validate=validate.Length(max=20))

    def validate(self, data, **kwargs):
        """Custom validation based on country code."""
        errors = {}
        country_code = data.get('country_code')

        if country_code == CountryCode.INDIA.value:
            # Validate Indian-specific fields
            if data.get('bank_ifsc_code') and len(data['bank_ifsc_code']) != 11:
                errors['bank_ifsc_code'] = ['Length must be between 11 and 11.']
            if data.get('gstin') and len(data['gstin']) > 15:
                errors['gstin'] = ['Length must be between 0 and 15.']
            if data.get('pan_number') and len(data['pan_number']) > 10:
                errors['pan_number'] = ['Length must be between 0 and 10.']
        else:  # GLOBAL
            # Validate Global-specific fields
            if data.get('bank_swift_code') and len(data['bank_swift_code']) > 11:
                errors['bank_swift_code'] = ['Length must be between 0 and 11.']
            if data.get('tax_id') and len(data['tax_id']) > 50:
                errors['tax_id'] = ['Length must be between 0 and 50.']
            if data.get('vat_number') and len(data['vat_number']) > 50:
                errors['vat_number'] = ['Length must be between 0 and 50.']
            if data.get('sales_tax_number') and len(data['sales_tax_number']) > 50:
                errors['sales_tax_number'] = ['Length must be between 0 and 50.']

        if errors:
            raise ValidationError(errors)

        return data

# Bio limits. 250 rather than Instagram's 150: merchants write business copy,
# and the long-form text already has a home in business_description.
BIO_MAX_CHARS = 250
BIO_MAX_LINES = 5
BIO_LINK_MAX_CHARS = 512
BIO_LINK_LABEL_MAX_CHARS = 60


def _apply_bio_updates(merchant_profile, data):
    """
    Sanitise and apply bio fields, popping them off `data` so the generic
    field loop does not write the raw values.

    Returns a dict of field -> [errors]; empty when everything applied.
    An explicit null (or a value that sanitises to empty) clears the field;
    an absent key leaves it untouched.
    """
    errors = {}
    bio_changed = False

    if 'bio' in data:
        bio = sanitize_plain_text(data.pop('bio'), allow_newlines=True)
        bio_errors = validate_text_length(bio, 'Bio', BIO_MAX_CHARS, max_lines=BIO_MAX_LINES)
        if bio_errors:
            errors['bio'] = bio_errors
        else:
            merchant_profile.bio = bio
            bio_changed = True

    if 'bio_link' in data:
        link, link_error = sanitize_url(data.pop('bio_link'), max_length=BIO_LINK_MAX_CHARS)
        if link_error:
            errors['bio_link'] = [link_error]
        else:
            merchant_profile.bio_link = link
            bio_changed = True

    if 'bio_link_label' in data:
        label = sanitize_plain_text(data.pop('bio_link_label'), allow_newlines=False)
        label_errors = validate_text_length(label, 'Link label', BIO_LINK_LABEL_MAX_CHARS)
        if label_errors:
            errors['bio_link_label'] = label_errors
        else:
            merchant_profile.bio_link_label = label
            bio_changed = True

    # A label with no link is dead weight — drop it rather than storing an
    # orphan the UI would have nothing to attach to.
    if not merchant_profile.bio_link:
        merchant_profile.bio_link_label = None

    if bio_changed and not errors:
        merchant_profile.bio_updated_at = datetime.utcnow()

    return errors


def serialize_bio(merchant_profile):
    """Bio fields as returned by both the owner and public profile endpoints."""
    return {
        "bio": merchant_profile.bio,
        "bio_link": merchant_profile.bio_link,
        "bio_link_label": merchant_profile.bio_link_label,
    }


def serialize_intro_video(video, owner_view=False):
    """None-safe wrapper — every endpoint returns null rather than omitting."""
    return video.serialize(owner_view=owner_view) if video else None


def intro_video_limits():
    """Server limits, published so the UI validates against the same numbers."""
    return {
        "max_size_bytes": MAX_VIDEO_SIZE,
        "max_size_mb": MAX_VIDEO_SIZE // (1024 * 1024),
        "max_duration_seconds": MAX_VIDEO_DURATION_SECONDS,
        "allowed_extensions": sorted(ALLOWED_VIDEO_EXTENSIONS),
        "max_title_chars": MAX_TITLE_CHARS,
        "max_caption_chars": MAX_CAPTION_CHARS,
    }


# Create merchants blueprint
merchants_bp = Blueprint('merchants', __name__)

@merchants_bp.route('/profile', methods=['POST'])
@jwt_required()
@merchant_role_required
def create_profile():
    """
    Create initial merchant profile.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - business_name
            - business_description
            - business_email
            - business_phone
            - business_address
            - country_code
          properties:
            business_name:
              type: string
              minLength: 2
              maxLength: 200
            business_description:
              type: string
            business_email:
              type: string
              format: email
            business_phone:
              type: string
            business_address:
              type: string
            country_code:
              type: string
              enum: [IN, US, GB, CA, AU]
            # Common fields
            bank_account_number:
              type: string
              minLength: 9
              maxLength: 18
            bank_name:
              type: string
              maxLength: 100
            bank_branch:
              type: string
              maxLength: 100
            bank_iban:
              type: string
              maxLength: 34
            # India-specific fields
            gstin:
              type: string
              maxLength: 15
            pan_number:
              type: string
              maxLength: 10
            bank_ifsc_code:
              type: string
              minLength: 11
              maxLength: 11
            # Global fields
            tax_id:
              type: string
              maxLength: 50
            vat_number:
              type: string
              maxLength: 50
            sales_tax_number:
              type: string
              maxLength: 50
            bank_swift_code:
              type: string
              maxLength: 11
            bank_routing_number:
              type: string
              maxLength: 20
    responses:
      201:
        description: Merchant profile created successfully
        schema:
          type: object
          properties:
            message:
              type: string
            profile:
              type: object
              properties:
                business_name:
                  type: string
                business_email:
                  type: string
                country_code:
                  type: string
                verification_status:
                  type: string
      400:
        description: Validation error or profile already exists
      500:
        description: Internal server error
    """
    try:
        # Validate request data
        schema = CreateMerchantProfileSchema()
        data = schema.load(request.json)
        
        merchant_id = get_jwt_identity()
        
        # Check if profile already exists
        existing_profile = MerchantProfile.get_by_user_id(merchant_id)
        if existing_profile:
            return jsonify({"error": "Merchant profile already exists"}), 400
        
        # Validate country-specific fields (relaxed requirements)
        country_code = data.get('country_code')
        if country_code == CountryCode.INDIA.value:
            missing = []
            if not data.get('pan_number'):
                missing.append('pan_number')
            if not data.get('bank_account_number'):
                missing.append('bank_account_number')
            if not data.get('bank_name'):
                missing.append('bank_name')
            if not data.get('bank_ifsc_code'):
                missing.append('bank_ifsc_code')
            if missing:
                return jsonify({
                    "error": "Validation error",
                    "details": f"Missing required fields: {', '.join(missing)}"
                }), 400
        else:  # Non-India: require core bank details only
            missing = []
            if not data.get('bank_account_number'):
                missing.append('bank_account_number')
            if not data.get('bank_name'):
                missing.append('bank_name')
            if missing:
                return jsonify({
                    "error": "Validation error",
                    "details": f"Missing required fields: {', '.join(missing)}"
                }), 400
        
        # Create new merchant profile
        merchant_profile = MerchantProfile(
            user_id=merchant_id,
            business_name=data['business_name'],
            business_description=data['business_description'],
            business_email=data['business_email'],
            business_phone=data['business_phone'],
            business_address=data['business_address'],
            country_code=country_code,
            # India-specific fields
            gstin=data.get('gstin'),
            pan_number=data.get('pan_number'),
            bank_ifsc_code=data.get('bank_ifsc_code'),
            # Global fields
            tax_id=data.get('tax_id'),
            vat_number=data.get('vat_number'),
            sales_tax_number=data.get('sales_tax_number'),
            bank_swift_code=data.get('bank_swift_code'),
            bank_routing_number=data.get('bank_routing_number'),
            # Common fields
            bank_account_number=data.get('bank_account_number'),
            bank_name=data.get('bank_name'),
            bank_branch=data.get('bank_branch'),
            bank_iban=data.get('bank_iban'),
            verification_status=VerificationStatus.PENDING,
            is_verified=False
        )
        
        merchant_profile.save()
        
        return jsonify({
            "message": "Merchant profile created successfully",
            "profile": {
                "business_name": merchant_profile.business_name,
                "business_email": merchant_profile.business_email,
                "country_code": merchant_profile.country_code,
                "verification_status": merchant_profile.verification_status.value
            }
        }), 201
        
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@merchants_bp.route('/profile', methods=['GET'])
@jwt_required()
@merchant_role_required
def get_profile():
    """
    Get merchant profile.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Merchant profile retrieved successfully
        schema:
          type: object
          properties:
            profile:
              type: object
              properties:
                business_name:
                  type: string
                business_description:
                  type: string
                business_email:
                  type: string
                business_phone:
                  type: string
                business_address:
                  type: string
                country_code:
                  type: string
                state_province:
                  type: string
                city:
                  type: string
                postal_code:
                  type: string
                gstin:
                  type: string
                pan_number:
                  type: string
                tax_id:
                  type: string
                vat_number:
                  type: string
                sales_tax_number:
                  type: string
                bank_account_number:
                  type: string
                bank_name:
                  type: string
                bank_branch:
                  type: string
                bank_ifsc_code:
                  type: string
                bank_swift_code:
                  type: string
                bank_routing_number:
                  type: string
                bank_iban:
                  type: string
                is_verified:
                  type: boolean
                verification_status:
                  type: string
                verification_submitted_at:
                  type: string
                  format: date-time
                verification_completed_at:
                  type: string
                  format: date-time
                verification_notes:
                  type: string
                required_documents:
                  type: array
                  items:
                    type: string
                submitted_documents:
                  type: array
                  items:
                    type: string
      404:
        description: Merchant profile not found
    """
    try:
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            return jsonify({"error": "Merchant profile not found"}), 404
        
        return jsonify({
            "profile": {
                "business_name": merchant_profile.business_name,
                "business_description": merchant_profile.business_description,
                "business_email": merchant_profile.business_email,
                "business_phone": merchant_profile.business_phone,
                "business_address": merchant_profile.business_address,
                "country_code": merchant_profile.country_code,
                "state_province": merchant_profile.state_province,
                "city": merchant_profile.city,
                "postal_code": merchant_profile.postal_code,
                "gstin": merchant_profile.gstin,
                "pan_number": merchant_profile.pan_number,
                "tax_id": merchant_profile.tax_id,
                "vat_number": merchant_profile.vat_number,
                "sales_tax_number": merchant_profile.sales_tax_number,
                "bank_account_number": merchant_profile.bank_account_number,
                "bank_name": merchant_profile.bank_name,
                "bank_branch": merchant_profile.bank_branch,
                "bank_ifsc_code": merchant_profile.bank_ifsc_code,
                "bank_swift_code": merchant_profile.bank_swift_code,
                "bank_routing_number": merchant_profile.bank_routing_number,
                "bank_iban": merchant_profile.bank_iban,
                "username": merchant_profile.username,
                "profile_img": merchant_profile.profile_img,
                **serialize_bio(merchant_profile),
                "intro_video": serialize_intro_video(
                    MerchantIntroVideo.get_active_for_merchant(merchant_profile.id), owner_view=True
                ),
                "is_verified": merchant_profile.is_verified,
                "verification_status": merchant_profile.verification_status.value,
                "verification_submitted_at": merchant_profile.verification_submitted_at.isoformat() if merchant_profile.verification_submitted_at else None,
                "verification_completed_at": merchant_profile.verification_completed_at.isoformat() if merchant_profile.verification_completed_at else None,
                "verification_notes": merchant_profile.verification_notes,
                "required_documents": merchant_profile.required_documents,
                "submitted_documents": merchant_profile.submitted_documents
            },
            "limits": {
                "bio_max_chars": BIO_MAX_CHARS,
                "bio_max_lines": BIO_MAX_LINES,
                "bio_link_label_max_chars": BIO_LINK_LABEL_MAX_CHARS,
                "intro_video": intro_video_limits(),
            }
        }), 200
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error fetching merchant profile: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to fetch profile: {str(e)}"}), 500

@merchants_bp.route('/<int:merchant_id>/public-profile', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_public_profile(merchant_id):
    """
    Get public merchant profile information (for users to view).
    ---
    tags:
      - Merchant
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID
      - in: header
        name: Authorization
        type: string
        required: false
        description: Optional JWT token (Bearer token)
    responses:
      200:
        description: Merchant profile retrieved successfully
        schema:
          type: object
          properties:
            merchant_id:
              type: integer
            business_name:
              type: string
            business_description:
              type: string
            business_email:
              type: string
            business_phone:
              type: string
            business_address:
              type: string
            location:
              type: object
              properties:
                country_code:
                  type: string
                state_province:
                  type: string
                city:
                  type: string
                postal_code:
                  type: string
            is_verified:
              type: boolean
            verification_status:
              type: string
            gstin:
              type: string
              nullable: true
            is_following:
              type: boolean
              description: Whether the authenticated user is following this merchant (false if not authenticated)
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
    try:
        merchant_profile = MerchantProfile.get_by_id(merchant_id)

        if not merchant_profile:
            return jsonify({"error": "Merchant not found"}), HTTPStatus.NOT_FOUND

        # Single source of truth for "may shoppers see this merchant at all":
        # covers soft close, elapsed deletion grace period and suspension.
        if not merchant_profile.is_publicly_visible():
            return jsonify({"error": "Merchant not found"}), HTTPStatus.NOT_FOUND

        # Check if user is authenticated and following the merchant
        is_following = False
        try:
            # Try to verify JWT token (this won't fail if token is missing, just returns False)
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
            
            if current_user_id:
                is_following = UserMerchantFollow.is_following(current_user_id, merchant_id)
        except Exception:
            # If token is invalid or any error occurs, default to False
            is_following = False
        
        return jsonify({
            "merchant_id": merchant_profile.id,
            "business_name": merchant_profile.business_name,
            "business_description": merchant_profile.business_description,
            "business_email": merchant_profile.business_email,
            "business_phone": merchant_profile.business_phone,
            "business_address": merchant_profile.business_address,
            "username": merchant_profile.username,
            "profile_img": merchant_profile.profile_img,
            **serialize_bio(merchant_profile),
            # Held to a stricter bar than the bio — verified merchants only.
            "intro_video": serialize_intro_video(
                MerchantIntroVideoController.get_public(merchant_profile)
            ),
            "location": {
                "country_code": merchant_profile.country_code,
                "state_province": merchant_profile.state_province,
                "city": merchant_profile.city,
                "postal_code": merchant_profile.postal_code
            },
            "is_verified": merchant_profile.is_verified,
            "verification_status": merchant_profile.verification_status.value if merchant_profile.verification_status else "pending",
            "gstin": merchant_profile.gstin,
            "tax_id": merchant_profile.tax_id,
            "is_following": is_following
        }), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"Error getting public merchant profile: {str(e)}")
        return jsonify({"error": "Failed to retrieve merchant profile"}), HTTPStatus.INTERNAL_SERVER_ERROR

@merchants_bp.route('/username/check', methods=['GET'])
@cross_origin()
def check_username_availability():
    """
    Check if username is available.
    ---
    tags:
      - Merchant
    parameters:
      - in: query
        name: username
        type: string
        required: true
        description: Username to check
    responses:
      200:
        description: Username availability status
        schema:
          type: object
          properties:
            available:
              type: boolean
            username:
              type: string
    """
    username = request.args.get('username', '').strip().lower()
    
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    # Validate format
    import re
    if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
        return jsonify({
            "available": False,
            "error": "Invalid username format. Username must be 3-30 characters, alphanumeric and underscores only"
        }), 400
    
    is_available = MerchantProfile.is_username_available(username)
    
    return jsonify({
        "available": is_available,
        "username": username
    }), 200

@merchants_bp.route('/profile', methods=['PUT'])
@jwt_required()
@merchant_role_required
def update_profile():
    """
    Update merchant profile.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            business_name:
              type: string
              minLength: 2
              maxLength: 200
            business_description:
              type: string
            business_email:
              type: string
              format: email
            business_phone:
              type: string
            business_address:
              type: string
            country_code:
              type: string
              enum: [IN, US, GB, CA, AU]
            state_province:
              type: string
            city:
              type: string
            postal_code:
              type: string
            # Common fields
            bank_account_number:
              type: string
              minLength: 9
              maxLength: 18
            bank_name:
              type: string
              maxLength: 100
            bank_branch:
              type: string
              maxLength: 100
            bank_iban:
              type: string
              maxLength: 34
            # India-specific fields
            gstin:
              type: string
              maxLength: 15
            pan_number:
              type: string
              maxLength: 10
            bank_ifsc_code:
              type: string
              maxLength: 11
            # Global fields
            tax_id:
              type: string
              maxLength: 50
            vat_number:
              type: string
              maxLength: 50
            sales_tax_number:
              type: string
              maxLength: 50
            bank_swift_code:
              type: string
              maxLength: 11
            bank_routing_number:
              type: string
              maxLength: 20
    responses:
      200:
        description: Profile updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
            profile:
              type: object
              properties:
                business_name:
                  type: string
                business_email:
                  type: string
                country_code:
                  type: string
                verification_status:
                  type: string
      400:
        description: Validation error
      404:
        description: Merchant profile not found
      500:
        description: Internal server error
    """
    try:
        logger.debug(f"Received profile update request: {request.json}")
        
        # Validate request data
        schema = UpdateProfileSchema()
        try:
            data = schema.load(request.json)
            logger.debug(f"Validated data: {data}")
        except ValidationError as e:
            logger.error(f"Schema validation error: {e.messages}")
            return jsonify({"error": "Validation error", "details": e.messages}), 400
        
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            logger.error(f"Merchant profile not found for user_id: {merchant_id}")
            return jsonify({"error": "Merchant profile not found"}), 404
        
        # Fields that are NOT allowed to be updated
        restricted_fields = ['business_email', 'business_phone', 'id', 'user_id', 
                            'verification_status', 'is_verified', 'verification_submitted_at',
                            'verification_completed_at', 'verification_notes',
                            'created_at', 'updated_at']
        
        # Check if user is trying to update restricted fields
        restricted_attempted = [field for field in data.keys() if field in restricted_fields]
        if restricted_attempted:
            return jsonify({
                "error": f"Cannot update restricted fields: {', '.join(restricted_attempted)}"
            }), 400
        
        # Handle username update separately (with 1-year restriction)
        if 'username' in data and data['username']:
            new_username = data['username'].strip().lower()
            
            # Check if username update is allowed (once per year)
            if merchant_profile.username_updated_at:
                from datetime import timedelta
                one_year_ago = datetime.utcnow() - timedelta(days=365)
                if merchant_profile.username_updated_at > one_year_ago:
                    days_remaining = (merchant_profile.username_updated_at + timedelta(days=365) - datetime.utcnow()).days
                    return jsonify({
                        "error": f"Username can only be updated once per year. You can update again in {days_remaining} days."
                    }), 400
            
            # Check if username is already taken by another merchant
            existing_merchant = MerchantProfile.get_by_username(new_username)
            if existing_merchant and existing_merchant.id != merchant_profile.id:
                return jsonify({"error": "Username already taken"}), 409
            
            # Update username and timestamp
            merchant_profile.username = new_username
            merchant_profile.username_updated_at = datetime.utcnow()
            data.pop('username')  # Remove from data to avoid duplicate processing
            logger.debug(f"Updated username to {new_username}")

        # Bio fields are sanitised and validated separately (and popped off
        # `data`), because the limits apply to the cleaned value.
        bio_errors = _apply_bio_updates(merchant_profile, data)
        if bio_errors:
            db.session.rollback()
            return jsonify({"error": "Validation error", "details": bio_errors}), 400

        # Allowed fields to update
        allowed_fields = [
            'business_name', 'business_description', 'business_address', 'profile_img',
            'country_code', 'state_province', 'city', 'postal_code',
            'bank_account_number', 'bank_name', 'bank_branch', 'bank_iban',
            'gstin', 'pan_number', 'bank_ifsc_code',
            'tax_id', 'vat_number', 'sales_tax_number',
            'bank_swift_code', 'bank_routing_number'
        ]
        
        # Update allowed fields
        for field, value in data.items():
            if field in allowed_fields and hasattr(merchant_profile, field):
                setattr(merchant_profile, field, value)
                logger.debug(f"Updated field {field} to {value}")
        
        # If country code is updated, validate required fields
        if 'country_code' in data:
            country_code = data['country_code']
            logger.debug(f"Validating country-specific fields for country: {country_code}")
            if country_code == CountryCode.INDIA.value:
                missing_fields = []
                if not merchant_profile.pan_number:
                    missing_fields.append('pan_number')
                if not merchant_profile.bank_account_number:
                    missing_fields.append('bank_account_number')
                if not merchant_profile.bank_name:
                    missing_fields.append('bank_name')
                if not merchant_profile.bank_ifsc_code:
                    missing_fields.append('bank_ifsc_code')
                if missing_fields:
                    error_msg = f"Missing required fields for Indian merchant: {', '.join(missing_fields)}"
                    logger.error(error_msg)
                    return jsonify({
                        "error": "Validation error",
                        "details": error_msg
                    }), 400
            else:
                missing_fields = []
                if not merchant_profile.bank_account_number:
                    missing_fields.append('bank_account_number')
                if not merchant_profile.bank_name:
                    missing_fields.append('bank_name')
                if missing_fields:
                    error_msg = f"Missing required fields for international merchant: {', '.join(missing_fields)}"
                    logger.error(error_msg)
                    return jsonify({
                        "error": "Validation error",
                        "details": error_msg
                    }), 400
        
        merchant_profile.updated_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"Successfully updated profile for merchant_id: {merchant_id}")
        
        return jsonify({
            "message": "Profile updated successfully",
            "profile": {
                "business_name": merchant_profile.business_name,
                "business_email": merchant_profile.business_email,
                "country_code": merchant_profile.country_code,
                "verification_status": merchant_profile.verification_status.value,
                **serialize_bio(merchant_profile)
            }
        }), 200
        
    except ValidationError as e:
        logger.error(f"Validation error: {e.messages}")
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    except Exception as e:
        logger.error(f"Unexpected error in update_profile: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --------------------------------------------------------------------------- #
# Intro video
# --------------------------------------------------------------------------- #

def _intro_video_error_response(error):
    """Uniform error body for IntroVideoError, matching this file's shape."""
    body = {"error": error.message}
    if error.details:
        body["details"] = error.details
    return jsonify(body), error.status_code


def _merchant_profile_or_error():
    """Resolve the caller's merchant profile from the JWT. Never from input."""
    merchant_profile = MerchantProfile.get_by_user_id(get_jwt_identity())
    if not merchant_profile:
        return None, (jsonify({"error": "Merchant profile not found"}), 404)
    return merchant_profile, None


@merchants_bp.route('/profile/intro-video', methods=['GET'])
@jwt_required()
@merchant_role_required
def get_intro_video():
    """
    Get the merchant's own intro video.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Intro video, or null when the merchant has not uploaded one
      404:
        description: Merchant profile not found
    """
    merchant_profile, error = _merchant_profile_or_error()
    if error:
        return error
    # Null rather than 404: "no video yet" is a normal state, not an error the
    # client should have to special-case.
    video = MerchantIntroVideoController.get_for_owner(merchant_profile)
    return jsonify({
        "intro_video": serialize_intro_video(video, owner_view=True),
        "limits": intro_video_limits(),
    }), 200


@merchants_bp.route('/profile/intro-video', methods=['POST'])
@jwt_required()
@merchant_role_required
def create_intro_video():
    """
    Upload the merchant's intro video.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: video
        type: file
        required: true
        description: MP4 or MOV, max 50MB, max 60 seconds
      - in: formData
        name: title
        type: string
        required: false
      - in: formData
        name: caption
        type: string
        required: false
      - in: formData
        name: duration_seconds
        type: integer
        required: false
        description: Client-measured duration; used only when ffprobe is unavailable
    responses:
      201:
        description: Intro video uploaded
      400:
        description: Validation error
      409:
        description: An intro video already exists
      429:
        description: Daily upload limit reached
      500:
        description: Upload failed
    """
    merchant_profile, error = _merchant_profile_or_error()
    if error:
        return error
    try:
        video = MerchantIntroVideoController.create(
            merchant_profile,
            request.files.get('video'),
            title=request.form.get('title'),
            caption=request.form.get('caption'),
            duration_hint=request.form.get('duration_seconds'),
        )
    except IntroVideoError as e:
        return _intro_video_error_response(e)

    return jsonify({
        "message": "Intro video uploaded successfully",
        "intro_video": serialize_intro_video(video, owner_view=True),
    }), 201


@merchants_bp.route('/profile/intro-video', methods=['PUT'])
@jwt_required()
@merchant_role_required
def update_intro_video():
    """
    Update intro video metadata (title, caption, visibility). Does not replace
    the file — use PUT /profile/intro-video/file for that.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              maxLength: 120
            caption:
              type: string
              maxLength: 500
            is_active:
              type: boolean
    responses:
      200:
        description: Intro video updated
      400:
        description: Validation error
      404:
        description: No intro video found
    """
    merchant_profile, error = _merchant_profile_or_error()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        video = MerchantIntroVideoController.update_metadata(
            merchant_profile,
            title=data.get('title') if 'title' in data else None,
            caption=data.get('caption') if 'caption' in data else None,
            is_active=data.get('is_active') if 'is_active' in data else None,
        )
    except IntroVideoError as e:
        return _intro_video_error_response(e)

    return jsonify({
        "message": "Intro video updated successfully",
        "intro_video": serialize_intro_video(video, owner_view=True),
    }), 200


@merchants_bp.route('/profile/intro-video/file', methods=['PUT', 'POST'])
@jwt_required()
@merchant_role_required
def replace_intro_video_file():
    """
    Replace the intro video file, keeping title/caption unless overridden.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: video
        type: file
        required: true
      - in: formData
        name: title
        type: string
        required: false
      - in: formData
        name: caption
        type: string
        required: false
      - in: formData
        name: duration_seconds
        type: integer
        required: false
    responses:
      200:
        description: Intro video replaced
      400:
        description: Validation error
      404:
        description: No intro video to replace
      429:
        description: Daily upload limit reached
      500:
        description: Upload failed
    """
    merchant_profile, error = _merchant_profile_or_error()
    if error:
        return error
    try:
        video = MerchantIntroVideoController.replace_file(
            merchant_profile,
            request.files.get('video'),
            title=request.form.get('title'),
            caption=request.form.get('caption'),
            duration_hint=request.form.get('duration_seconds'),
        )
    except IntroVideoError as e:
        return _intro_video_error_response(e)

    return jsonify({
        "message": "Intro video replaced successfully",
        "intro_video": serialize_intro_video(video, owner_view=True),
    }), 200


@merchants_bp.route('/profile/intro-video', methods=['DELETE'])
@jwt_required()
@merchant_role_required
def delete_intro_video():
    """
    Delete the merchant's intro video.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Intro video deleted
      404:
        description: No intro video found
    """
    merchant_profile, error = _merchant_profile_or_error()
    if error:
        return error
    try:
        MerchantIntroVideoController.delete(merchant_profile)
    except IntroVideoError as e:
        return _intro_video_error_response(e)
    return jsonify({"message": "Intro video deleted successfully"}), 200


@merchants_bp.route('/<int:merchant_id>/intro-video', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_public_intro_video(merchant_id):
    """
    Get a merchant's public intro video.
    ---
    tags:
      - Merchant
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
    responses:
      200:
        description: Intro video, or null when there is nothing to show
    """
    merchant_profile = MerchantProfile.get_by_id(merchant_id)
    # Null, never 404: a hidden video must be indistinguishable from no video,
    # otherwise the status code leaks moderation state to shoppers.
    if not merchant_profile:
        return jsonify({"intro_video": None}), 200
    video = MerchantIntroVideoController.get_public(merchant_profile)
    return jsonify({"intro_video": serialize_intro_video(video)}), 200


@merchants_bp.route('/profile/image', methods=['POST'])
@jwt_required()
@merchant_role_required
def upload_profile_image():
    """
    Upload or update merchant profile image.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: profile_image
        type: file
        required: true
        description: Profile image file to upload
    responses:
      200:
        description: Profile image uploaded successfully
        schema:
          type: object
          properties:
            message:
              type: string
            profile_img_url:
              type: string
      400:
        description: No file provided or invalid file
      404:
        description: Merchant profile not found
      500:
        description: Upload failed
    """
    try:
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            logger.error(f"Merchant profile not found for user_id: {merchant_id}")
            return jsonify({"error": "Merchant profile not found"}), 404
        
        # Check if file is present
        if 'profile_image' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
        
        file = request.files['profile_image']
        if file.filename == '':
            return jsonify({"error": "No file selected for uploading"}), 400
        
        # Delete old profile image from S3 if it exists
        if merchant_profile.profile_img:
            try:
                from services.s3_service import get_s3_service
                s3_service = get_s3_service()
                s3_service.delete_profile_image(merchant_profile.profile_img)
            except Exception as e:
                logger.warning(f"Failed to delete old profile image from S3: {str(e)}")
        
        # Upload to S3
        from services.s3_service import get_s3_service
        s3_service = get_s3_service()
        # Use merchant_id (which is the user_id) for the upload
        upload_result = s3_service.upload_profile_image(file, merchant_id)
        
        secure_url = upload_result.get('url')
        if not secure_url:
            return jsonify({"error": "Failed to get URL from S3 upload result"}), 500
        
        # Update merchant profile
        merchant_profile.profile_img = secure_url
        merchant_profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Successfully uploaded profile image for merchant_id: {merchant_id}")
        
        return jsonify({
            "message": "Profile image uploaded successfully",
            "profile_img_url": merchant_profile.profile_img
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Profile image upload error for merchant {merchant_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "An internal error occurred during file upload"}), 500

@merchants_bp.route('/profile/verify', methods=['POST'])
@jwt_required()
@merchant_role_required
def submit_for_verification():
    """
    Submit merchant profile for verification.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Profile submitted for verification
        schema:
          type: object
          properties:
            message:
              type: string
            verification_status:
              type: string
      400:
        description: Validation error - missing required fields
      404:
        description: Merchant profile not found
      500:
        description: Internal server error
    """
    try:
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            return jsonify({"error": "Merchant profile not found"}), 404
            
        # Validate required fields based on country (relaxed)
        if merchant_profile.country_code == CountryCode.INDIA.value:
            missing = []
            if not merchant_profile.pan_number:
                missing.append('pan_number')
            if not merchant_profile.bank_account_number:
                missing.append('bank_account_number')
            if not merchant_profile.bank_name:
                missing.append('bank_name')
            if not merchant_profile.bank_ifsc_code:
                missing.append('bank_ifsc_code')
            if missing:
                return jsonify({
                    "error": "Validation error",
                    "details": f"Missing required fields: {', '.join(missing)}"
                }), 400
        else:
            missing = []
            if not merchant_profile.bank_account_number:
                missing.append('bank_account_number')
            if not merchant_profile.bank_name:
                missing.append('bank_name')
            if missing:
                return jsonify({
                    "error": "Validation error",
                    "details": f"Missing required fields: {', '.join(missing)}"
                }), 400
            
        merchant_profile.submit_for_verification()
        
        return jsonify({
            "message": "Profile submitted for verification",
            "verification_status": merchant_profile.verification_status.value
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@merchants_bp.route('/products', methods=['GET'])
@jwt_required()
@merchant_role_required
@cache_response(timeout=60, key_prefix='merchant_products')
def get_products():
    """
    Get merchant products.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Products retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not a merchant
    """
    merchant_id = get_jwt_identity()
    return {"message": f"Products for merchant ID: {merchant_id}"}, 200

@merchants_bp.route('/analytics', methods=['GET'])
@jwt_required()
@merchant_role_required
@cache_response(timeout=300, key_prefix='merchant_analytics')
def get_analytics():
    """
    Get merchant analytics.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Analytics retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not a merchant
    """
    merchant_id = get_jwt_identity()
    return {"message": f"Analytics for merchant ID: {merchant_id}"}, 200

@merchants_bp.route('/verification-status', methods=['GET'])
@jwt_required()
@merchant_role_required
def get_verification_status():
    """
    Get merchant verification status and check if documents have been submitted.
    ---
    tags:
      - Merchant
    security:
      - Bearer: []
    responses:
      200:
        description: Verification status retrieved successfully
        schema:
          type: object
          properties:
            has_submitted_documents:
              type: boolean
            verification_status:
              type: string
            verification_submitted_at:
              type: string
              format: date-time
            verification_completed_at:
              type: string
              format: date-time
            verification_notes:
              type: string
            required_documents:
              type: array
              items:
                type: string
            submitted_documents:
              type: array
              items:
                type: string
            document_details:
              type: array
              items:
                type: object
                properties:
                  document_type:
                    type: string
                  status:
                    type: string
                  admin_notes:
                    type: string
                  verified_at:
                    type: string
                    format: date-time
      404:
        description: Merchant profile not found
      500:
        description: Internal server error
    """
    try:
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            return jsonify({
                "error": "Merchant profile not found",
                "has_submitted_documents": False,
                "verification_status": "pending",
                "required_documents": [],
                "submitted_documents": [],
                "document_details": []
            }), 404
        
        # Get all documents for the merchant
        documents = MerchantDocument.get_by_merchant_id(merchant_profile.id)
        
        # Check if documents have been submitted
        has_submitted_documents = (
            merchant_profile.verification_status != VerificationStatus.PENDING and
            merchant_profile.verification_submitted_at is not None and
            len(documents) > 0
        )
        
        # If no documents are submitted, return early with pending status
        if not has_submitted_documents:
            return jsonify({
                "has_submitted_documents": False,
                "verification_status": "pending",
                "verification_submitted_at": None,
                "verification_completed_at": None,
                "verification_notes": None,
                "required_documents": merchant_profile.required_documents,
                "submitted_documents": [],
                "document_details": []
            }), 200
        
        # Prepare document details with admin notes
        document_details = [{
            'document_type': doc.document_type.value,
            'status': doc.status.value,
            'admin_notes': doc.admin_notes,
            'verified_at': doc.verified_at.isoformat() if doc.verified_at else None
        } for doc in documents]
        
        return jsonify({
            "has_submitted_documents": True,
            "verification_status": merchant_profile.verification_status.value,
            "verification_submitted_at": merchant_profile.verification_submitted_at.isoformat() if merchant_profile.verification_submitted_at else None,
            "verification_completed_at": merchant_profile.verification_completed_at.isoformat() if merchant_profile.verification_completed_at else None,
            "verification_notes": merchant_profile.verification_notes,
            "required_documents": merchant_profile.required_documents,
            "submitted_documents": merchant_profile.submitted_documents,
            "document_details": document_details
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting verification status: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Failed to get verification status",
            "details": str(e),
            "has_submitted_documents": False,
            "verification_status": "pending",
            "required_documents": [],
            "submitted_documents": [],
            "document_details": []
        }), 500