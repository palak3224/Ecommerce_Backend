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