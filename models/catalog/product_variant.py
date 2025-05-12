from common.database import db, BaseModel

class ProductVariant(BaseModel):
    """Product variant model for different product combinations (size, color, etc.)."""
    __tablename__ = 'product_variants'
    
    variant_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    color_id = db.Column(db.Integer, db.ForeignKey('colors.color_id'), nullable=True)
    size_id = db.Column(db.Integer, db.ForeignKey('sizes.size_id'), nullable=True)
    stock_quantity = db.Column(db.Integer, nullable=True)
    
    # Relationships
    product = db.relationship('Product', back_populates='variants')
    color = db.relationship('Color', back_populates='variants')
    size = db.relationship('Size', back_populates='variants')
    images = db.relationship('VariantImage', back_populates='variant', cascade='all, delete-orphan')
    attributes = db.relationship('VariantAttribute', back_populates='variant', cascade='all, delete-orphan')
    
    @classmethod
    def get_by_id(cls, variant_id):
        """Get variant by ID."""
        return cls.query.filter_by(variant_id=variant_id).first()
    
    @classmethod
    def get_by_sku(cls, sku):
        """Get variant by SKU."""
        return cls.query.filter_by(sku=sku).first()
    
    @classmethod
    def get_product_variants(cls, product_id):
        """Get all variants for a product."""
        return cls.query.filter_by(product_id=product_id).all()
    
    def is_in_stock(self):
        """Check if variant is in stock."""
        return self.stock_quantity is None or self.stock_quantity > 0


class VariantImage(BaseModel):
    """Variant image model."""
    __tablename__ = 'variant_images'
    
    image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.variant_id'), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    
    # Relationships
    variant = db.relationship('ProductVariant', back_populates='images')
    
    @classmethod
    def get_by_id(cls, image_id):
        """Get image by ID."""
        return cls.query.filter_by(image_id=image_id).first()
    
    @classmethod
    def get_variant_images(cls, variant_id):
        """Get all images for a variant."""
        return cls.query.filter_by(variant_id=variant_id).all()


class VariantAttribute(BaseModel):
    """Variant attribute model for variant-specific attributes (fabric, pattern, etc.)."""
    __tablename__ = 'variant_attributes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.variant_id'), nullable=False)
    attribute_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    
    # Relationships
    variant = db.relationship('ProductVariant', back_populates='attributes')
    
    @classmethod
    def get_by_id(cls, id):
        """Get variant attribute by ID."""
        return cls.query.filter_by(id=id).first()
    
    @classmethod
    def get_variant_attributes(cls, variant_id):
        """Get all attributes for a variant."""
        return cls.query.filter_by(variant_id=variant_id).all()
    
    @classmethod
    def get_by_name(cls, variant_id, attribute_name):
        """Get specific attribute by name for a variant."""
        return cls.query.filter_by(
            variant_id=variant_id,
            attribute_name=attribute_name
        ).first()