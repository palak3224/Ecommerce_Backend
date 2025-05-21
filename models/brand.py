from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import User

# Association table for brand-category relationship
brand_categories = db.Table('brand_categories',
    db.Column('brand_id', db.Integer, db.ForeignKey('brands.brand_id', ondelete='CASCADE'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.category_id', ondelete='CASCADE'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow, nullable=False),
    db.Column('updated_at', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
)

class Brand(BaseModel):
    __tablename__ = 'brands'
    
    brand_id    = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    slug        = db.Column(db.String(100), unique=True, nullable=False)
    icon_url    = db.Column(db.String(255), nullable=True)  
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at  = db.Column(db.DateTime)

    # Relationships
    approver    = db.relationship('User', foreign_keys=[approved_by])
    categories  = db.relationship('Category', 
                                secondary=brand_categories,
                                backref=db.backref('brands', lazy='dynamic'),
                                lazy='dynamic')

    def add_category(self, category):
        """Add a category to the brand"""
        if not self.has_category(category):
            self.categories.append(category)

    def remove_category(self, category):
        """Remove a category from the brand"""
        if self.has_category(category):
            self.categories.remove(category)

    def has_category(self, category):
        """Check if brand has a specific category"""
        return self.categories.filter(brand_categories.c.category_id == category.category_id).count() > 0

    def serialize(self):
        return {
            'brand_id': self.brand_id,
            'name': self.name,
            'slug': self.slug,
            'icon_url': self.icon_url,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'categories': [category.serialize() for category in self.categories]
        }

    def serialize_with_categories(self):
        """Serialize brand with detailed category information"""
        return {
            'brand_id': self.brand_id,
            'name': self.name,
            'slug': self.slug,
            'icon_url': self.icon_url,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'categories': [{
                'category_id': category.category_id,
                'name': category.name,
                'slug': category.slug,
                'parent_id': category.parent_id
            } for category in self.categories]
        }