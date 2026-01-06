# models/user_reel_view.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.reel import Reel


class UserReelView(BaseModel):
    """Model to track which users viewed which reels (for recommendations)."""
    __tablename__ = 'user_reel_views'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.reel_id'), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    view_duration = db.Column(db.Integer, nullable=True)  # Duration in seconds (optional)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('reel_views', lazy='dynamic'))
    reel = db.relationship('Reel', backref=db.backref('user_views', lazy='dynamic'))
    
    # Unique constraint: one view record per user per reel
    __table_args__ = (
        db.UniqueConstraint('user_id', 'reel_id', name='uq_user_reel_view'),
    )
    
    @classmethod
    def has_user_viewed(cls, user_id, reel_id):
        """Check if a user has already viewed a reel."""
        return cls.query.filter_by(user_id=user_id, reel_id=reel_id).first() is not None
    
    @classmethod
    def track_view(cls, user_id, reel_id, view_duration=None):
        """Track a view if it doesn't exist, or update the viewed_at timestamp."""
        view = cls.query.filter_by(user_id=user_id, reel_id=reel_id).first()
        if view:
            # Update viewed_at timestamp
            view.viewed_at = datetime.now(timezone.utc)
            if view_duration is not None:
                view.view_duration = view_duration
            return view
        else:
            # Create new view record
            view = cls(
                user_id=user_id,
                reel_id=reel_id,
                view_duration=view_duration
            )
            db.session.add(view)
            return view
    
    @classmethod
    def get_user_viewed_reels(cls, user_id, limit=None):
        """Get reels that a user has viewed, ordered by most recent."""
        query = cls.query.filter_by(user_id=user_id).order_by(cls.viewed_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

