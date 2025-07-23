from datetime import datetime, timezone
from common.database import db, BaseModel
from models.enums import AttributeInputType

class ShopAttribute(BaseModel):
    __tablename__ = 'shop_attributes'

    attribute_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.category_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    attribute_type = db.Column(db.Enum(AttributeInputType), nullable=False)
    is_required = db.Column(db.Boolean, default=False)
    is_filterable = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Unique constraint per shop and category
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'category_id', 'name', name='unique_shop_category_attribute_name'),
        db.UniqueConstraint('shop_id', 'category_id', 'slug', name='unique_shop_category_attribute_slug'),
    )

    # Relationships
    attribute_values = db.relationship('ShopAttributeValue', backref='attribute', cascade='all, delete-orphan')
    product_attributes = db.relationship('ShopProductAttribute', backref='attribute', cascade='all, delete-orphan')

    def serialize(self, active_values_only=False):
        """Return object data in easily serializable format"""
        # Include both active and inactive values by default, but filter out hard-deleted ones
        if active_values_only:
            # For product forms, only show active values
            available_values = [value for value in self.attribute_values if value.deleted_at is None and value.is_active]
        else:
            # For attribute management, show all values (active and inactive)
            available_values = [value for value in self.attribute_values if value.deleted_at is None]
        
        return {
            'attribute_id': self.attribute_id,
            'shop_id': self.shop_id,
            'shop_name': self.shop.name if self.shop else None,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'attribute_type': self.attribute_type.value if self.attribute_type else None,
            'type': self.attribute_type.value if self.attribute_type else None,  # Add type field for frontend
            'is_required': self.is_required,
            'is_filterable': self.is_filterable,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'values': [value.serialize() for value in available_values]
        }


class ShopAttributeValue(BaseModel):
    __tablename__ = 'shop_attribute_values'

    value_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attribute_id = db.Column(db.Integer, db.ForeignKey('shop_attributes.attribute_id'), nullable=False)
    value = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Unique constraint per attribute
    __table_args__ = (
        db.UniqueConstraint('attribute_id', 'value', name='unique_attribute_value'),
    )

    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'value_id': self.value_id,
            'attribute_id': self.attribute_id,
            'value': self.value,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
