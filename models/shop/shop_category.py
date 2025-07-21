from datetime import datetime, timezone
from common.database import db, BaseModel

class ShopCategory(BaseModel):
    __tablename__ = 'shop_categories'

    category_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('shop_categories.category_id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon_url = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Unique constraint per shop
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'name', name='unique_shop_category_name'),
        db.UniqueConstraint('shop_id', 'slug', name='unique_shop_category_slug'),
    )

    # Relationships
    parent = db.relationship('ShopCategory', remote_side=[category_id], backref='children')
    brands = db.relationship('ShopBrand', backref='category', cascade='all, delete-orphan')
    attributes = db.relationship('ShopAttribute', backref='category', cascade='all, delete-orphan')
    products = db.relationship('ShopProduct', backref='category', cascade='all, delete-orphan')

    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'category_id': self.category_id,
            'shop_id': self.shop_id,
            'shop_name': self.shop.name if self.shop else None,
            'parent_id': self.parent_id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'icon_url': self.icon_url,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'children': [child.serialize() for child in self.children] if self.children else []
        }
