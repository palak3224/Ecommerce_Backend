from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import User

class Brand(BaseModel):
    __tablename__ = 'brands'
    brand_id    = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    slug        = db.Column(db.String(100), unique=True, nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at  = db.Column(db.DateTime)

    approver    = db.relationship('User', foreign_keys=[approved_by])