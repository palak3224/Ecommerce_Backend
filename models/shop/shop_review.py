from datetime import datetime
from common.database import db, BaseModel
from models.enums import MediaType


class ShopReviewImage(BaseModel):
    __tablename__ = 'shop_review_images'

    image_id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('shop_reviews.review_id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False)
    public_id = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    type = db.Column(db.Enum(MediaType), default=MediaType.IMAGE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    review = db.relationship('ShopReview', back_populates='images')

    def serialize(self):
        return {
            'image_id': self.image_id,
            'review_id': self.review_id,
            'image_url': self.image_url,
            'public_id': self.public_id,
            'sort_order': self.sort_order,
            'type': self.type.value if self.type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ShopReview(BaseModel):
    __tablename__ = 'shop_reviews'

    review_id = db.Column(db.Integer, primary_key=True)
    shop_product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id', ondelete='CASCADE'), nullable=False, index=True)
    shop_order_id = db.Column(db.String(50), db.ForeignKey('shop_orders.order_id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=True)
    body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # relationships
    product = db.relationship('ShopProduct', backref='reviews')
    user = db.relationship('User', backref='shop_reviews')
    order = db.relationship('ShopOrder', backref='reviews')
    images = db.relationship('ShopReviewImage', back_populates='review', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('shop_order_id', 'shop_product_id', name='uq_shop_review_order_product'),
    )

    def serialize(self, include_images=True):
        data = {
            'review_id': self.review_id,
            'shop_product_id': self.shop_product_id,
            'user_id': self.user_id,
            'shop_order_id': self.shop_order_id,
            'rating': self.rating,
            'title': self.title,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'user': {
                'id': self.user.id if self.user else None,
                'first_name': getattr(self.user, 'first_name', '') if self.user else '',
                'last_name': getattr(self.user, 'last_name', '') if self.user else '',
                'email': getattr(self.user, 'email', '') if self.user else '',
            } if self.user else None,
            'images': []
        }

        if include_images and self.images:
            data['images'] = [img.serialize() for img in sorted(self.images, key=lambda x: x.sort_order)]

        return data
