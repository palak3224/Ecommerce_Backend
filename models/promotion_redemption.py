# FILE: models/promotion_redemption.py
"""One row per promotion actually spent on an order.

The `UniqueConstraint` on `promotion_id` *is* the single-use enforcement. Not an
application-level `if used_count < limit` check — that reads and then writes, so two
concurrent checkouts both pass it. A unique index holds under any isolation level and
any concurrency, which is the same technique consume_quote() uses for the quote itself.

Written inside OrderController.create_order_from_quote, before its commit, so the
redemption and the order share one transaction: either both exist or neither does.
Writing it beside consume_quote() instead would lose it, because create_order_from_quote
rolls the outer transaction back on failure — on the exact path where money already moved.
"""
from datetime import datetime

from sqlalchemy import UniqueConstraint

from common.database import db


class PromotionRedemption(db.Model):
    __tablename__ = 'promotion_redemptions'

    redemption_id = db.Column(db.Integer, primary_key=True)
    promotion_id = db.Column(
        db.Integer, db.ForeignKey('promotions.promotion_id'), nullable=False, index=True
    )
    # orders.order_id is a String PK, not an Integer.
    order_id = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quote_id = db.Column(db.String(64), nullable=True, index=True)
    # Plain reference id into plinko_leads, mirroring Promotion.lead_id.
    lead_id = db.Column(db.Integer, nullable=True, index=True)
    # Stored, not derived: the superadmin panel reports what each lead actually cost,
    # and the promotion's rules may have changed since.
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False)
    redeemed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    promotion = db.relationship('Promotion', backref='redemptions')

    __table_args__ = (
        UniqueConstraint('promotion_id', name='uq_promo_redemption_promotion'),
    )

    def serialize(self):
        return {
            'redemption_id': self.redemption_id,
            'promotion_id': self.promotion_id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'quote_id': self.quote_id,
            'lead_id': self.lead_id,
            'discount_amount': float(self.discount_amount),
            'redeemed_at': self.redeemed_at.isoformat() if self.redeemed_at else None,
        }
