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
    """
    Get all merchants for admin dashboard.
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: List of merchants retrieved successfully
        schema:
          type: object
          properties:
            merchants:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  user_id:
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
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
                  user:
                    type: object
                    properties:
                      id:
                        type: integer
                      email:
                        type: string
                      first_name:
                        type: string
                      last_name:
                        type: string
                      role:
                        type: string
                  documents:
                    type: array
                    items:
                      type: object
                      properties:
                        id:
                          type: integer
                        document_type:
                          type: string
                        status:
                          type: string
                        file_url:
                          type: string
                        created_at:
                          type: string
                          format: date-time
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not an admin
      500:
        description: Internal server error
    """
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
    """
    Approve a merchant.
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        description: Merchant ID
    responses:
      200:
        description: Merchant approved successfully
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not an admin
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
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
    """
    Reject a merchant.
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        description: Merchant ID
      - in: body
        name: body
        schema:
          type: object
          properties:
            reason:
              type: string
              description: Reason for rejection
    responses:
      200:
        description: Merchant rejected successfully
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not an admin
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
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
    """
    Get detailed information for a specific merchant.
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        description: Merchant ID
    responses:
      200:
        description: Merchant details retrieved successfully
        schema:
          type: object
          properties:
            id:
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
            country_code:
              type: string
            # India-specific fields
            gstin:
              type: string
            pan_number:
              type: string
            bank_ifsc_code:
              type: string
            # Global fields
            tax_id:
              type: string
            vat_number:
              type: string
            sales_tax_number:
              type: string
            bank_swift_code:
              type: string
            bank_routing_number:
              type: string
            bank_iban:
              type: string
            # Common fields
            bank_account_number:
              type: string
            bank_name:
              type: string
            bank_branch:
              type: string
            verification_status:
              type: string
            is_verified:
              type: boolean
            verification_notes:
              type: string
            verification_submitted_at:
              type: string
              format: date-time
            verification_completed_at:
              type: string
              format: date-time
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
            user:
              type: object
              properties:
                id:
                  type: integer
                email:
                  type: string
                first_name:
                  type: string
                last_name:
                  type: string
                phone:
                  type: string
                role:
                  type: string
            documents:
              type: object
              additionalProperties:
                type: object
                properties:
                  id:
                    type: integer
                  type:
                    type: string
                  status:
                    type: string
                  submitted:
                    type: boolean
                  imageUrl:
                    type: string
                  file_name:
                    type: string
                  file_size:
                    type: integer
                  mime_type:
                    type: string
                  admin_notes:
                    type: string
                  verified_at:
                    type: string
                    format: date-time
      401:
        description: Unauthorized
      403:
        description: Forbidden - User is not an admin
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
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
            
        # Format merchant data with country-specific fields
        merchant_data = {
            "id": merchant_profile.id,
            "business_name": merchant_profile.business_name,
            "business_description": merchant_profile.business_description,
            "business_email": merchant_profile.business_email,
            "business_phone": merchant_profile.business_phone,
            "business_address": merchant_profile.business_address,
            "country_code": merchant_profile.country_code,
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
            "documents": documents_data,
            # Common fields
            "bank_account_number": merchant_profile.bank_account_number,
            "bank_name": merchant_profile.bank_name,
            "bank_branch": merchant_profile.bank_branch,
        }

        # Add country-specific fields
        if merchant_profile.country_code == 'IN':
            # India-specific fields
            merchant_data.update({
                "gstin": merchant_profile.gstin,
                "pan_number": merchant_profile.pan_number,
                "bank_ifsc_code": merchant_profile.bank_ifsc_code,
                # Set global fields to null for Indian merchants
                "tax_id": None,
                "vat_number": None,
                "sales_tax_number": None,
                "bank_swift_code": None,
                "bank_routing_number": None,
                "bank_iban": None
            })
        else:
            # Global fields
            merchant_data.update({
                "tax_id": merchant_profile.tax_id,
                "vat_number": merchant_profile.vat_number,
                "sales_tax_number": merchant_profile.sales_tax_number,
                "bank_swift_code": merchant_profile.bank_swift_code,
                "bank_routing_number": merchant_profile.bank_routing_number,
                "bank_iban": merchant_profile.bank_iban,
                # Set Indian fields to null for global merchants
                "gstin": None,
                "pan_number": None,
                "bank_ifsc_code": None
            })
        
        return jsonify(merchant_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500