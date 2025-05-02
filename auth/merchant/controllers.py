from flask import current_app, request
import os
from datetime import datetime
from werkzeug.utils import secure_filename

from common.database import db
from auth.models import User, MerchantProfile, VerificationStatus
from auth.models.merchant_document import MerchantDocument, DocumentType, DocumentStatus

def update_merchant_profile(user_id, data):
    """Update a merchant's profile information."""
    try:
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Update fields
        if 'business_name' in data:
            merchant.business_name = data['business_name']
        if 'business_description' in data:
            merchant.business_description = data['business_description']
        if 'business_email' in data:
            merchant.business_email = data['business_email']
        if 'business_phone' in data:
            merchant.business_phone = data['business_phone']
        if 'business_address' in data:
            merchant.business_address = data['business_address']
        if 'gstin' in data:
            merchant.gstin = data['gstin']
        if 'pan_number' in data:
            merchant.pan_number = data['pan_number']
        if 'store_url' in data:
            merchant.store_url = data['store_url']
        
        db.session.commit()
        
        return {
            "message": "Merchant profile updated successfully",
            "merchant": {
                "id": merchant.id,
                "business_name": merchant.business_name,
                "verification_status": merchant.verification_status.value,
                "is_verified": merchant.is_verified
            }
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update merchant profile error: {str(e)}")
        return {"error": "Failed to update merchant profile"}, 500

def get_merchant_verification_status(user_id):
    """Get merchant verification status and document submission status."""
    try:
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Get user information
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Get documents submitted
        documents = MerchantDocument.get_by_merchant_id(merchant.id)
        document_status = {}
        
        # Initialize all document types as not submitted
        for doc_type in DocumentType:
            document_status[doc_type.value] = {
                "submitted": False,
                "status": None,
                "file_name": None,
                "uploaded_at": None
            }
        
        # Update with submitted documents
        for doc in documents:
            document_status[doc.document_type.value] = {
                "submitted": True,
                "status": doc.status,
                "file_name": doc.file_name,
                "uploaded_at": doc.created_at.isoformat()
            }
        
        return {
            "merchant_id": merchant.id,
            "business_name": merchant.business_name,
            "verification_status": merchant.verification_status.value,
            "is_verified": merchant.is_verified,
            "email_verified": user.is_email_verified,
            "phone_verified": user.is_phone_verified,
            "verification_submitted_at": merchant.verification_submitted_at.isoformat() if merchant.verification_submitted_at else None,
            "verification_completed_at": merchant.verification_completed_at.isoformat() if merchant.verification_completed_at else None,
            "verification_notes": merchant.verification_notes,
            "documents": document_status
        }, 200
    except Exception as e:
        current_app.logger.error(f"Get verification status error: {str(e)}")
        return {"error": "Failed to get verification status"}, 500

def upload_merchant_document(user_id, document_type, file):
    """Upload a merchant verification document."""
    try:
        # Validate document type
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            return {"error": f"Invalid document type: {document_type}"}, 400
        
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Check if file is provided
        if not file:
            return {"error": "No file provided"}, 400
        
        # Upload to Cloudinary
        folder = f"merchant_documents/{merchant.id}"
        upload_result, error = upload_to_cloudinary(file, folder)
        if error:
            return {"error": f"Failed to upload document: {error}"}, 500
        
        # Check if document already exists
        existing_doc = MerchantDocument.get_by_merchant_and_type(merchant.id, doc_type)
        if existing_doc:
            # Delete old file from Cloudinary
            if existing_doc.public_id:
                delete_from_cloudinary(existing_doc.public_id)
            
            # Update existing document record
            existing_doc.public_id = upload_result['public_id']
            existing_doc.file_url = upload_result['secure_url']
            existing_doc.file_name = file.filename
            existing_doc.file_size = upload_result['bytes']
            existing_doc.mime_type = upload_result['resource_type']
            existing_doc.status = DocumentStatus.PENDING
            existing_doc.updated_at = datetime.utcnow()
            db.session.commit()
            document = existing_doc
        else:
            # Create new document record
            document = MerchantDocument(
                merchant_id=merchant.id,
                document_type=doc_type,
                public_id=upload_result['public_id'],
                file_url=upload_result['secure_url'],
                file_name=file.filename,
                file_size=upload_result['bytes'],
                mime_type=upload_result['resource_type']
            )
            document.save()
        
        return {
            "message": "Document uploaded successfully",
            "document": {
                "id": document.id,
                "document_type": document.document_type.value,
                "file_name": document.file_name,
                "file_url": document.file_url,
                "status": document.status.value,
                "uploaded_at": document.created_at.isoformat()
            }
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Document upload error: {str(e)}")
        return {"error": "Failed to upload document"}, 500

def delete_merchant_document(user_id, document_id):
    """Delete a merchant verification document."""
    try:
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Find document
        document = MerchantDocument.get_by_id(document_id)
        if not document or document.merchant_id != merchant.id:
            return {"error": "Document not found"}, 404
        
        # Remove file if it exists
        if os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                current_app.logger.error(f"Failed to remove file: {str(e)}")
        
        # Delete document record
        document.delete()
        
        return {"message": "Document deleted successfully"}, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Document delete error: {str(e)}")
        return {"error": "Failed to delete document"}, 500

def submit_merchant_verification(user_id):
    """Submit merchant profile for verification."""
    try:
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Find user
        user = User.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Check if email is verified
        if not user.is_email_verified:
            return {"error": "Email must be verified before submitting for verification"}, 400
        
        # Check for required documents
        documents = MerchantDocument.get_by_merchant_id(merchant.id)
        doc_types = [doc.document_type for doc in documents]
        
        required_docs = [
            DocumentType.BUSINESS_REGISTRATION,
            DocumentType.PAN_CARD
        ]
        
        missing_docs = [doc.value for doc in required_docs if doc not in doc_types]
        if missing_docs:
            return {
                "error": "Missing required documents",
                "missing_documents": missing_docs
            }, 400
        
        # Submit for verification
        merchant.submit_for_verification()
        
        return {
            "message": "Merchant profile submitted for verification",
            "verification_status": merchant.verification_status.value
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verification submission error: {str(e)}")
        return {"error": "Failed to submit for verification"}, 500

def get_merchant_profile(merchant_id):
    """Get merchant profile by ID."""
    try:
        merchant = MerchantProfile.get_by_id(merchant_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        return {
            "merchant": {
                "id": merchant.id,
                "business_name": merchant.business_name,
                "business_description": merchant.business_description,
                "business_email": merchant.business_email,
                "business_phone": merchant.business_phone,
                "business_address": merchant.business_address,
                "is_verified": merchant.is_verified,
                "verification_status": merchant.verification_status.value,
                "store_url": merchant.store_url,
                "logo_url": merchant.logo_url,
                "created_at": merchant.created_at.isoformat()
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Get merchant profile error: {str(e)}")
        return {"error": "Failed to get merchant profile"}, 500

def update_merchant_logo(user_id, file):
    """Update merchant logo."""
    try:
        # Find merchant profile
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            return {"error": "Merchant profile not found"}, 404
        
        # Check if file is provided
        if not file:
            return {"error": "No file provided"}, 400
        
        # Upload to Cloudinary
        folder = f"merchant_logos/{merchant.id}"
        upload_result, error = upload_to_cloudinary(file, folder)
        if error:
            return {"error": f"Failed to upload logo: {error}"}, 500
        
        # Delete old logo if exists
        if merchant.logo_public_id:
            delete_from_cloudinary(merchant.logo_public_id)
        
        # Update merchant logo
        merchant.logo_url = upload_result['secure_url']
        merchant.logo_public_id = upload_result['public_id']
        db.session.commit()
        
        return {
            "message": "Logo updated successfully",
            "logo_url": merchant.logo_url
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update logo error: {str(e)}")
        return {"error": "Failed to update logo"}, 500

# Admin functions
def admin_get_pending_verifications():
    """Get all pending merchant verifications for admin review."""
    try:
        # Find merchants with pending verification
        merchants = MerchantProfile.query.filter_by(
            verification_status=VerificationStatus.DOCUMENTS_SUBMITTED
        ).all()
        
        result = []
        for merchant in merchants:
            user = User.get_by_id(merchant.user_id)
            if not user:
                continue
            
            result.append({
                "merchant_id": merchant.id,
                "user_id": user.id,
                "business_name": merchant.business_name,
                "business_email": merchant.business_email,
                "business_phone": merchant.business_phone,
                "submitted_at": merchant.verification_submitted_at.isoformat() if merchant.verification_submitted_at else None,
                "created_at": merchant.created_at.isoformat()
            })
        
        return {"merchants": result}, 200
    except Exception as e:
        current_app.logger.error(f"Get pending verifications error: {str(e)}")
        return {"error": "Failed to get pending verifications"}, 500

def admin_get_merchant_details(merchant_id):
    """Get merchant details for admin review."""
    try:
        # Find merchant
        merchant = MerchantProfile.get_by_id(merchant_id)
        if not merchant:
            return {"error": "Merchant not found"}, 404
        
        # Find user
        user = User.get_by_id(merchant.user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Get documents
        documents = MerchantDocument.get_by_merchant_id(merchant.id)
        doc_list = []
        for doc in documents:
            doc_list.append({
                "id": doc.id,
                "document_type": doc.document_type.value,
                "file_name": doc.file_name,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "status": doc.status,
                "uploaded_at": doc.created_at.isoformat()
            })
        
        return {
            "merchant": {
                "id": merchant.id,
                "business_name": merchant.business_name,
                "business_description": merchant.business_description,
                "business_email": merchant.business_email,
                "business_phone": merchant.business_phone,
                "business_address": merchant.business_address,
                "gstin": merchant.gstin,
                "pan_number": merchant.pan_number,
                "verification_status": merchant.verification_status.value,
                "verification_submitted_at": merchant.verification_submitted_at.isoformat() if merchant.verification_submitted_at else None,
                "created_at": merchant.created_at.isoformat()
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "is_email_verified": user.is_email_verified,
                "is_phone_verified": user.is_phone_verified,
                "created_at": user.created_at.isoformat()
            },
            "documents": doc_list
        }, 200
    except Exception as e:
        current_app.logger.error(f"Get merchant details error: {str(e)}")
        return {"error": "Failed to get merchant details"}, 500

def admin_verify_merchant(admin_id, merchant_id, approval, notes=None):
    """Approve or reject merchant verification."""
    try:
        # Find merchant
        merchant = MerchantProfile.get_by_id(merchant_id)
        if not merchant:
            return {"error": "Merchant not found"}, 404
        
        # Check merchant status
        if merchant.verification_status != VerificationStatus.DOCUMENTS_SUBMITTED and merchant.verification_status != VerificationStatus.UNDER_REVIEW:
            return {"error": f"Merchant is not in a reviewable state. Current status: {merchant.verification_status.value}"}, 400
        
        # Update verification status
        if approval:
            merchant.update_verification_status(VerificationStatus.APPROVED, notes)
            message = "Merchant approved successfully"
        else:
            merchant.update_verification_status(VerificationStatus.REJECTED, notes)
            message = "Merchant rejected successfully"
        
        return {
            "message": message,
            "merchant_id": merchant.id,
            "verification_status": merchant.verification_status.value
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Merchant verification error: {str(e)}")
        return {"error": "Failed to process merchant verification"}, 500

def admin_review_document(admin_id, document_id, status, notes=None):
    """Review a merchant document."""
    try:
        # Find document
        document = MerchantDocument.get_by_id(document_id)
        if not document:
            return {"error": "Document not found"}, 404
        
        # Update document status
        try:
            doc_status = DocumentStatus(status)
            if doc_status == DocumentStatus.APPROVED:
                document.approve(admin_id, notes)
            elif doc_status == DocumentStatus.REJECTED:
                document.reject(admin_id, notes)
            else:
                return {"error": f"Invalid status: {status}"}, 400
        except ValueError:
            return {"error": f"Invalid status: {status}"}, 400
        
        return {
            "message": f"Document {status} successfully",
            "document_id": document.id,
            "status": document.status.value
        }, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Document review error: {str(e)}")
        return {"error": "Failed to review document"}, 500

def admin_get_all_merchants(page=1, per_page=10, status=None):
    """Get all merchants with pagination and optional filtering by status."""
    try:
        query = MerchantProfile.query
        
        # Filter by status if provided
        if status:
            try:
                verification_status = VerificationStatus(status)
                query = query.filter_by(verification_status=verification_status)
            except ValueError:
                return {"error": f"Invalid status: {status}"}, 400
        
        # Paginate results
        pagination = query.order_by(MerchantProfile.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        merchants = []
        for merchant in pagination.items:
            user = User.get_by_id(merchant.user_id)
            if not user:
                continue
                
            merchants.append({
                "id": merchant.id,
                "business_name": merchant.business_name,
                "business_email": merchant.business_email,
                "verification_status": merchant.verification_status.value,
                "is_verified": merchant.is_verified,
                "created_at": merchant.created_at.isoformat(),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
            })
        
        return {
            "merchants": merchants,
            "pagination": {
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        }, 200
    except Exception as e:
        current_app.logger.error(f"Get all merchants error: {str(e)}")
        return {"error": "Failed to get merchants"}, 500