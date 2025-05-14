from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class VariantStock(BaseModel):
    __tablename__ = 'variant_stock'
    variant_id          = db.Column(db.Integer, db.ForeignKey('variants.variant_id'), primary_key=True)
    stock_qty           = db.Column(db.Integer, default=0, nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=0, nullable=False)
    pending_qty         = db.Column(db.Integer, default=0, nullable=False)
    reserved_qty        = db.Column(db.Integer, default=0, nullable=False)
    variant             = db.relationship('Variant', backref=db.backref('stock', uselist=False))