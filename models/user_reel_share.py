# models/user_reel_share.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.reel import Reel


class UserReelShare(BaseModel):
    """Model to track which users share which reels (for analytics and recommendations)."""
    __tablename__ = 'user_reel_shares'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.reel_id'), nullable=False, index=True)
    shared_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('reel_shares', lazy='dynamic'))
    reel = db.relationship('Reel', backref=db.backref('user_shares', lazy='dynamic'))
    
    # Unique constraint: one share record per user per reel (but allow updates to shared_at)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'reel_id', name='uq_user_reel_share'),
    )
    
    @classmethod
    def user_has_shared(cls, user_id, reel_id):
        """Check if a user has already shared a reel."""
        return cls.query.filter_by(user_id=user_id, reel_id=reel_id).first() is not None
    
    @classmethod
    def create_share(cls, user_id, reel_id):
        """Create a share record if it doesn't exist, or update shared_at timestamp."""
        share = cls.query.filter_by(user_id=user_id, reel_id=reel_id).first()
        if share:
            # Update shared_at timestamp
            share.shared_at = datetime.now(timezone.utc)
            return share
        else:
            # Create new share record
            share = cls(user_id=user_id, reel_id=reel_id)
            db.session.add(share)
            return share
    
    @classmethod
    def get_user_shared_reels(cls, user_id, limit=None):
        """Get reels that a user has shared, ordered by most recent."""
        query = cls.query.filter_by(user_id=user_id).order_by(cls.shared_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

