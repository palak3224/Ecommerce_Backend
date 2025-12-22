# models/merchant_notification.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import MerchantProfile, User
from models.enums import NotificationType
from sqlalchemy import Index


class MerchantNotification(BaseModel):
    """Model for merchant notifications (aggregated for reel likes)."""
    __tablename__ = 'merchant_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)
    
    # Notification details
    notification_type = db.Column(db.Enum(NotificationType), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Related entity (for reel likes: entity_type='reel', entity_id=reel_id)
    # For follows: entity_type='user', entity_id=user_id
    related_entity_type = db.Column(db.String(50), nullable=True, index=True)
    related_entity_id = db.Column(db.Integer, nullable=True, index=True)
    
    # Aggregation fields (for reel likes)
    like_count = db.Column(db.Integer, default=0, nullable=False)  # Total likes for this reel
    last_liked_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_liked_by_user_name = db.Column(db.String(200), nullable=True)  # Cache user name for performance
    
    # Read status
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', backref=db.backref('notifications', lazy='dynamic'))
    last_liked_by = db.relationship('User', foreign_keys=[last_liked_by_user_id])
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_merchant_notification_type', 'merchant_id', 'notification_type', 'related_entity_type', 'related_entity_id'),
        Index('idx_merchant_unread', 'merchant_id', 'is_read'),
    )
    
    @classmethod
    def get_or_create_reel_like_notification(cls, merchant_id, reel_id, user_id, user_name):
        """
        Get existing notification for reel likes or create new one.
        Updates like count if notification exists.
        Uses row-level locking to prevent race conditions.
        
        Args:
            merchant_id: Merchant ID
            reel_id: Reel ID
            user_id: User ID who liked
            user_name: User's full name (will use fallback if empty)
            
        Returns:
            MerchantNotification instance
        """
        # Ensure user_name is not empty
        if not user_name or not user_name.strip():
            user_name = "Someone"
        
        # Use row-level locking to prevent race conditions
        # Lock the row for update to ensure atomic operation
        # If lock fails (nowait=True), fall back to regular query
        try:
            notification = cls.query.filter_by(
                merchant_id=merchant_id,
                notification_type=NotificationType.REEL_LIKED,
                related_entity_type='reel',
                related_entity_id=reel_id,
                is_read=False  # Only update unread notifications
            ).with_for_update(nowait=True).first()
        except Exception:
            # If locking fails, use regular query (fallback for compatibility)
            notification = cls.query.filter_by(
                merchant_id=merchant_id,
                notification_type=NotificationType.REEL_LIKED,
                related_entity_type='reel',
                related_entity_id=reel_id,
                is_read=False
            ).first()
        
        if notification:
            # Update existing notification atomically
            notification.like_count += 1
            notification.last_liked_by_user_id = user_id
            notification.last_liked_by_user_name = user_name
            notification.updated_at = datetime.now(timezone.utc)
            # Update message with new count
            notification.message = f"Your reel has received {notification.like_count} likes"
            db.session.add(notification)
        else:
            # Create new notification
            notification = cls(
                merchant_id=merchant_id,
                notification_type=NotificationType.REEL_LIKED,
                title="Your reel is getting popular!",
                message=f"Your reel has received 1 like",
                related_entity_type='reel',
                related_entity_id=reel_id,
                like_count=1,
                last_liked_by_user_id=user_id,
                last_liked_by_user_name=user_name,
                is_read=False
            )
            db.session.add(notification)
        
        return notification
    
    @classmethod
    def create_follow_notification(cls, merchant_id, follower_user_id, follower_name):
        """
        Create notification when merchant is followed.
        Follows are not aggregated - each follow gets its own notification.
        
        Args:
            merchant_id: Merchant ID
            follower_user_id: User ID who followed
            follower_name: User's full name (will use fallback if empty)
            
        Returns:
            MerchantNotification instance
        """
        # Ensure user_name is not empty
        if not follower_name or not follower_name.strip():
            follower_name = "Someone"
        
        notification = cls(
            merchant_id=merchant_id,
            notification_type=NotificationType.MERCHANT_FOLLOWED,
            title="New follower",
            message=f"{follower_name} started following you",
            related_entity_type='user',
            related_entity_id=follower_user_id,
            is_read=False
        )
        db.session.add(notification)
        return notification
    
    @classmethod
    def get_merchant_notifications(cls, merchant_id, page=1, per_page=20, unread_only=False):
        """
        Get paginated notifications for a merchant.
        
        Args:
            merchant_id: Merchant ID
            page: Page number (must be >= 1)
            per_page: Items per page (must be between 1 and 100)
            unread_only: If True, only return unread notifications
            
        Returns:
            tuple: (notifications list, total count, total pages)
        """
        # Validate pagination parameters
        page = max(1, int(page)) if page else 1
        per_page = max(1, min(100, int(per_page))) if per_page else 20
        
        query = cls.query.filter_by(merchant_id=merchant_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        # Order by created_at descending (newest first)
        query = query.order_by(cls.created_at.desc())
        
        # Get total count
        total = query.count()
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        offset = (page - 1) * per_page
        
        notifications = query.offset(offset).limit(per_page).all()
        
        return notifications, total, total_pages
    
    @classmethod
    def get_unread_count(cls, merchant_id):
        """Get count of unread notifications for a merchant."""
        return cls.query.filter_by(merchant_id=merchant_id, is_read=False).count()
    
    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)
        db.session.add(self)
    
    @classmethod
    def mark_all_as_read(cls, merchant_id):
        """Mark all notifications as read for a merchant."""
        notifications = cls.query.filter_by(merchant_id=merchant_id, is_read=False).all()
        now = datetime.now(timezone.utc)
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
            db.session.add(notification)
        return len(notifications)
    
    @classmethod
    def cleanup_old_notifications(cls, merchant_id=None, days_old=90):
        """
        Delete notifications older than specified days.
        Only deletes read notifications to preserve unread ones.
        
        Args:
            merchant_id: Optional merchant ID to cleanup only for specific merchant
            days_old: Number of days old (default: 90)
            
        Returns:
            int: Number of notifications deleted
        """
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        # Only delete read notifications older than cutoff
        query = cls.query.filter(
            cls.is_read == True,
            cls.created_at < cutoff_date
        )
        
        # If merchant_id provided, filter by merchant
        if merchant_id:
            query = query.filter(cls.merchant_id == merchant_id)
        
        old_notifications = query.all()
        
        count = len(old_notifications)
        for notification in old_notifications:
            db.session.delete(notification)
        
        return count
    
    @classmethod
    def bulk_delete(cls, merchant_id, notification_ids):
        """
        Delete multiple notifications for a merchant.
        
        Args:
            merchant_id: Merchant ID
            notification_ids: List of notification IDs to delete
            
        Returns:
            int: Number of notifications deleted
        """
        if not notification_ids:
            return 0
        
        notifications = cls.query.filter(
            cls.id.in_(notification_ids),
            cls.merchant_id == merchant_id
        ).all()
        
        count = len(notifications)
        for notification in notifications:
            db.session.delete(notification)
        
        return count
    
    def serialize(self):
        """Serialize notification to dictionary."""
        return {
            'id': self.id,
            'type': self.notification_type.value if self.notification_type else None,
            'title': self.title,
            'message': self.message,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'like_count': self.like_count if self.like_count > 0 else None,
            'last_liked_by_user_name': self.last_liked_by_user_name,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

