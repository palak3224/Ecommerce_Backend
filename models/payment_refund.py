# models/payment_refund.py
"""Refund ledger.

Before this table, `POST /api/razorpay/refund` called the gateway and persisted
nothing at all — the only record a refund ever happened lived in Razorpay's
dashboard. That makes invariant I11 (refund currency == capture currency, and the
sum of refunds never exceeds what was captured) unenforceable, because there is
nothing to sum.

Amounts are stored in minor units as integers. A partial-refund ledger that sums
Decimals is one rounding rule away from allowing a refund of one paise more than
was captured; integers cannot drift.
"""
from datetime import datetime

from common.database import db


class RefundStatus:
    """String, not a DB Enum — see the note in models/checkout_quote.py."""
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class PaymentRefund(db.Model):
    __tablename__ = "payment_refunds"

    refund_id = db.Column(db.Integer, primary_key=True)

    # Nullable: a refund can be issued against a gateway payment whose internal
    # order we failed to correlate. Recording it unlinked beats not recording it.
    order_id = db.Column(db.String(50), nullable=True, index=True)

    gateway_payment_id = db.Column(db.String(100), nullable=False, index=True)
    gateway_refund_id = db.Column(db.String(100), nullable=True, index=True)
    gateway_name = db.Column(db.String(50), nullable=False, default="Razorpay")

    amount_minor = db.Column(db.BigInteger, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")

    status = db.Column(db.String(16), nullable=False, default=RefundStatus.PENDING, index=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def total_refunded_minor(cls, gateway_payment_id):
        """Minor units already refunded against a capture, excluding failed attempts."""
        rows = cls.query.filter(
            cls.gateway_payment_id == gateway_payment_id,
            cls.status != RefundStatus.FAILED,
        ).all()
        return sum(int(r.amount_minor) for r in rows)

    def serialize(self):
        return {
            "refund_id": self.refund_id,
            "order_id": self.order_id,
            "gateway_payment_id": self.gateway_payment_id,
            "gateway_refund_id": self.gateway_refund_id,
            "amount_minor": int(self.amount_minor),
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z",
        }
