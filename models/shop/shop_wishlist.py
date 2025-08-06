from datetime import datetime, timezone
from common.database import db, BaseModel
from models.shop.shop_product import ShopProduct
from auth.models.models import User

class ShopWishlistItem(BaseModel):
    __tablename__ = 'shop_wishlist_items'

    wishlist_item_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id', ondelete='CASCADE'), nullable=False)
    shop_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id', ondelete='CASCADE'), nullable=False)
    
    # Store product details at time of adding to wishlist
    product_name = db.Column(db.String(255), nullable=False)
    product_sku = db.Column(db.String(50), nullable=False)
    product_price = db.Column(db.Numeric(10, 2), nullable=False)
    product_discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    product_special_price = db.Column(db.Numeric(10, 2), nullable=True)
    product_image_url = db.Column(db.String(255), nullable=True)
    product_stock_qty = db.Column(db.Integer, nullable=False)
    
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships - keep these for reference but we'll use stored values
    user = db.relationship('User', backref='shop_wishlist_items')
    shop_product = db.relationship('ShopProduct', backref='wishlist_items')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'shop_id', 'shop_product_id', name='uq_user_shop_product_wishlist'),
    )

    @classmethod
    def create_from_shop_product(cls, user_id, shop_product):
        """Create a wishlist item from a shop product, storing all relevant details"""
        # Get the primary image from shop product media
        main_image = None
        if hasattr(shop_product, 'media') and shop_product.media:
            # First, try to get the primary image
            primary_image = next(
                (media for media in shop_product.media 
                 if media.type.value == 'image' and media.is_primary and media.deleted_at is None), 
                None
            )
            
            if primary_image:
                main_image = primary_image.url
            else:
                # If no primary image, get the first available image
                first_image = next(
                    (media for media in shop_product.media 
                     if media.type.value == 'image' and media.deleted_at is None), 
                    None
                )
                main_image = first_image.url if first_image else None
        
        # Get stock quantity (if stock relationship exists)
        stock_qty = getattr(shop_product, 'stock', None).stock_qty if hasattr(shop_product, 'stock') and shop_product.stock else 0
        
        # Get product data with proper price calculations
        product_data = shop_product.serialize(include_variants=False)
        
        return cls(
            user_id=user_id,
            shop_id=shop_product.shop_id,
            shop_product_id=shop_product.product_id,
            product_name=shop_product.product_name,
            product_sku=shop_product.sku,
            product_price=product_data.get('price', shop_product.selling_price),
            product_discount_pct=shop_product.discount_pct,
            product_special_price=shop_product.special_price,
            product_image_url=main_image,
            product_stock_qty=stock_qty
        )

    @classmethod
    def get_user_shop_wishlist(cls, user_id, shop_id):
        """Get all wishlist items for a specific user and shop"""
        return cls.query.filter_by(
            user_id=user_id,
            shop_id=shop_id,
            is_deleted=False
        ).order_by(cls.added_at.desc()).all()

    @classmethod
    def check_item_in_wishlist(cls, user_id, shop_id, shop_product_id):
        """Check if a product is already in user's wishlist for a specific shop"""
        return cls.query.filter_by(
            user_id=user_id,
            shop_id=shop_id,
            shop_product_id=shop_product_id,
            is_deleted=False
        ).first() is not None

    @classmethod
    def get_wishlist_item(cls, user_id, shop_id, wishlist_item_id):
        """Get a specific wishlist item for a user in a shop"""
        return cls.query.filter_by(
            wishlist_item_id=wishlist_item_id,
            user_id=user_id,
            shop_id=shop_id,
            is_deleted=False
        ).first()

    def __repr__(self):
        return f"<ShopWishlistItem id={self.wishlist_item_id} user={self.user_id} shop_product={self.shop_product_id}>"

    def serialize(self):
        return {
            "wishlist_item_id": self.wishlist_item_id,
            "user_id": self.user_id,
            "shop_id": self.shop_id,
            "shop_product_id": self.shop_product_id,
            "product": {
                "name": self.product_name,
                "sku": self.product_sku,
                "price": float(self.product_price),
                "discount_pct": float(self.product_discount_pct),
                "special_price": float(self.product_special_price) if self.product_special_price else None,
                "image_url": self.product_image_url,
                "stock": self.product_stock_qty
            },
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted
        }
