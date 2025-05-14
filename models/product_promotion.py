from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class ProductPromotion(BaseModel):
    __tablename__ = 'product_promotions'
    product_id     = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    promotion_id   = db.Column(db.Integer, db.ForeignKey('promotions.promotion_id'), primary_key=True)
