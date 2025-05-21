from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand

class ProductAttribute(BaseModel):
    __tablename__ = 'product_attributes'
    
    # Primary key columns
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    attribute_id  = db.Column(db.Integer, db.ForeignKey('attributes.attribute_id'), primary_key=True)
    value_code    = db.Column(db.String(50), primary_key=True, nullable=True)  # Made nullable since it's not always required
    value_text    = db.Column(db.String(255), nullable=True)
    
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['attribute_id', 'value_code'],
            ['attribute_values.attribute_id', 'attribute_values.value_code'],
            ondelete='CASCADE'
        ),
        {}
    )
    
    # Relationships
    attribute = db.relationship('Attribute', foreign_keys=[attribute_id])
    attribute_value = db.relationship('AttributeValue',
        primaryjoin="and_(ProductAttribute.attribute_id==AttributeValue.attribute_id, "
                    "ProductAttribute.value_code==AttributeValue.value_code)",
        foreign_keys=[attribute_id, value_code],
        overlaps="attribute"
    )
    
    # models/product_attribute.py
    def serialize(self):
        return {
            "product_id": self.product_id,
            "attribute_id": self.attribute_id,
            "value_code": self.value_code,
            "value_text": self.value_text,
            "attribute": self.attribute.serialize() if self.attribute else None,
            "attribute_value": self.attribute_value.serialize() if self.attribute_value else None,
            "is_text_based": self.value_code.startswith('text_') if self.value_code else False
        }
