from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class ProductShipping(BaseModel):
    __tablename__ = 'product_shipping'
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    length_cm     = db.Column(db.Numeric(7,2))
    width_cm      = db.Column(db.Numeric(7,2))
    height_cm     = db.Column(db.Numeric(7,2))
    weight_kg     = db.Column(db.Numeric(7,3))
    product       = db.relationship('Product', backref=db.backref('shipping', uselist=False))
    # models/product_shipping.py
    def serialize(self):
        return {
            "product_id": self.product_id,
            "length_cm": str(self.length_cm),
            "width_cm": str(self.width_cm),
            "height_cm": str(self.height_cm),
            "weight_kg": str(self.weight_kg)
        }
