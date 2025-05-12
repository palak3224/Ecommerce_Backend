import enum
from datetime import datetime

from common.database import db, BaseModel

class DocumentType(enum.Enum):
    """Types of documents required for merchant verification."""
    BUSINESS_REGISTRATION = 'business_registration'
    PAN_CARD = 'pan_card'
    GSTIN = 'gstin'
    ADDRESS_PROOF = 'address_proof'
    IDENTITY_PROOF = 'identity_proof'
    CANCELLED_CHEQUE = 'cancelled_cheque'
    BRAND_AUTHORIZATION = 'brand_authorization'
    PRODUCT_IMAGES = 'product_images'
    GST_CERTIFICATE = 'gst_certificate'
    MSME_CERTIFICATE = 'msme_certificate'
    DIGITAL_SIGNATURE = 'digital_signature'
    RETURN_POLICY = 'return_policy'
    SHIPPING_DETAILS = 'shipping_details'
    OTHER = 'other'

class VerificationStatus(enum.Enum):
    """Status of merchant verification."""
    PENDING = 'pending'
    EMAIL_VERIFIED = 'email_verified'
    DOCUMENTS_SUBMITTED = 'documents_submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class DocumentStatus(enum.Enum):
    """Status of merchant document verification."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class MerchantDocument(BaseModel):
    """Merchant document model for storing verification documents."""
    __tablename__ = 'merchant_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)
    document_type = db.Column(db.Enum(DocumentType), nullable=False)
    public_id = db.Column(db.String(255), nullable=False)  # Cloudinary public ID
    file_url = db.Column(db.String(255), nullable=False)  # Cloudinary secure URL
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    mime_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    admin_notes = db.Column(db.Text, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', back_populates='documents')
    verified_by_user = db.relationship('User', foreign_keys=[verified_by])
    
    @classmethod
    def get_by_id(cls, id):
        """Get a document by ID."""
        return cls.query.filter_by(id=id).first()
    
    @classmethod
    def get_by_merchant_id(cls, merchant_id):
        """Get all documents for a merchant."""
        return cls.query.filter_by(merchant_id=merchant_id).all()
    
    @classmethod
    def get_by_merchant_and_type(cls, merchant_id, document_type):
        """Get a specific document type for a merchant."""
        return cls.query.filter_by(
            merchant_id=merchant_id,
            document_type=document_type
        ).first()
    
    def approve(self, admin_id, notes=None):
        """Approve document."""
        self.status = DocumentStatus.APPROVED
        self.verified_at = datetime.utcnow()
        self.verified_by = admin_id
        if notes:
            self.admin_notes = notes
        db.session.commit()
    
    def reject(self, admin_id, notes=None):
        """Reject document."""
        self.status = DocumentStatus.REJECTED
        self.verified_at = datetime.utcnow()
        self.verified_by = admin_id
        if notes:
            self.admin_notes = notes
        db.session.commit()
    
    def delete(self):
        """Delete document and its associated Cloudinary file."""
        from auth.utils import delete_from_cloudinary
        if self.public_id:
            delete_from_cloudinary(self.public_id)
        db.session.delete(self)
        db.session.commit()