from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile, User
from models.enums import BrandRequestStatus

class BrandRequest(BaseModel):
    __tablename__ = 'brand_requests'
    request_id   = db.Column(db.Integer, primary_key=True)
    merchant_id  = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    name         = db.Column(db.String(100), nullable=False)
    status       = db.Column(db.Enum(BrandRequestStatus), default=BrandRequestStatus.PENDING, nullable=False)
    reviewer_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at  = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at   = db.Column(db.DateTime)

    merchant     = db.relationship('MerchantProfile', backref='brand_requests')
    reviewer     = db.relationship('User', foreign_keys=[reviewer_id])
    
    def serialize(self):
        return {
            "request_id":    self.request_id,
            "merchant_id":   self.merchant_id,
            "name":          self.name,
            "status":        self.status.value,
            "reviewer_id":   self.reviewer_id,
            "requested_at":  self.requested_at.isoformat() if self.requested_at else None,
            "reviewed_at":   self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "updated_at":    self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at":    self.deleted_at.isoformat() if self.deleted_at else None,
            
        }