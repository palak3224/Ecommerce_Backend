from enum import Enum
from common.database import db, BaseModel

class AddedBy(Enum):
    SUPERADMIN = 'superadmin'
    MERCHANT = 'merchant'

class Color(BaseModel):
    """Color model for product variants."""
    __tablename__ = 'colors'
    
    color_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    hex_code = db.Column(db.String(10), nullable=False)
    added_by = db.Column(db.Enum(AddedBy), default=AddedBy.SUPERADMIN, nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', backref=db.backref('colors', lazy=True))
    variants = db.relationship('ProductVariant', back_populates='color')
    
    @classmethod
    def get_by_id(cls, color_id):
        """Get color by ID."""
        return cls.query.filter_by(color_id=color_id).first()
    
    @classmethod
    def get_by_name(cls, name):
        """Get color by name."""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_approved_colors(cls):
        """Get all approved colors."""
        return cls.query.filter_by(is_approved=True).all()
    
    @classmethod
    def get_pending_approval(cls):
        """Get colors pending approval."""
        return cls.query.filter_by(is_approved=False).all()
    
    def approve(self):
        """Approve the color."""
        self.is_approved = True
        db.session.commit()