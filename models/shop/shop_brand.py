from datetime import datetime, timezone
from common.database import db, BaseModel

class ShopBrand(BaseModel):
    __tablename__ = 'shop_brands'

    brand_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.category_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Unique constraint per shop and category
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'category_id', 'name', name='unique_shop_category_brand_name'),
        db.UniqueConstraint('shop_id', 'category_id', 'slug', name='unique_shop_category_brand_slug'),
    )

    # Relationships
    products = db.relationship('ShopProduct', backref='brand', cascade='all, delete-orphan')

    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'brand_id': self.brand_id,
            'shop_id': self.shop_id,
            'shop_name': self.shop.name if self.shop else None,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'logo_url': self.logo_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
