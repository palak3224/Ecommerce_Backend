from datetime import datetime, timezone
from common.database import db, BaseModel

class Shop(BaseModel):
    __tablename__ = 'shops'

    shop_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # ShipRocket integration fields
    shiprocket_pickup_location_id = db.Column(db.Integer, nullable=True)
    shiprocket_pickup_location_name = db.Column(db.String(255), nullable=True)

    # Relationships
    categories = db.relationship('ShopCategory', backref='shop', cascade='all, delete-orphan')
    brands = db.relationship('ShopBrand', backref='shop', cascade='all, delete-orphan')
    attributes = db.relationship('ShopAttribute', backref='shop', cascade='all, delete-orphan')
    products = db.relationship('ShopProduct', backref='shop', cascade='all, delete-orphan')

    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'shop_id': self.shop_id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'logo_url': self.logo_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'shiprocket_pickup_location_id': self.shiprocket_pickup_location_id,
            'shiprocket_pickup_location_name': self.shiprocket_pickup_location_name
        }
