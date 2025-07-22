
# models/shop/shop_product_attribute.py
from datetime import datetime, timezone
from common.database import db, BaseModel

class ShopProductAttribute(BaseModel):
    __tablename__ = 'shop_product_attributes'
    
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    product_id    = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), nullable=False)
    attribute_id  = db.Column(db.Integer, db.ForeignKey('shop_attributes.attribute_id'), nullable=False)
    value_id      = db.Column(db.Integer, db.ForeignKey('shop_attribute_values.value_id'), nullable=True)
    
    value_code    = db.Column(db.String(50), nullable=True)
    value_text    = db.Column(db.String(255), nullable=True)
    value_number  = db.Column(db.Float,   nullable=True)

    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'attribute_id', name='uq_shop_product_attribute'),
    )

    # Relationships to shop-specific models  
    attribute_value = db.relationship('ShopAttributeValue', foreign_keys=[value_id])
    
    def serialize(self):
        val = None
        if self.attribute.attribute_type.value == 'SELECT' or self.attribute.attribute_type.value == 'MULTISELECT':
            val = self.value_code
        elif self.attribute.attribute_type.value == 'NUMBER':
            val = self.value_number
        else:
            val = self.value_text
        
        return {
            "id": self.id,
            "product_id": self.product_id,
            "attribute_id": self.attribute_id,
            "value_id": self.value_id,
            "value": val,
            "attribute": self.attribute.serialize() if self.attribute else None,
            "attribute_value": self.attribute_value.serialize() if self.attribute_value else None,
        }
