from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from auth.utils import merchant_role_required
from common.decorators import rate_limit, cache_response
from auth.models import User, MerchantProfile
from auth.models.merchant_document import VerificationStatus
from common.database import db

# Schema definitions
class CreateMerchantProfileSchema(Schema):
    business_name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    business_description = fields.Str(required=True)
    business_email = fields.Email(required=True)
    business_phone = fields.Str(required=True)
    business_address = fields.Str(required=True)
    gstin = fields.Str(validate=validate.Length(max=15))
    pan_number = fields.Str(validate=validate.Length(max=10))
    store_url = fields.Str(validate=validate.Length(max=255))
    logo_url = fields.Str(validate=validate.Length(max=255))

class UpdateProfileSchema(Schema):
    business_name = fields.Str(validate=validate.Length(min=2, max=200))
    business_description = fields.Str()
    business_email = fields.Email()
    business_phone = fields.Str()
    business_address = fields.Str()
    gstin = fields.Str(validate=validate.Length(max=15))
    pan_number = fields.Str(validate=validate.Length(max=10))
    store_url = fields.Str(validate=validate.Length(max=255))
    logo_url = fields.Str(validate=validate.Length(max=255))

# Create merchants blueprint
merchants_bp = Blueprint('merchants', __name__)

@merchants_bp.route('/profile', methods=['POST'])
@jwt_required()
@merchant_role_required
def create_profile():
    """Create initial merchant profile."""
    try:
        # Validate request data
        schema = CreateMerchantProfileSchema()
        data = schema.load(request.json)
        
        merchant_id = get_jwt_identity()
        
        # Check if profile already exists
        existing_profile = MerchantProfile.get_by_user_id(merchant_id)
        if existing_profile:
            return jsonify({"error": "Merchant profile already exists"}), 400
        
        # Create new merchant profile
        merchant_profile = MerchantProfile(
            user_id=merchant_id,
            business_name=data['business_name'],
            business_description=data['business_description'],
            business_email=data['business_email'],
            business_phone=data['business_phone'],
            business_address=data['business_address'],
            gstin=data.get('gstin'),
            pan_number=data.get('pan_number'),
            store_url=data.get('store_url'),
            logo_url=data.get('logo_url'),
            verification_status=VerificationStatus.PENDING,
            is_verified=False
        )
        
        merchant_profile.save()
        
        return jsonify({
            "message": "Merchant profile created successfully",
            "profile": {
                "business_name": merchant_profile.business_name,
                "business_email": merchant_profile.business_email,
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
@cache_response(timeout=60, key_prefix='merchant_profile')
def get_profile():
    """Get merchant profile."""
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
            "gstin": merchant_profile.gstin,
            "pan_number": merchant_profile.pan_number,
            "store_url": merchant_profile.store_url,
            "logo_url": merchant_profile.logo_url,
            "is_verified": merchant_profile.is_verified,
            "verification_status": merchant_profile.verification_status.value,
            "verification_submitted_at": merchant_profile.verification_submitted_at.isoformat() if merchant_profile.verification_submitted_at else None,
            "verification_completed_at": merchant_profile.verification_completed_at.isoformat() if merchant_profile.verification_completed_at else None,
            "verification_notes": merchant_profile.verification_notes
        }
    }), 200

@merchants_bp.route('/profile', methods=['PUT'])
@jwt_required()
@merchant_role_required
def update_profile():
    """Update merchant profile."""
    try:
        # Validate request data
        schema = UpdateProfileSchema()
        data = schema.load(request.json)
        
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            return jsonify({"error": "Merchant profile not found"}), 404
        
        # Update profile fields
        for field, value in data.items():
            if hasattr(merchant_profile, field):
                setattr(merchant_profile, field, value)
        
        merchant_profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "message": "Profile updated successfully",
            "profile": {
                "business_name": merchant_profile.business_name,
                "business_email": merchant_profile.business_email,
                "verification_status": merchant_profile.verification_status.value
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@merchants_bp.route('/profile/verify', methods=['POST'])
@jwt_required()
@merchant_role_required
def submit_for_verification():
    """Submit merchant profile for verification."""
    try:
        merchant_id = get_jwt_identity()
        merchant_profile = MerchantProfile.get_by_user_id(merchant_id)
        
        if not merchant_profile:
            return jsonify({"error": "Merchant profile not found"}), 404
            
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
    """Get merchant products."""
    merchant_id = get_jwt_identity()
    # In a real implementation, fetch merchant products from database
    # This is a placeholder
    return {"message": f"Products for merchant ID: {merchant_id}"}, 200

@merchants_bp.route('/analytics', methods=['GET'])
@jwt_required()
@merchant_role_required
@cache_response(timeout=300, key_prefix='merchant_analytics')
def get_analytics():
    """Get merchant analytics."""
    merchant_id = get_jwt_identity()
    # In a real implementation, fetch merchant analytics from database
    # This is a placeholder
    return {"message": f"Analytics for merchant ID: {merchant_id}"}, 200