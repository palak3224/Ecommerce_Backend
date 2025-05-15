from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand

class ProductAttribute(BaseModel):
    __tablename__ = 'product_attributes'
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    attribute_id  = db.Column(db.Integer, db.ForeignKey('attributes.attribute_id'), primary_key=True)
    value_code    = db.Column(db.String(50), primary_key=True)
    value_text    = db.Column(db.String(255))
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['attribute_id', 'value_code'],
            ['attribute_values.attribute_id', 'attribute_values.value_code']
        ),
        {}
    )
    # models/product_attribute.py
    def serialize(self):
        return {
            "product_id": self.product_id,
            "attribute_id": self.attribute_id,
            "value_code": self.value_code,
            "value_text": self.value_text
        }
