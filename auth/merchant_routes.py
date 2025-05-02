from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError

from auth.utils import merchant_role_required, admin_role_required
from auth.models.merchant_document import DocumentStatus
from merchant.controllers import (
    update_merchant_profile, 
    get_merchant_verification_status,
    upload_merchant_document,
    delete_merchant_document,
    submit_merchant_verification,
    get_merchant_profile,
    update_merchant_logo,
    admin_get_pending_verifications,
    admin_get_merchant_details,
    admin_verify_merchant,
    admin_review_document,
    admin_get_all_merchants
)

# Schema definitions
class MerchantProfileUpdateSchema(Schema):
    business_name = fields.Str()
    business_description = fields.Str()
    business_email = fields.Email()
    business_phone = fields.Str()
    business_address = fields.Str()
    gstin = fields.Str()
    pan_number = fields.Str()
    store_url = fields.Str()

class DocumentReviewSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf([status.value for status in DocumentStatus]))
    notes = fields.Str()

class MerchantVerificationSchema(Schema):
    approval = fields.Bool(required=True)
    notes = fields.Str()

# Create merchant blueprint
merchant_bp = Blueprint('merchant', __name__)

@merchant_bp.route('/profile', methods=['GET'])
@jwt_required()
@merchant_role_required
def get_profile():
    """Get merchant's own profile."""
    user_id = get_jwt_identity()
    merchant = MerchantProfile.get_by_user_id(user_id)
    if not merchant:
        return jsonify({"error": "Merchant profile not found"}), 404
    
    response, status_code = get_merchant_profile(merchant.id)
    return jsonify(response), status_code

@merchant_bp.route('/profile', methods=['PUT'])
@jwt_required()
@merchant_role_required
def update_profile():
    """Update merchant profile."""
    try:
        # Validate request data
        schema = MerchantProfileUpdateSchema()
        data = schema.load(request.json)
        
        # Update profile
        user_id = get_jwt_identity()
        response, status_code = update_merchant_profile(user_id, data)
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@merchant_bp.route('/verification/status', methods=['GET'])
@jwt_required()
@merchant_role_required
def verification_status():
    """Get merchant verification status."""
    user_id = get_jwt_identity()
    response, status_code = get_merchant_verification_status(user_id)
    return jsonify(response), status_code

@merchant_bp.route('/verification/submit', methods=['POST'])
@jwt_required()
@merchant_role_required
def submit_verification():
    """Submit merchant profile for verification."""
    user_id = get_jwt_identity()
    response, status_code = submit_merchant_verification(user_id)
    return jsonify(response), status_code

@merchant_bp.route('/document/<document_type>', methods=['POST'])
@jwt_required()
@merchant_role_required
def upload_document(document_type):
    """Upload merchant document."""
    # Check if file is included in the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    user_id = get_jwt_identity()
    response, status_code = upload_merchant_document(user_id, document_type, file)
    return jsonify(response), status_code

@merchant_bp.route('/document/<int:document_id>', methods=['DELETE'])
@jwt_required()
@merchant_role_required
def delete_document(document_id):
    """Delete merchant document."""
    user_id = get_jwt_identity()
    response, status_code = delete_merchant_document(user_id, document_id)
    return jsonify(response), status_code

@merchant_bp.route('/logo', methods=['POST'])
@jwt_required()
@merchant_role_required
def upload_logo():
    """Upload merchant logo."""
    # Check if file is included in the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    user_id = get_jwt_identity()
    response, status_code = update_merchant_logo(user_id, file)
    return jsonify(response), status_code

# Admin routes
@merchant_bp.route('/admin/verifications/pending', methods=['GET'])
@jwt_required()
@admin_role_required
def get_pending_verifications():
    """Get pending merchant verifications."""
    response, status_code = admin_get_pending_verifications()
    return jsonify(response), status_code

@merchant_bp.route('/admin/merchant/<int:merchant_id>', methods=['GET'])
@jwt_required()
@admin_role_required
def get_merchant_details(merchant_id):
    """Get merchant details for admin."""
    response, status_code = admin_get_merchant_details(merchant_id)
    return jsonify(response), status_code

@merchant_bp.route('/admin/merchant/<int:merchant_id>/verify', methods=['POST'])
@jwt_required()
@admin_role_required
def verify_merchant(merchant_id):
    """Verify or reject merchant."""
    try:
        # Validate request data
        schema = MerchantVerificationSchema()
        data = schema.load(request.json)
        
        # Process verification
        admin_id = get_jwt_identity()
        response, status_code = admin_verify_merchant(
            admin_id, 
            merchant_id, 
            data['approval'], 
            data.get('notes')
        )
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@merchant_bp.route('/admin/document/<int:document_id>/review', methods=['POST'])
@jwt_required()
@admin_role_required
def review_document(document_id):
    """Review merchant document."""
    try:
        # Validate request data
        schema = DocumentReviewSchema()
        data = schema.load(request.json)
        
        # Process document review
        admin_id = get_jwt_identity()
        response, status_code = admin_review_document(
            admin_id, 
            document_id, 
            data['status'], 
            data.get('notes')
        )
        return jsonify(response), status_code
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.messages}), 400

@merchant_bp.route('/admin/merchants', methods=['GET'])
@jwt_required()
@admin_role_required
def get_all_merchants():
    """Get all merchants with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    
    response, status_code = admin_get_all_merchants(page, per_page, status)
    return jsonify(response), status_code