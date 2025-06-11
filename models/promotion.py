# FILE: models/promotion.py
from datetime import datetime
from common.database import db, BaseModel
from models.enums import DiscountType
from sqlalchemy import CheckConstraint

class Promotion(BaseModel):
    __tablename__ = 'promotions'
    promotion_id   = db.Column(db.Integer, primary_key=True)
    code           = db.Column(db.String(50), unique=True, nullable=False)
    description    = db.Column(db.String(255))
    discount_type  = db.Column(db.Enum(DiscountType), nullable=False)
    discount_value = db.Column(db.Numeric(10,2), nullable=False)
    
    # Target specific entities
    product_id     = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=True)
    category_id    = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    brand_id       = db.Column(db.Integer, db.ForeignKey('brands.brand_id'), nullable=True)
    
    start_date     = db.Column(db.Date, nullable=False)
    end_date       = db.Column(db.Date, nullable=False)
    active_flag    = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at     = db.Column(db.DateTime)

    # Relationships
    product = db.relationship('Product', backref='promotions')
    category = db.relationship('Category', backref='promotions')
    brand = db.relationship('Brand', backref='promotions')

    # Constraint to ensure only one of product_id, category_id, brand_id is set
    __table_args__ = (
        CheckConstraint(
            '(CASE WHEN product_id IS NOT NULL THEN 1 ELSE 0 END + '
            'CASE WHEN category_id IS NOT NULL THEN 1 ELSE 0 END + '
            'CASE WHEN brand_id IS NOT NULL THEN 1 ELSE 0 END) <= 1',
            name='chk_promotion_target_exclusivity'
        ),
    )

    def serialize(self):
        target = None
        if self.product_id and self.product:
            target = {
                'type': 'product',
                'id': self.product_id,
                'name': self.product.product_name
            }
        elif self.category_id and self.category:
            target = {
                'type': 'category',
                'id': self.category_id,
                'name': self.category.name
            }
        elif self.brand_id and self.brand:
            target = {
                'type': 'brand',
                'id': self.brand_id,
                'name': self.brand.name
            }

        return {
            'promotion_id': self.promotion_id,
            'code': self.code,
            'description': self.description,
            'discount_type': self.discount_type.value,
            'discount_value': float(self.discount_value),
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'active_flag': self.active_flag,
            'target': target,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }