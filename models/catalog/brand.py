from enum import Enum
from common.database import db, BaseModel

class AddedBy(Enum):
    SUPERADMIN = 'superadmin'
    MERCHANT = 'merchant'

class Brand(BaseModel):
    """Brand model for product brands."""
    __tablename__ = 'brands'
    
    brand_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    added_by = db.Column(db.Enum(AddedBy), default=AddedBy.SUPERADMIN, nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', backref=db.backref('brands', lazy=True))
    products = db.relationship('Product', back_populates='brand')
    category = db.relationship('Category', back_populates='brands')
    
    @classmethod
    def get_by_id(cls, brand_id):
        """Get brand by ID."""
        return cls.query.filter_by(brand_id=brand_id).first()
    
    @classmethod
    def get_by_name(cls, name):
        """Get brand by name."""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_by_category(cls, category_id):
        """Get brands for a specific category."""
        return cls.query.filter_by(category_id=category_id).all()
    
    @classmethod
    def get_approved_brands(cls):
        """Get all approved brands."""
        return cls.query.filter_by(is_approved=True).all()
    
    @classmethod
    def get_pending_approval(cls):
        """Get brands pending approval."""
        return cls.query.filter_by(is_approved=False).all()
    
    def approve(self):
        """Approve the brand."""
        self.is_approved = True
        db.session.commit()