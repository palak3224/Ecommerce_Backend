from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from auth.utils import admin_role_required
from auth.models.models import User, MerchantProfile
from auth.models.merchant_document import MerchantDocument

# Create admin blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/merchants', methods=['GET'])
@jwt_required()
@admin_role_required
def get_all_merchants():
    """Get all merchants for admin dashboard."""
    try:
        # Get all merchant profiles
        merchant_profiles = MerchantProfile.query.all()
        
        merchants_data = []
        for profile in merchant_profiles:
            # Get associated user
            user = User.get_by_id(profile.user_id)
            if not user:
                continue
                
            # Get documents
            documents = MerchantDocument.query.filter_by(merchant_id=profile.id).all()
            
            # Format merchant data
            merchant_data = {
                "id": profile.id,
                "user_id": profile.user_id,
                "business_name": profile.business_name,
                "business_description": profile.business_description,
                "business_email": profile.business_email,
                "business_phone": profile.business_phone,
                "business_address": profile.business_address,
                "verification_status": profile.verification_status.value,
                "verification_submitted_at": profile.verification_submitted_at.isoformat() if profile.verification_submitted_at else None,
                "verification_completed_at": profile.verification_completed_at.isoformat() if profile.verification_completed_at else None,
                "verification_notes": profile.verification_notes,
                "created_at": profile.created_at.isoformat(),
                "updated_at": profile.updated_at.isoformat(),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role.value
                },
                "documents": [{
                    "id": doc.id,
                    "document_type": doc.document_type.value,
                    "status": doc.status.value,
                    "file_url": doc.file_url,
                    "created_at": doc.created_at.isoformat()
                } for doc in documents]
            }
            
            merchants_data.append(merchant_data)
        
        return jsonify({
            "merchants": merchants_data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add endpoints for approving and rejecting merchants
@admin_bp.route('/merchants/<int:id>/approve', methods=['POST'])
@jwt_required()
@admin_role_required
def approve_merchant(id):
    """Approve a merchant."""
    try:
        merchant = MerchantProfile.query.get_or_404(id)
        merchant.approve()
        return jsonify({"message": "Merchant approved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/merchants/<int:id>/reject', methods=['POST'])
@jwt_required()
@admin_role_required
def reject_merchant(id):
    """Reject a merchant."""
    try:
        data = request.json
        reason = data.get('reason', 'No reason provided')
        
        merchant = MerchantProfile.query.get_or_404(id)
        merchant.reject(reason)
        return jsonify({"message": "Merchant rejected successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/merchants/<int:id>', methods=['GET'])
@jwt_required()
@admin_role_required
def get_merchant_details(id):
    """Get detailed information for a specific merchant."""
    try:
        # Get merchant profile
        merchant_profile = MerchantProfile.query.get_or_404(id)
        
        # Get associated user
        user = User.get_by_id(merchant_profile.user_id)
        if not user:
            return jsonify({"error": "Associated user not found"}), 404
            
        # Get documents
        documents = MerchantDocument.query.filter_by(merchant_id=merchant_profile.id).all()
        
        # Format document data
        documents_data = {}
        for doc in documents:
            documents_data[doc.document_type.value] = {
                "id": doc.id,
                "type": doc.document_type.value,
                "status": doc.status.value,
                "submitted": True,
                "imageUrl": doc.file_url,
                "file_name": doc.file_name,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "admin_notes": doc.admin_notes,
                "verified_at": doc.verified_at.isoformat() if doc.verified_at else None
            }
            
        # Format merchant data
        merchant_data = {
            "id": merchant_profile.id,
            "business_name": merchant_profile.business_name,
            "business_description": merchant_profile.business_description,
            "business_email": merchant_profile.business_email,
            "business_phone": merchant_profile.business_phone,
            "business_address": merchant_profile.business_address,
            "gstin": merchant_profile.gstin,
            "pan_number": merchant_profile.pan_number,
            "bank_account_number": merchant_profile.bank_account_number,
            "bank_ifsc_code": merchant_profile.bank_ifsc_code,
            "verification_status": merchant_profile.verification_status.value,
            "is_verified": merchant_profile.is_verified,
            "verification_notes": merchant_profile.verification_notes,
            "verification_submitted_at": merchant_profile.verification_submitted_at.isoformat() if merchant_profile.verification_submitted_at else None,
            "verification_completed_at": merchant_profile.verification_completed_at.isoformat() if merchant_profile.verification_completed_at else None,
            "created_at": merchant_profile.created_at.isoformat(),
            "updated_at": merchant_profile.updated_at.isoformat(),
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "role": user.role.value
            },
            "documents": documents_data
        }
        
        return jsonify(merchant_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500