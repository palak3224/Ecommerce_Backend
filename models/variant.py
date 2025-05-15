from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class Variant(BaseModel):
    __tablename__ = 'variants'
    variant_id    = db.Column(db.Integer, primary_key=True)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    attribute     = db.Column(db.String(50), nullable=False)
    value         = db.Column(db.String(50), nullable=False)
    sku           = db.Column(db.String(60), unique=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at    = db.Column(db.DateTime)
    product       = db.relationship('Product', backref='variants')
    # models/variant.py
    def serialize(self):
        return {
            "variant_id": self.variant_id,
            "product_id": self.product_id,
            "attribute": self.attribute,
            "value": self.value,
            "sku": self.sku,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }
