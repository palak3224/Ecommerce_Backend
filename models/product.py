# models/product.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand

from decimal import Decimal

import json


class Product(BaseModel):
    __tablename__ = 'products'

    product_id    = db.Column(db.Integer, primary_key=True)
    merchant_id   = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    category_id   = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    brand_id      = db.Column(db.Integer, db.ForeignKey('brands.brand_id'), nullable=False)
    parent_product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=True)
    sku           = db.Column(db.String(50), unique=True, nullable=False)
    product_name  = db.Column(db.String(255), nullable=False)
    product_description = db.Column(db.Text, nullable=False)
    
    cost_price    = db.Column(db.Numeric(10,2), nullable=False) 
    
    # selling_price is THE GST-INCLUSIVE price entered by the merchant.
    selling_price = db.Column(db.Numeric(10,2), nullable=False) 
    
    discount_pct  = db.Column(db.Numeric(5,2), default=0.00) # This discount is on some base, likely pre-GST. Calculation of this needs care.
                                                            # If merchant inputs inclusive price, how is discount_pct meant to be used?
                                                            # For now, assume it's informational or applied by merchant mentally before setting selling_price.

    # special_price is also GST-INCLUSIVE if a special offer is active.
    special_price = db.Column(db.Numeric(10,2), nullable=True) 
    special_start = db.Column(db.Date)
    special_end   = db.Column(db.Date)
    
    active_flag   = db.Column(db.Boolean, default=True, nullable=False)
    
    approval_status = db.Column(db.String(20), default='pending', nullable=False)
    approved_at     = db.Column(db.DateTime, nullable=True)
    approved_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at    = db.Column(db.DateTime)

    # REMOVED: base_price_calculated
    # REMOVED: gst_rate_percentage_applied

    merchant      = db.relationship('MerchantProfile', backref='products')
    category      = db.relationship('Category', backref='products')
    brand         = db.relationship('Brand', backref='products')
    product_attributes = db.relationship('ProductAttribute', backref='product', cascade='all, delete-orphan')
    cart_items    = db.relationship('CartItem', back_populates='product', cascade='all, delete-orphan')
    wishlist_items = db.relationship('WishlistItem', back_populates='product', cascade='all, delete-orphan')
    approved_by_admin = db.relationship('User', backref='approved_products', foreign_keys=[approved_by])
    
    parent = db.relationship('Product', remote_side=[product_id], backref='variants')

    # REMOVED: update_base_price_and_gst_details() method
    # REMOVED: get_effective_inclusive_price_and_base() - this logic moves to checkout/invoice calculation

    def get_current_listed_inclusive_price(self):
        """Returns the current GST-inclusive price (special or regular) listed by the merchant."""
        today = datetime.now(timezone.utc).date()
        is_on_special = False
        current_price = self.selling_price

        if self.special_price is not None and \
           (self.special_start is None or self.special_start <= today) and \
           (self.special_end is None or self.special_end >= today):
            current_price = self.special_price
            is_on_special = True
        return current_price, is_on_special

    def serialize(self):

        current_listed_inclusive_price, is_on_special = self.get_current_listed_inclusive_price()

        # The main price shown to users before cart.
        display_price = current_listed_inclusive_price

        # originalPrice is shown if there's a special offer active. It's the standard selling_price (inclusive).
        original_display_price = self.selling_price if is_on_special and self.selling_price != display_price else None

        # Process attributes to handle array format from variants
        def process_attributes(attributes):
            processed_attributes = []
            
            for attr in attributes:
                # Check if the value is in array format (from variants)
                if attr.value_text and attr.value_text.startswith('[') and attr.value_text.endswith(']'):
                    try:
                        # Parse the array string
                        values = json.loads(attr.value_text)
                        if isinstance(values, list):
                            # Create individual attributes for each value
                            for index, value in enumerate(values):
                                processed_attributes.append({
                                    "attribute_id": attr.attribute_id + index,  # Create unique IDs
                                    "attribute_name": attr.attribute.name,
                                    "value_code": attr.value_code,
                                    "value_text": str(value),
                                    "value_label": str(value),
                                    "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                    "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                })
                        else:
                            # If not a list, treat as regular attribute
                            processed_attributes.append(attr.serialize())
                    except (json.JSONDecodeError, ValueError):
                        # If parsing fails, treat as regular attribute
                        processed_attributes.append(attr.serialize())
                else:
                    # Regular attribute, no processing needed
                    processed_attributes.append(attr.serialize())
            
            return processed_attributes

        return {
            "product_id": self.product_id,
            "merchant_id": self.merchant_id,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,  # Added for convenience
            "brand_id": self.brand_id,
            "brand_name": self.brand.name if self.brand else None,  # Added for convenience
            "parent_product_id": self.parent_product_id,
            "sku": self.sku,
            "product_name": self.product_name,
            "product_description": self.product_description,
            "cost_price": float(self.cost_price) if self.cost_price is not None else None,

            # Merchant's standard GST-inclusive selling price
            "selling_price": float(self.selling_price) if self.selling_price is not None else None,

            # Merchant's special GST-inclusive price (if any)
            "special_price": float(self.special_price) if self.special_price is not None else None,
            "special_start": self.special_start.isoformat() if self.special_start else None,
            "special_end": self.special_end.isoformat() if self.special_end else None,
            "is_on_special_offer": is_on_special,

            "active_flag": bool(self.active_flag),
            "approval_status": self.approval_status,

            # Approval metadata
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,

            # Frontend pricing display
            "price": float(display_price) if display_price is not None else 0.0,
            "originalPrice": float(original_display_price) if original_display_price is not None else None,

            # Attributes, Variants, Stock
            "attributes": [attr.serialize() for attr in self.product_attributes] if self.product_attributes else [],
            "variants": [variant.serialize() for variant in self.variants] if self.variants else [],
            "stock": self.stock.serialize() if hasattr(self, 'stock') and self.stock else None
        }
