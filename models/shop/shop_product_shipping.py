
# models/shop/shop_product_shipping.py
from datetime import datetime
from common.database import db, BaseModel

class ShopProductShipping(BaseModel):
    __tablename__ = 'shop_product_shipping'
    product_id    = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), primary_key=True)
    length_cm     = db.Column(db.Numeric(7,2))
    width_cm      = db.Column(db.Numeric(7,2))
    height_cm     = db.Column(db.Numeric(7,2))
    weight_kg     = db.Column(db.Numeric(7,3))
    shipping_class = db.Column(db.String(50), default='standard')
    
    product       = db.relationship('ShopProduct', backref=db.backref('shipping', uselist=False))
    
    def serialize(self):
        return {
            "product_id": self.product_id,
            "length_cm": float(self.length_cm) if self.length_cm else 0,
            "width_cm": float(self.width_cm) if self.width_cm else 0,
            "height_cm": float(self.height_cm) if self.height_cm else 0,
            "weight_kg": float(self.weight_kg) if self.weight_kg else 0,
            "shipping_class": self.shipping_class or 'standard'
        }
