from datetime import datetime, timezone
from common.database import db, BaseModel

class VariantMedia(BaseModel):
    __tablename__ = 'variant_media'
    
    media_id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('variants.variant_id'), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)  # image, video, etc.
    media_url = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationship with Variant
    variant = db.relationship('Variant', backref='media')

    def serialize(self):
        return {
            "media_id": self.media_id,
            "variant_id": self.variant_id,
            "media_type": self.media_type,
            "media_url": self.media_url,
            "is_primary": self.is_primary,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        } 