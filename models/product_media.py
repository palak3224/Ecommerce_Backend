from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
from models.enums import MediaType


class ProductMedia(BaseModel):
    __tablename__ = 'product_media'
    media_id      = db.Column(db.Integer, primary_key=True)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    type          = db.Column(db.Enum(MediaType), nullable=False)
    url           = db.Column(db.String(255), nullable=False)
    sort_order    = db.Column(db.Integer, default=0, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at    = db.Column(db.DateTime)
    product       = db.relationship('Product', backref='media')