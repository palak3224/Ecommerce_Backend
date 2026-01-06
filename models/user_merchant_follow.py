# models/user_merchant_follow.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User, MerchantProfile


class UserMerchantFollow(BaseModel):
    """Model to track which merchants users follow."""
    __tablename__ = 'user_merchant_follows'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)
    followed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('merchant_follows', lazy='dynamic'))
    merchant = db.relationship('MerchantProfile', backref=db.backref('followers', lazy='dynamic'))
    
    # Unique constraint: one follow per user per merchant
    __table_args__ = (
        db.UniqueConstraint('user_id', 'merchant_id', name='uq_user_merchant_follow'),
    )
    
    @classmethod
    def is_following(cls, user_id, merchant_id):
        """Check if a user is following a merchant."""
        return cls.query.filter_by(user_id=user_id, merchant_id=merchant_id).first() is not None
    
    @classmethod
    def follow(cls, user_id, merchant_id):
        """Create a follow record if it doesn't exist."""
        if cls.is_following(user_id, merchant_id):
            return None  # Already following
        follow = cls(user_id=user_id, merchant_id=merchant_id)
        db.session.add(follow)
        return follow
    
    @classmethod
    def unfollow(cls, user_id, merchant_id):
        """Remove a follow record if it exists."""
        follow = cls.query.filter_by(user_id=user_id, merchant_id=merchant_id).first()
        if follow:
            db.session.delete(follow)
            return True
        return False
    
    @classmethod
    def get_followed_merchants(cls, user_id):
        """Get all merchants that a user follows."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.followed_at.desc()).all()
    
    @classmethod
    def get_merchant_followers(cls, merchant_id):
        """Get all users that follow a merchant."""
        return cls.query.filter_by(merchant_id=merchant_id).order_by(cls.followed_at.desc()).all()

