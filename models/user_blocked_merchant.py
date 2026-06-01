# models/user_blocked_merchant.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User, MerchantProfile


class UserBlockedMerchant(BaseModel):
    """Per-user 'not interested in this vendor' signal.

    When a user blocks a merchant, that merchant's reels are hidden from the
    user's reel feeds (recommended / trending / following / public). It is a
    user-scoped preference only: it does NOT affect other users, and it does
    NOT block product browsing, search or ordering.
    """
    __tablename__ = 'user_blocked_merchants'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('blocked_merchants', lazy='dynamic'))
    merchant = db.relationship('MerchantProfile', backref=db.backref('blocked_by_users', lazy='dynamic'))

    # Unique constraint: one block per user per merchant
    __table_args__ = (
        db.UniqueConstraint('user_id', 'merchant_id', name='uq_user_blocked_merchant'),
    )

    @classmethod
    def is_blocked(cls, user_id, merchant_id):
        """Check if a user has blocked a merchant."""
        return cls.query.filter_by(user_id=user_id, merchant_id=merchant_id).first() is not None

    @classmethod
    def block(cls, user_id, merchant_id):
        """Create a block record if it doesn't already exist."""
        if cls.is_blocked(user_id, merchant_id):
            return None  # Already blocked
        block = cls(user_id=user_id, merchant_id=merchant_id)
        db.session.add(block)
        return block

    @classmethod
    def unblock(cls, user_id, merchant_id):
        """Remove a block record if it exists."""
        block = cls.query.filter_by(user_id=user_id, merchant_id=merchant_id).first()
        if block:
            db.session.delete(block)
            return True
        return False

    @classmethod
    def get_blocked_merchant_ids(cls, user_id):
        """Return the set of merchant IDs the user has blocked (for fast feed filtering)."""
        rows = db.session.query(cls.merchant_id).filter_by(user_id=user_id).all()
        return {row[0] for row in rows}

    @classmethod
    def get_blocked(cls, user_id):
        """Return all block records for a user, newest first."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).all()
