from common.database import db, BaseModel

class ProductImage(BaseModel):
    """Product image model."""
    __tablename__ = 'product_images'
    
    image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    is_main = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    product = db.relationship('Product', back_populates='images')
    
    @classmethod
    def get_by_id(cls, image_id):
        """Get image by ID."""
        return cls.query.filter_by(image_id=image_id).first()
    
    @classmethod
    def get_product_images(cls, product_id):
        """Get all images for a product."""
        return cls.query.filter_by(product_id=product_id).all()
    
    @classmethod
    def get_main_image(cls, product_id):
        """Get main image for a product."""
        return cls.query.filter_by(product_id=product_id, is_main=True).first()


class ProductVideo(BaseModel):
    """Product video model."""
    __tablename__ = 'product_videos'
    
    video_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    video_url = db.Column(db.Text, nullable=False)
    
    # Relationships
    product = db.relationship('Product', back_populates='videos')
    
    @classmethod
    def get_by_id(cls, video_id):
        """Get video by ID."""
        return cls.query.filter_by(video_id=video_id).first()
    
    @classmethod
    def get_product_videos(cls, product_id):
        """Get all videos for a product."""
        return cls.query.filter_by(product_id=product_id).all()


class ProductAttribute(BaseModel):
    """Product attribute model for product-specific attribute values."""
    __tablename__ = 'product_attributes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attributes.attribute_id'), nullable=False)
    value = db.Column(db.String(255), nullable=False)
    
    # Relationships
    product = db.relationship('Product', back_populates='attributes')
    attribute = db.relationship('Attribute', back_populates='product_attributes')
    
    @classmethod
    def get_by_id(cls, id):
        """Get product attribute by ID."""
        return cls.query.filter_by(id=id).first()
    
    @classmethod
    def get_product_attributes(cls, product_id):
        """Get all attributes for a product."""
        return cls.query.filter_by(product_id=product_id).all()
    
    @classmethod
    def get_product_attribute(cls, product_id, attribute_id):
        """Get specific attribute for a product."""
        return cls.query.filter_by(
            product_id=product_id,
            attribute_id=attribute_id
        ).first()