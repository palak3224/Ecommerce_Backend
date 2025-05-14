from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class ProductMeta(BaseModel):
    __tablename__ = 'product_meta'
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    short_desc    = db.Column(db.String(255))
    full_desc     = db.Column(db.Text)
    meta_title    = db.Column(db.String(100))
    meta_desc     = db.Column(db.String(255))
    meta_keywords = db.Column(db.String(255))
    product       = db.relationship('Product', backref=db.backref('meta', uselist=False))
