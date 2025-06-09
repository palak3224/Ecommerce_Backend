from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
from models.enums import MediaType

class ReviewImage(BaseModel):
    __tablename__ = 'review_images'
    
    image_id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.review_id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    public_id = db.Column(db.String(255), nullable=True)  # Add public_id field for Cloudinary
    sort_order = db.Column(db.Integer, default=0)
    type = db.Column(db.Enum(MediaType), default=MediaType.IMAGE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    review = db.relationship('Review', back_populates='images')
    
    def serialize(self):
        return {
            'image_id': self.image_id,
            'review_id': self.review_id,
            'image_url': self.image_url,
            'public_id': self.public_id,  # Include public_id in serialization
            'sort_order': self.sort_order,
            'type': self.type.value if self.type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Review(BaseModel):
    __tablename__ = 'reviews'
    
    review_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.String(50), db.ForeignKey('orders.order_id'), nullable=False)  # Add order_id to link review to order
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime)
    
    product = db.relationship('Product', backref='reviews')
    user = db.relationship('User', backref='reviews')
    order = db.relationship('Order', backref='reviews')  # Add relationship to Order
    images = db.relationship('ReviewImage', back_populates='review', cascade='all, delete-orphan')
    
    def serialize(self, include_images=True):
        data = {
            'review_id': self.review_id,
            'product_id': self.product_id,
            'user_id': self.user_id,
            'order_id': self.order_id,
            'rating': self.rating,
            'title': self.title,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'user': {
                'id': self.user.id,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'email': self.user.email
            } if self.user else None,
            'product': {
                'product_id': self.product.product_id,
                'name': self.product.product_name,
                'sku': self.product.sku
            } if self.product else None,
            'images': []  # Initialize empty images array
        }
        
        if include_images and self.images:
            # Sort images by sort_order and serialize them
            sorted_images = sorted(self.images, key=lambda x: x.sort_order)
            data['images'] = [image.serialize() for image in sorted_images]
            
        return data