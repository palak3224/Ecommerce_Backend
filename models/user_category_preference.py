# models/user_category_preference.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import User
from models.category import Category


class UserCategoryPreference(BaseModel):
    """Model to store calculated category preferences for faster recommendation queries."""
    __tablename__ = 'user_category_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False, index=True)
    preference_score = db.Column(db.Numeric(5, 4), default=0.0000, nullable=False)  # Score 0.0000 to 1.0000
    interaction_count = db.Column(db.Integer, default=0, nullable=False)  # Total interactions in this category
    last_interaction_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('category_preferences', lazy='dynamic'))
    category = db.relationship('Category', backref=db.backref('user_preferences', lazy='dynamic'))
    
    # Unique constraint: one preference per user per category
    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', name='uq_user_category_pref'),
        db.Index('idx_preference_score', 'preference_score'),
    )
    
    @classmethod
    def get_user_preferences(cls, user_id, limit=None):
        """Get user's category preferences, ordered by score descending."""
        query = cls.query.filter_by(user_id=user_id).order_by(cls.preference_score.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @classmethod
    def update_preference(cls, user_id, category_id, score_delta, interaction_type='view'):
        """
        Update or create a category preference.
        
        Args:
            user_id: User ID
            category_id: Category ID
            score_delta: Score increment (e.g., 0.1 for view, 0.3 for like)
            interaction_type: Type of interaction (view, like, order)
        """
        preference = cls.query.filter_by(user_id=user_id, category_id=category_id).first()
        
        if preference:
            # Update existing preference
            new_score = float(preference.preference_score) + score_delta
            # Cap at 1.0
            preference.preference_score = min(1.0, new_score)
            preference.interaction_count += 1
            preference.last_interaction_at = datetime.now(timezone.utc)
        else:
            # Create new preference
            preference = cls(
                user_id=user_id,
                category_id=category_id,
                preference_score=min(1.0, score_delta),
                interaction_count=1,
                last_interaction_at=datetime.now(timezone.utc)
            )
            db.session.add(preference)
        
        return preference
    
    @classmethod
    def calculate_from_behavior(cls, user_id):
        """
        Calculate category preferences from user behavior (likes, views, orders).
        This is a batch operation that can be run periodically.
        """
        from models.user_reel_like import UserReelLike
        from models.user_reel_view import UserReelView
        from models.order import Order, OrderItem
        from models.reel import Reel
        from models.product import Product
        
        # Get user's liked reels and extract categories
        liked_reels = UserReelLike.query.filter_by(user_id=user_id).all()
        category_scores = {}
        
        # Process likes (weight: 3.0)
        for like in liked_reels:
            reel = Reel.query.get(like.reel_id)
            if reel and reel.product:
                category_id = reel.product.category_id
                if category_id:
                    if category_id not in category_scores:
                        category_scores[category_id] = {'score': 0.0, 'count': 0}
                    category_scores[category_id]['score'] += 0.3
                    category_scores[category_id]['count'] += 1
        
        # Process views (weight: 1.0)
        viewed_reels = UserReelView.query.filter_by(user_id=user_id).all()
        for view in viewed_reels:
            reel = Reel.query.get(view.reel_id)
            if reel and reel.product:
                category_id = reel.product.category_id
                if category_id:
                    if category_id not in category_scores:
                        category_scores[category_id] = {'score': 0.0, 'count': 0}
                    category_scores[category_id]['score'] += 0.1
                    category_scores[category_id]['count'] += 1
        
        # Process orders (weight: 2.0)
        orders = Order.query.filter_by(user_id=user_id).all()
        for order in orders:
            for item in order.items:
                if item.product:
                    category_id = item.product.category_id
                    if category_id:
                        if category_id not in category_scores:
                            category_scores[category_id] = {'score': 0.0, 'count': 0}
                        category_scores[category_id]['score'] += 0.2
                        category_scores[category_id]['count'] += 1
        
        # Normalize scores to 0.0-1.0 range and update preferences
        max_score = max([s['score'] for s in category_scores.values()]) if category_scores else 1.0
        if max_score > 0:
            for category_id, data in category_scores.items():
                normalized_score = min(1.0, data['score'] / max_score)
                cls.update_preference(user_id, category_id, normalized_score, 'calculated')
        
        db.session.commit()
        return category_scores

