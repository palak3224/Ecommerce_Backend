from datetime import datetime
from common.database import db, BaseModel

class Product(BaseModel):
    """Product model for merchant products."""
    __tablename__ = 'products'
    
    product_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    sub_category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    product_name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    url_key = db.Column(db.String(255), unique=True, nullable=False)
    tax_category = db.Column(db.String(100), nullable=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.brand_id'), nullable=True)
    short_description = db.Column(db.Text, nullable=True)
    full_description = db.Column(db.Text, nullable=True)
    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.Text, nullable=True)
    meta_keywords = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=True)
    special_price = db.Column(db.Numeric(10, 2), nullable=True)
    special_price_from = db.Column(db.Date, nullable=True)
    special_price_to = db.Column(db.Date, nullable=True)
    manage_stock = db.Column(db.Boolean, default=True, nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=True)
    low_stock_threshold = db.Column(db.Integer, nullable=True)
    dimensions_length = db.Column(db.Numeric(10, 2), nullable=True)
    dimensions_width = db.Column(db.Numeric(10, 2), nullable=True)
    dimensions_height = db.Column(db.Numeric(10, 2), nullable=True)
    weight = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', backref=db.backref('products', lazy=True))
    category = db.relationship('Category', foreign_keys=[category_id], back_populates='products')
    sub_category = db.relationship('Category', foreign_keys=[sub_category_id], back_populates='sub_products')
    brand = db.relationship('Brand', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan')
    videos = db.relationship('ProductVideo', back_populates='product', cascade='all, delete-orphan')
    attributes = db.relationship('ProductAttribute', back_populates='product', cascade='all, delete-orphan')
    variants = db.relationship('ProductVariant', back_populates='product', cascade='all, delete-orphan')
    
    @classmethod
    def get_by_id(cls, product_id):
        """Get product by ID."""
        return cls.query.filter_by(product_id=product_id).first()
    
    @classmethod
    def get_by_sku(cls, sku):
        """Get product by SKU."""
        return cls.query.filter_by(sku=sku).first()
    
    @classmethod
    def get_by_url_key(cls, url_key):
        """Get product by URL key."""
        return cls.query.filter_by(url_key=url_key).first()
    
    @classmethod
    def get_by_merchant(cls, merchant_id):
        """Get all products for a merchant."""
        return cls.query.filter_by(id=merchant_id).all()
    
    @classmethod
    def get_by_category(cls, category_id):
        """Get all products in a category."""
        return cls.query.filter_by(category_id=category_id).all()
    
    def get_current_price(self):
        """Get the current effective price (considering special price if active)."""
        today = datetime.utcnow().date()
        
        if (self.special_price is not None and 
            (self.special_price_from is None or self.special_price_from <= today) and
            (self.special_price_to is None or self.special_price_to >= today)):
            return self.special_price
        
        return self.price
    
    def is_in_stock(self):
        """Check if product is in stock."""
        if not self.manage_stock:
            return True
            
        if self.variants:
            # Check if any variant is in stock
            for variant in self.variants:
                if variant.stock_quantity is None or variant.stock_quantity > 0:
                    return True
            return False
        
        return self.stock_quantity is None or self.stock_quantity > 0
    
    def get_main_image(self):
        """Get the main product image."""
        main_image = next((img for img in self.images if img.is_main), None)
        return main_image if main_image else (self.images[0] if self.images else None)