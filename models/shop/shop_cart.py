from datetime import datetime
from common.database import db, BaseModel
from models.shop.shop_product import ShopProduct
from models.shop.shop import Shop
from auth.models.models import User  # Assuming User model is here
import json

class ShopCart(BaseModel):
    __tablename__ = 'shop_carts'

    cart_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    items = db.relationship('ShopCartItem', backref='cart', cascade='all, delete-orphan')
    user = db.relationship('User', backref='shop_carts')
    shop = db.relationship('Shop', backref='carts')

    def serialize(self):
        return {
            'cart_id': self.cart_id,
            'user_id': self.user_id,
            'shop_id': self.shop_id,
            'items': [item.serialize() for item in self.items if not item.is_deleted],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_deleted': self.is_deleted
        }

class ShopCartItem(BaseModel):
    __tablename__ = 'shop_cart_items'

    cart_item_id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('shop_carts.cart_id'), nullable=False)
    shop_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    # Store product details at time of adding to cart
    product_name = db.Column(db.String(255), nullable=False)
    product_sku = db.Column(db.String(50), nullable=False)
    product_price = db.Column(db.Numeric(10, 2), nullable=False)
    product_discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    product_special_price = db.Column(db.Numeric(10, 2), nullable=True)
    product_image_url = db.Column(db.String(255), nullable=True)
    product_stock_qty = db.Column(db.Integer, nullable=False)
    # No merchant_id here

    # Store selected attributes as JSON
    selected_attributes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    shop_product = db.relationship('ShopProduct', backref='cart_items')

    @classmethod
    def create_from_shop_product(cls, cart_id, shop_product, quantity, selected_attributes=None):
        # Get the first product image (if media relationship exists)
        main_image = None
        if hasattr(shop_product, 'media') and shop_product.media:
            main_image = next((media.url for media in shop_product.media if getattr(media, 'type', None) == 'image'), None)
        # Get stock quantity (if stock relationship exists)
        stock_qty = getattr(shop_product, 'stock', None).stock_qty if hasattr(shop_product, 'stock') and shop_product.stock else 0
        product_data = shop_product.serialize(include_variants=False)
        return cls(
            cart_id=cart_id,
            shop_product_id=shop_product.product_id,
            quantity=quantity,
            product_name=shop_product.product_name,
            product_sku=shop_product.sku,
            product_price=product_data.get('price', shop_product.selling_price),
            product_discount_pct=shop_product.discount_pct,
            product_special_price=shop_product.special_price,
            product_image_url=main_image,
            product_stock_qty=stock_qty,
            selected_attributes=json.dumps(selected_attributes) if selected_attributes else None
        )

    def get_selected_attributes(self):
        if self.selected_attributes:
            try:
                return json.loads(self.selected_attributes)
            except json.JSONDecodeError:
                return {}
        return {}

    def serialize(self):
        original_price = self.product_price
        if self.product_special_price and self.product_special_price < self.product_price:
            if self.shop_product:
                product_data = self.shop_product.serialize(include_variants=False)
                original_price = product_data.get('originalPrice', self.shop_product.selling_price)
        return {
            'cart_item_id': self.cart_item_id,
            'cart_id': self.cart_id,
            'shop_product_id': self.shop_product_id,
            'quantity': self.quantity,
            'selected_attributes': self.get_selected_attributes(),
            'product': {
                'id': self.shop_product_id,
                'name': self.product_name,
                'sku': self.product_sku,
                'price': float(self.product_price),
                'original_price': float(original_price),
                'special_price': float(self.product_special_price) if self.product_special_price else None,
                'image_url': self.product_image_url,
                'stock': self.product_stock_qty,
                'is_deleted': False
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_deleted': self.is_deleted
        }
