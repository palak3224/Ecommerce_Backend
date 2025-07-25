# models/shop/shop_product_variant.py
from datetime import datetime, timezone
from common.database import db, BaseModel
import json

class ShopProductVariant(BaseModel):
    """
    Enhanced variant model for better performance and industry best practices.
    This supplements the existing parent-child product relationship.
    """
    __tablename__ = 'shop_product_variants'

    variant_id = db.Column(db.Integer, primary_key=True)
    parent_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), nullable=False)
    variant_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), nullable=False)
    
    # Variant-specific fields (optimized for queries)
    variant_sku = db.Column(db.String(100), unique=True, nullable=False)
    variant_name = db.Column(db.String(255), nullable=True)  # Optional: "Red - Large", "32GB - Blue"
    
    # Attribute combination (JSON for flexible storage)
    attribute_combination = db.Column(db.JSON, nullable=False)  # {"color": "red", "size": "L", "storage": "32GB"}
    
    # Variant-specific overrides (only if different from parent)
    price_override = db.Column(db.Numeric(10,2), nullable=True)
    cost_override = db.Column(db.Numeric(10,2), nullable=True)
    
    # Display order for frontend
    sort_order = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)  # One variant per parent should be default
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    parent_product = db.relationship('ShopProduct', foreign_keys=[parent_product_id], backref='variant_relations')
    variant_product = db.relationship('ShopProduct', foreign_keys=[variant_product_id], backref='variant_info')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_parent_product', 'parent_product_id'),
        db.Index('idx_variant_product', 'variant_product_id'),
        db.Index('idx_variant_sku', 'variant_sku'),
        db.Index('idx_attribute_combination', 'attribute_combination'),
    )
    
    def generate_variant_sku(self, parent_sku, attributes):
        """
        Generate variant SKU following industry standards:
        PARENT-SKU-ATTR1-ATTR2-ATTR3
        Example: SH01-TEE-2024-RED-L-COT
        """
        # Get attribute values and create short codes
        attr_codes = []
        for key, value in attributes.items():
            if isinstance(value, str):
                # Create 2-3 character codes from attribute values
                code = value.upper()[:3]
                attr_codes.append(code)
        
        variant_suffix = '-'.join(attr_codes)
        return f"{parent_sku}-{variant_suffix}"
    
    def get_effective_price(self):
        """Get the effective price (override or parent price)"""
        if self.price_override:
            return self.price_override
        return self.variant_product.selling_price if self.variant_product else 0
    
    def get_effective_cost(self):
        """Get the effective cost (override or parent cost)"""
        if self.cost_override:
            return self.cost_override
        return self.variant_product.cost_price if self.variant_product else 0
    
    def serialize(self):
        return {
            "variant_id": self.variant_id,
            "parent_product_id": self.parent_product_id,
            "variant_product_id": self.variant_product_id,
            "variant_sku": self.variant_sku,
            "variant_name": self.variant_name,
            "attribute_combination": self.attribute_combination,
            "effective_price": float(self.get_effective_price()),
            "effective_cost": float(self.get_effective_cost()),
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "stock": self.variant_product.stock.serialize() if self.variant_product and hasattr(self.variant_product, 'stock') else None,
            "media": [media.serialize() for media in self.variant_product.media] if self.variant_product else [],
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ShopVariantAttributeValue(BaseModel):
    """
    Normalized table for variant attribute values - better for filtering and queries
    """
    __tablename__ = 'shop_variant_attribute_values'
    
    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('shop_product_variants.variant_id'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('shop_attributes.attribute_id'), nullable=False)
    value_id = db.Column(db.Integer, db.ForeignKey('shop_attribute_values.value_id'), nullable=True)
    value_text = db.Column(db.String(255), nullable=True)  # For custom values
    
    # Relationships
    variant = db.relationship('ShopProductVariant', backref='attribute_values')
    attribute = db.relationship('ShopAttribute')
    attribute_value = db.relationship('ShopAttributeValue')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('variant_id', 'attribute_id', name='uq_variant_attribute'),
        db.Index('idx_variant_attr', 'variant_id', 'attribute_id'),
    )
    
    def serialize(self):
        return {
            "id": self.id,
            "variant_id": self.variant_id,
            "attribute_id": self.attribute_id,
            "attribute_name": self.attribute.name if self.attribute else None,
            "value_id": self.value_id,
            "value_text": self.value_text or (self.attribute_value.value if self.attribute_value else None),
            "display_value": self.attribute_value.display_name if self.attribute_value else self.value_text
        }
