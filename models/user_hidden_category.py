# models/user_hidden_category.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.category import Category


class UserHiddenCategory(BaseModel):
    """Per-user 'not interested in this category' signal.

    When a user hides a category, reels in that category are hard-hidden from
    the user's reel feeds. Covers both AOIN reels (category via the linked
    product) and external reels (category stored directly on the reel). It is a
    user-scoped preference only and does not affect other users.
    """
    __tablename__ = 'user_hidden_categories'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('hidden_categories', lazy='dynamic'))
    category = db.relationship('Category', backref=db.backref('hidden_by_users', lazy='dynamic'))

    # Unique constraint: one hide per user per category
    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', name='uq_user_hidden_category'),
    )

    @classmethod
    def is_hidden(cls, user_id, category_id):
        """Check if a user has hidden a category."""
        return cls.query.filter_by(user_id=user_id, category_id=category_id).first() is not None

    @classmethod
    def hide(cls, user_id, category_id):
        """Create a hidden-category record if it doesn't already exist."""
        if cls.is_hidden(user_id, category_id):
            return None  # Already hidden
        hidden = cls(user_id=user_id, category_id=category_id)
        db.session.add(hidden)
        return hidden

    @classmethod
    def unhide(cls, user_id, category_id):
        """Remove a hidden-category record if it exists."""
        hidden = cls.query.filter_by(user_id=user_id, category_id=category_id).first()
        if hidden:
            db.session.delete(hidden)
            return True
        return False

    @classmethod
    def get_hidden_category_ids(cls, user_id):
        """Return the set of category IDs the user has hidden (for fast feed filtering)."""
        rows = db.session.query(cls.category_id).filter_by(user_id=user_id).all()
        return {row[0] for row in rows}

    @classmethod
    def get_hidden(cls, user_id):
        """Return all hidden-category records for a user, newest first."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).all()
