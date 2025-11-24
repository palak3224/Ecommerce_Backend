# models/user_reel_like.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.reel import Reel


class UserReelLike(BaseModel):
    """Model to track which users like which reels (for recommendations)."""
    __tablename__ = 'user_reel_likes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.reel_id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('reel_likes', lazy='dynamic'))
    reel = db.relationship('Reel', backref=db.backref('user_likes', lazy='dynamic'))
    
    # Unique constraint: one user can only like a reel once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'reel_id', name='uq_user_reel_like'),
    )
    
    @classmethod
    def user_has_liked(cls, user_id, reel_id):
        """Check if a user has already liked a reel."""
        return cls.query.filter_by(user_id=user_id, reel_id=reel_id).first() is not None
    
    @classmethod
    def create_like(cls, user_id, reel_id):
        """Create a like record if it doesn't exist."""
        if cls.user_has_liked(user_id, reel_id):
            return None  # Already liked
        like = cls(user_id=user_id, reel_id=reel_id)
        db.session.add(like)
        return like
    
    @classmethod
    def remove_like(cls, user_id, reel_id):
        """Remove a like record if it exists."""
        like = cls.query.filter_by(user_id=user_id, reel_id=reel_id).first()
        if like:
            db.session.delete(like)
            return True
        return False

