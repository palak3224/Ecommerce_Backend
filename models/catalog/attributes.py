from common.database import db, BaseModel

class Size(BaseModel):
    """Size model for product variants."""
    __tablename__ = 'sizes'
    __include_default_id__ = False  # Disable default id field
    
    size_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp(), nullable=False)
    
    # Relationships
    category = db.relationship('Category', back_populates='sizes')
    variants = db.relationship('ProductVariant', back_populates='size')
    
    @classmethod
    def get_by_id(cls, size_id):
        """Get size by ID."""
        return cls.query.filter_by(size_id=size_id).first()
    
    @classmethod
    def get_by_name(cls, name):
        """Get size by name."""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_by_category(cls, category_id):
        """Get sizes for a specific category."""
        return cls.query.filter_by(category_id=category_id).all()


class Attribute(BaseModel):
    """Attribute model for product attributes."""
    __tablename__ = 'attributes'
    
    attribute_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    is_category_specific = db.Column(db.Boolean, default=False, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    
    # Relationships
    category = db.relationship('Category', back_populates='attributes')
    product_attributes = db.relationship('ProductAttribute', back_populates='attribute')
    
    @classmethod
    def get_by_id(cls, attribute_id):
        """Get attribute by ID."""
        return cls.query.filter_by(attribute_id=attribute_id).first()
    
    @classmethod
    def get_by_name(cls, name):
        """Get attribute by name."""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_by_category(cls, category_id):
        """Get attributes for a specific category."""
        return cls.query.filter_by(category_id=category_id).all()