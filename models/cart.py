# models/cart.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from decimal import Decimal

class Cart(BaseModel):
    __tablename__ = 'carts'

    cart_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True) 
    
    

    user = db.relationship('User', back_populates='cart')
    items = db.relationship('CartItem', back_populates='cart', cascade='all, delete-orphan', lazy='joined', order_by='CartItem.added_at')

    def __repr__(self):
        return f"<Cart id={self.cart_id} user_id={self.user_id}>"

    @property
    def subtotal(self):
        current_items = self.items if self.items is not None else []
        return sum((item.price_at_addition * item.quantity for item in current_items), Decimal('0.00'))
    
    @property
    def total_items_count(self):
        current_items = self.items if self.items is not None else []
        return sum(item.quantity for item in current_items)

    def serialize(self, include_items=True):
        data = {
            "cart_id": self.cart_id,
            "user_id": self.user_id,
            "subtotal": str(self.subtotal), 
            "total_items_count": self.total_items_count, 
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }
        if include_items:
            current_items = self.items if self.items is not None else []
            data["items"] = [item.serialize() for item in current_items]
        return data

class CartItem(BaseModel): 
    __tablename__ = 'cart_items'

    cart_item_id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.cart_id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id', ondelete='CASCADE'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('variants.variant_id', ondelete='CASCADE'), nullable=False) 
    
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_addition = db.Column(db.Numeric(10, 2), nullable=False) 
    
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Product', lazy='joined') 
    variant = db.relationship('Variant', lazy='joined') 

    __table_args__ = (
        db.UniqueConstraint('cart_id', 'variant_id', name='uq_cart_variant_item'),
    )

    def __repr__(self):
        return f"<CartItem id={self.cart_item_id} cart_id={self.cart_id} variant_id={self.variant_id} qty={self.quantity}>"

    @property
    def line_total(self):
        return self.price_at_addition * self.quantity

    def serialize(self):
        product_name = self.product.name if self.product and hasattr(self.product, 'name') else "N/A"
        variant_sku = self.variant.sku if self.variant and hasattr(self.variant, 'sku') else "N/A"
        variant_display_name = self.variant.get_display_name() if self.variant and hasattr(self.variant, 'get_display_name') else "N/A"
        
        image_url = None
        
        if self.variant and hasattr(self.variant, 'main_image_url'): # Assuming Variant might have a main_image_url property/field
            image_url = self.variant.main_image_url
        elif self.product and hasattr(self.product, 'default_image_url'): # Assuming Product might have a default_image_url
            image_url = self.product.default_image_url
            
        return {
            "cart_item_id": self.cart_item_id,
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "quantity": self.quantity,
            "price_at_addition": str(self.price_at_addition),
            "line_total": str(self.line_total), # Use property
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "product_name": product_name,
            "variant_display_name": variant_display_name,
            "sku": variant_sku,
            "image_url": image_url, # You'll need logic to fetch this from ProductMedia or a main image field
        }