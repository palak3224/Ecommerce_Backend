from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand

class Product(BaseModel):
    __tablename__ = 'products'
    product_id    = db.Column(db.Integer, primary_key=True)
    merchant_id   = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    category_id   = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    brand_id      = db.Column(db.Integer, db.ForeignKey('brands.brand_id'), nullable=False)
    sku           = db.Column(db.String(50), unique=True, nullable=False)
    product_name  = db.Column(db.String(255), nullable=False)
    product_description = db.Column(db.Text, nullable=False)
    cost_price    = db.Column(db.Numeric(10,2), nullable=False)
    selling_price = db.Column(db.Numeric(10,2), nullable=False)
    discount_pct  = db.Column(db.Numeric(5,2), default=0.00)
    special_price = db.Column(db.Numeric(10,2), nullable=True)
    special_start = db.Column(db.Date)
    special_end   = db.Column(db.Date)
    active_flag   = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at    = db.Column(db.DateTime)

    merchant      = db.relationship('MerchantProfile', backref='products')
    category      = db.relationship('Category', backref='products')
    brand         = db.relationship('Brand', backref='products')
    product_attributes = db.relationship('ProductAttribute', backref='product', cascade='all, delete-orphan')

    def serialize(self):
        return {
            "product_id":      self.product_id,
            "merchant_id":     self.merchant_id,
            "category_id":     self.category_id,
            "brand_id":        self.brand_id,
            "sku":             self.sku,
            "product_name":    self.product_name,
            "product_description": self.product_description,
            "cost_price":      float(self.cost_price),
            "selling_price":   float(self.selling_price),
            "discount_pct":    float(self.discount_pct),
            "special_price":   float(self.special_price) if self.special_price is not None else None,
            "special_start":   self.special_start.isoformat() if self.special_start else None,
            "special_end":     self.special_end.isoformat() if self.special_end else None,
            "active_flag":     bool(self.active_flag),
            "created_at":      self.created_at.isoformat() if self.created_at else None,
            "updated_at":      self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at":      self.deleted_at.isoformat() if self.deleted_at else None,
            "attributes":      [attr.serialize() for attr in self.product_attributes] if self.product_attributes else []
        }