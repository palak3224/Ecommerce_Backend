# models/reel_like.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.reel import Reel


class ReelLike(BaseModel):
    """Model to track which users like which reels (for recommendations)."""
    __tablename__ = 'reel_likes'
    
    like_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.reel_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('reel_likes_legacy', lazy='dynamic'))
    reel = db.relationship('Reel', backref=db.backref('reel_likes_legacy_users', lazy='dynamic'))
    
    # Unique constraint: one user can only like a reel once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'reel_id', name='uq_user_reel_like'),
        db.Index('idx_reel_likes_user_reel', 'user_id', 'reel_id'),
    )
    
    @classmethod
    def user_has_liked(cls, user_id, reel_id):
        """Check if user has already liked this reel."""
        return cls.query.filter_by(
            user_id=user_id,
            reel_id=reel_id,
            deleted_at=None
        ).first() is not None
    
    @classmethod
    def get_user_like(cls, user_id, reel_id):
        """Get like record if exists."""
        return cls.query.filter_by(
            user_id=user_id,
            reel_id=reel_id,
            deleted_at=None
        ).first()
    
    def serialize(self):
        """Serialize like record."""
        return {
            'like_id': self.like_id,
            'user_id': self.user_id,
            'reel_id': self.reel_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

