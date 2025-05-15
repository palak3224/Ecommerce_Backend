from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class ProductTax(BaseModel):
    __tablename__ = 'product_tax'
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    tax_rate      = db.Column(db.Numeric(5,2), nullable=False)
    product       = db.relationship('Product', backref=db.backref('tax', uselist=False))
    # models/product_tax.py
    def serialize(self):
        return {
            "product_id": self.product_id,
            "tax_rate": str(self.tax_rate)
        }
