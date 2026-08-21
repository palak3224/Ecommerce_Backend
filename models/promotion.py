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

    # --- Redemption rules. All nullable with no server default: every historical row
    # must read as "no minimum, no cap, not bound to anyone", which is how promotions
    # behaved before these existed. See services/promotion_service.py for enforcement.
    min_order_value     = db.Column(db.Numeric(10, 2), nullable=True)
    max_discount_amount = db.Column(db.Numeric(10, 2), nullable=True)
    # Recorded on every minted code; only *enforced* when PROMO_EMAIL_BINDING_ENFORCED
    # is on, because rejecting a legitimate winner costs more than a leaked code.
    restricted_to_email = db.Column(db.String(255), nullable=True, index=True)
    # Provenance, not a gate: which lead earned this code. A plain reference id rather
    # than a FK, mirroring fx_rate_id (see migration 010).
    lead_id             = db.Column(db.Integer, nullable=True, index=True)
    # 'plinko' for game-issued codes. Lets the superadmin grid exclude them and powers
    # the daily mint ceiling.
    source              = db.Column(db.String(32), nullable=True, index=True)
    
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
            'min_order_value': float(self.min_order_value) if self.min_order_value is not None else None,
            'max_discount_amount': float(self.max_discount_amount) if self.max_discount_amount is not None else None,
            'restricted_to_email': self.restricted_to_email,
            'lead_id': self.lead_id,
            'source': self.source,
            'target': target,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }

class GamePlay(BaseModel):
    __tablename__ = 'game_plays'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    game_type = db.Column(db.String(50), nullable=False)  # e.g., 'spin-wheel', 'match-card'
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.promotion_id'), nullable=True)
    played_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='game_plays')
    promotion = db.relationship('Promotion', backref='game_plays')

    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'game_type': self.game_type,
            'promotion': self.promotion.serialize() if self.promotion else None,
            'played_at': self.played_at.isoformat(),
        }