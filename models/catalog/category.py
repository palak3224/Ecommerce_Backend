from datetime import datetime
from common.database import db, BaseModel

class Category(BaseModel):
    """Category model for product categorization with hierarchical structure."""
    __tablename__ = 'categories'
    
    category_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    
    # Relationships
    parent = db.relationship('Category', remote_side=[category_id], backref=db.backref('subcategories', lazy='dynamic'))
    products = db.relationship('Product', foreign_keys='Product.category_id', back_populates='category')
    sub_products = db.relationship('Product', foreign_keys='Product.sub_category_id', back_populates='sub_category')
    attributes = db.relationship('Attribute', back_populates='category')
    sizes = db.relationship('Size', back_populates='category', cascade='all, delete-orphan')
    brands = db.relationship('Brand', back_populates='category')
    
    @classmethod
    def get_by_id(cls, category_id):
        """Get category by ID."""
        return cls.query.filter_by(category_id=category_id).first()
    
    @classmethod
    def get_by_name(cls, name):
        """Get category by name."""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_top_level_categories(cls):
        """Get all top-level categories (no parent)."""
        return cls.query.filter_by(parent_id=None).all()
    
    def get_all_subcategories(self):
        """Get all subcategories recursively."""
        all_subcategories = []
        for subcategory in self.subcategories:
            all_subcategories.append(subcategory)
            all_subcategories.extend(subcategory.get_all_subcategories())
        return all_subcategories