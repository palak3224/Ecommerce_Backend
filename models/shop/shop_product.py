

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
    
    # Relationship to get variant relationships for this product as parent
    variant_relations = db.relationship('ShopProductVariant', foreign_keys='ShopProductVariant.parent_product_id', back_populates='parent_product')

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
        if not hasattr(self, 'variant_relations') or not self.variant_relations:
            return []
        
        if include_inactive:
            return [rel.variant_product for rel in self.variant_relations if rel.variant_product]
        return [rel.variant_product for rel in self.variant_relations if rel.variant_product and rel.variant_product.active_flag]
    
    def get_default_variant(self):
        """Get the default variant for display"""
        if not hasattr(self, 'variant_relations') or not self.variant_relations:
            return None
        
        # Look for explicitly marked default variant
        for relation in self.variant_relations:
            if relation.is_default and relation.variant_product and relation.variant_product.active_flag:
                return relation.variant_product
        
        # Return first active variant as fallback
        for relation in self.variant_relations:
            if relation.variant_product and relation.variant_product.active_flag:
                return relation.variant_product
        
        return None
    
    def get_price_range(self):
        """Get min/max price range for products with variants"""
        variants = self.get_all_variants()
        if not variants:
            current_price, _ = self.get_current_listed_inclusive_price()
            return {"min": float(current_price), "max": float(current_price)}
        
        prices = []
        for variant in variants:
            if variant.active_flag:
                variant_price, _ = variant.get_current_listed_inclusive_price()
                prices.append(float(variant_price))
        
        if not prices:
            current_price, _ = self.get_current_listed_inclusive_price()
            return {"min": float(current_price), "max": float(current_price)}
        
        return {"min": min(prices), "max": max(prices)}
    
    def get_available_attributes(self):
        """Get all possible attribute combinations from variants"""
        if not hasattr(self, 'variant_relations') or not self.variant_relations:
            return {}
        
        attributes = {}
        for relation in self.variant_relations:
            if relation.variant_product and relation.variant_product.active_flag:
                # Get attributes from the variant relation's attribute_combination
                if relation.attribute_combination:
                    for attr_name, attr_value in relation.attribute_combination.items():
                        if attr_name not in attributes:
                            attributes[attr_name] = set()
                        attributes[attr_name].add(str(attr_value))
        
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in attributes.items()}

    def get_variant_attributes_for_frontend(self):
        """Get variant attributes formatted for frontend Hero component"""
        variant_attributes = {}
        
        # For parent products, get available attributes from variants
        if self.is_parent_product():
            available_attrs = self.get_available_attributes()
            
            # Get parent product attributes to set as default selection
            parent_attrs = {}
            if self.product_attributes:
                for attr in self.product_attributes:
                    if attr.attribute and attr.attribute.name:
                        # Get the display value
                        if attr.value_id and attr.attribute_value:
                            parent_attrs[attr.attribute.name] = attr.attribute_value.value
                        elif attr.value_text:
                            parent_attrs[attr.attribute.name] = attr.value_text
                        elif attr.value_number is not None:
                            parent_attrs[attr.attribute.name] = str(attr.value_number)
            
            # Combine available variant options with parent defaults
            for attr_name, options in available_attrs.items():
                variant_attributes[attr_name] = {
                    'options': options,
                    'selected': parent_attrs.get(attr_name, options[0] if options else '')
                }
        
        return variant_attributes

    def get_variant_media_for_product(self, variant_product_id):
        """Get media for a specific variant product with fallback to parent media"""
        from models.shop.shop_product_media import ShopProductMedia
        from models.enums import MediaType
        
        # First, try to get variant-specific media
        variant_media = ShopProductMedia.query.filter_by(
            product_id=variant_product_id,
            deleted_at=None
        ).order_by(ShopProductMedia.sort_order).all()
        
        if variant_media:
            # Convert to the same format as parent media
            images = []
            videos = []
            primary_image = None
            
            for media in variant_media:
                media_item = {
                    'url': media.url,
                    'type': media.type.value if hasattr(media.type, 'value') else str(media.type),
                    'is_primary': media.is_primary
                }
                
                if media.type == MediaType.IMAGE:
                    images.append(media_item)
                    if media.is_primary:
                        primary_image = media.url
                elif media.type == MediaType.VIDEO:
                    videos.append(media_item)
            
            # If no primary image set, use first image
            if not primary_image and images:
                primary_image = images[0]['url']
                images[0]['is_primary'] = True
            
            return {
                'images': images,
                'videos': videos,
                'primary_image': primary_image,
                'total_media': len(variant_media)
            }
        else:
            # Fallback to parent media if no variant-specific media
            return self.media if hasattr(self, 'media') else {
                'images': [],
                'videos': [],
                'primary_image': None,
                'total_media': 0
            }

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
        variants = self.get_all_variants()
        if include_variants and variants:
            if variant_summary_only:
                # For listing pages - just count and price range
                data.update({
                    "variant_count": len([v for v in variants if v.active_flag]),
                    "price_range": self.get_price_range(),
                    "available_attributes": self.get_available_attributes(),
                    "variant_attributes": self.get_variant_attributes_for_frontend(),  # Frontend-formatted attributes
                    "default_variant": self.get_default_variant().serialize(include_variants=False) if self.get_default_variant() else None
                })
            else:
                # For detail pages - full variant data
                variants_data = []
                for variant in variants:
                    variant_data = variant.serialize(include_variants=False)
                    # Add media for variant products
                    if variant.is_variant_product():
                        # Get variant-specific media or fallback to parent media
                        variant_media = self.get_variant_media_for_product(variant.product_id)
                        variant_data['media'] = variant_media
                    variants_data.append(variant_data)
                
                data.update({
                    "variants": variants_data,
                    "variant_count": len([v for v in variants if v.active_flag]),
                    "price_range": self.get_price_range(),
                    "available_attributes": self.get_available_attributes(),
                    "variant_attributes": self.get_variant_attributes_for_frontend()  # Frontend-formatted attributes
                })
        else:
            data["variants"] = []
        
        return data

