

# models/shop/shop_product.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User  # Assuming superadmins are in the User table

from decimal import Decimal
import json

class ShopProduct(BaseModel):
    __tablename__ = 'shop_products'

    product_id    = db.Column(db.Integer, primary_key=True)
    shop_id       = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    category_id   = db.Column(db.Integer, db.ForeignKey('shop_categories.category_id'), nullable=False)
    brand_id      = db.Column(db.Integer, db.ForeignKey('shop_brands.brand_id'), nullable=True)
    parent_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), nullable=True)
    sku           = db.Column(db.String(50), unique=True, nullable=False)
    product_name  = db.Column(db.String(255), nullable=False)
    product_description = db.Column(db.Text, nullable=False)
    
    cost_price    = db.Column(db.Numeric(10,2), nullable=False) 
    selling_price = db.Column(db.Numeric(10,2), nullable=False) 
    
    discount_pct  = db.Column(db.Numeric(5,2), default=0.00)
    
    special_price = db.Column(db.Numeric(10,2), nullable=True) 
    special_start = db.Column(db.DateTime, nullable=True)
    special_end   = db.Column(db.DateTime, nullable=True)
    
    active_flag   = db.Column(db.Boolean, default=True, nullable=False)
    
    # Approval is handled by superadmin, so status is simpler.
    # Or we can keep the approval flow if superadmins also need to approve.
    # Assuming a simple "published" status for now.
    is_published   = db.Column(db.Boolean, default=False, nullable=False)
    
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at    = db.Column(db.DateTime)

    # No longer using the old category and brand relationships
    # Now using shop-specific relationships
    
    # Updated relationships for shop-specific models
    product_attributes = db.relationship('ShopProductAttribute', backref='product', cascade='all, delete-orphan')
    
    parent = db.relationship('ShopProduct', remote_side=[product_id], backref='variants')

    def get_current_listed_inclusive_price(self):
        """Returns the current GST-inclusive price (special or regular)."""
        today = datetime.now(timezone.utc).date()
        is_on_special = False
        current_price = self.selling_price

        if self.special_price is not None and \
           (self.special_start is None or self.special_start <= today) and \
           (self.special_end is None or self.special_end >= today):
            current_price = self.special_price
            is_on_special = True
        return current_price, is_on_special

    def is_parent_product(self):
        """Check if this product is a parent (has variants)"""
        return self.parent_product_id is None and len(self.variants) > 0
    
    def is_variant_product(self):
        """Check if this product is a variant"""
        return self.parent_product_id is not None
    
    def is_simple_product(self):
        """Check if this product is a simple product (no variants)"""
        return self.parent_product_id is None and len(self.variants) == 0
    
    def get_all_variants(self, include_inactive=False):
        """Get all variants with optional filtering"""
        if include_inactive:
            return self.variants
        return [v for v in self.variants if v.active_flag]
    
    def get_default_variant(self):
        """Get the default variant for display"""
        if not self.variants:
            return None
        # Look for explicitly marked default variant
        for variant in self.variants:
            if hasattr(variant, 'variant_info') and variant.variant_info and variant.variant_info[0].is_default:
                return variant
        # Return first active variant as fallback
        return next((v for v in self.variants if v.active_flag), None)
    
    def get_price_range(self):
        """Get min/max price range for products with variants"""
        if not self.variants:
            current_price, _ = self.get_current_listed_inclusive_price()
            return {"min": float(current_price), "max": float(current_price)}
        
        prices = []
        for variant in self.variants:
            if variant.active_flag:
                variant_price, _ = variant.get_current_listed_inclusive_price()
                prices.append(float(variant_price))
        
        if not prices:
            current_price, _ = self.get_current_listed_inclusive_price()
            return {"min": float(current_price), "max": float(current_price)}
        
        return {"min": min(prices), "max": max(prices)}
    
    def get_available_attributes(self):
        """Get all possible attribute combinations from variants"""
        if not self.variants:
            return {}
        
        attributes = {}
        for variant in self.variants:
            if variant.active_flag:
                for attr in variant.product_attributes:
                    attr_name = attr.attribute.name
                    if attr_name not in attributes:
                        attributes[attr_name] = set()
                    
                    # Add the value to the set
                    if attr.value_text:
                        attributes[attr_name].add(attr.value_text)
                    elif attr.attribute_value:
                        attributes[attr_name].add(attr.attribute_value.value)
        
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in attributes.items()}

    def serialize(self, include_variants=True, variant_summary_only=False):
        current_listed_inclusive_price, is_on_special = self.get_current_listed_inclusive_price()
        display_price = current_listed_inclusive_price
        original_display_price = self.selling_price if is_on_special and self.selling_price != display_price else None
        
        # Basic product data
        data = {
            "product_id": self.product_id,
            "shop_id": self.shop_id,
            "shop_name": self.shop.name if self.shop else None,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "brand_id": self.brand_id,
            "brand_name": self.brand.name if self.brand else None,
            "parent_product_id": self.parent_product_id,
            "sku": self.sku,
            "product_name": self.product_name,
            "product_description": self.product_description,
            "cost_price": float(self.cost_price) if self.cost_price is not None else None,
            "selling_price": float(self.selling_price) if self.selling_price is not None else None,
            "special_price": float(self.special_price) if self.special_price is not None else None,
            "special_start": self.special_start.isoformat() if self.special_start else None,
            "special_end": self.special_end.isoformat() if self.special_end else None,
            "is_on_special_offer": is_on_special,
            "is_published": self.is_published,
            "active_flag": bool(self.active_flag),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "price": float(display_price) if display_price is not None else 0.0,
            "originalPrice": float(original_display_price) if original_display_price is not None else None,
            "attributes": [attr.serialize() for attr in self.product_attributes] if self.product_attributes else [],
            "stock": self.stock.serialize() if hasattr(self, 'stock') and self.stock else None,
            # Product type indicators
            "is_parent_product": self.is_parent_product(),
            "is_variant_product": self.is_variant_product(),
            "is_simple_product": self.is_simple_product(),
        }
        
        # Add variant-specific data
        if include_variants and self.variants:
            if variant_summary_only:
                # For listing pages - just count and price range
                data.update({
                    "variant_count": len([v for v in self.variants if v.active_flag]),
                    "price_range": self.get_price_range(),
                    "available_attributes": self.get_available_attributes(),
                    "default_variant": self.get_default_variant().serialize(include_variants=False) if self.get_default_variant() else None
                })
            else:
                # For detail pages - full variant data
                data.update({
                    "variants": [variant.serialize(include_variants=False) for variant in self.variants] if self.variants else [],
                    "variant_count": len([v for v in self.variants if v.active_flag]),
                    "price_range": self.get_price_range(),
                    "available_attributes": self.get_available_attributes()
                })
        else:
            data["variants"] = []
        
        return data

