from datetime import datetime, timezone
from common.database import db, BaseModel

class WishlistItem(BaseModel):
    __tablename__ = 'wishlist_items'

    
    wishlist_item_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id', ondelete='CASCADE'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('variants.variant_id', ondelete='CASCADE'), nullable=False) 
    
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


    user = db.relationship('User',  back_populates='wishlist_items')
    product = db.relationship('Product', lazy='joined') 
    variant = db.relationship('Variant', lazy='joined') 

    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', 'variant_id', name='uq_user_product_variant_wishlist'),
    )

    def __repr__(self):
        return f"<WishlistItem id={self.wishlist_item_id} user={self.user_id} variant={self.variant_id}>"

    def serialize(self):
       
        product_summary = None
        variant_summary = None

        if self.product:
            product_summary = {
                "product_id": self.product.product_id,
                "name": getattr(self.product, 'name', "N/A"), # Assuming Product model has 'name'
                # "slug": getattr(self.product, 'slug', None),
                # "main_image_url": getattr(self.product, 'main_image_url', None) # Get from product_media
            }
        if self.variant:
            variant_summary = self.variant.serialize(include_options=True) 

        return {
            "wishlist_item_id": self.wishlist_item_id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "product_details": product_summary,
            "variant_details": variant_summary
        }