from datetime import datetime, timezone
from common.database import db, BaseModel
from decimal import Decimal

class VisitTracking(BaseModel):
    __tablename__ = 'visit_tracking'

    visit_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 addresses can be up to 45 chars
    visit_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
    landing_page = db.Column(db.String(255), nullable=False)
    exited_page = db.Column(db.String(255), nullable=True)
    was_converted = db.Column(db.Boolean, default=False)
    
    # Additional useful fields
    referrer_url = db.Column(db.String(255), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)  # mobile, tablet, desktop
    browser = db.Column(db.String(50), nullable=True)
    os = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    time_spent = db.Column(db.Integer, nullable=True)  # in seconds
    pages_viewed = db.Column(db.Integer, default=1)
    
    # Timestamps and soft delete
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    
    # If user later signs up, we can link their visit
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user = db.relationship('User', back_populates='visits')

    __table_args__ = (
        db.Index('idx_visit_session', 'session_id'),
        db.Index('idx_visit_time', 'visit_time'),
        db.Index('idx_visit_ip', 'ip_address'),
    )

    @classmethod
    def create_visit(cls, session_id, ip_address, landing_page, user_agent=None):
        """Create a new visit tracking record"""
        return cls(
            session_id=session_id,
            ip_address=ip_address,
            landing_page=landing_page,
            user_agent=user_agent,
            pages_viewed=1
        )

    def update_exit(self, exited_page, time_spent):
        """Update visit when user leaves the site"""
        self.exited_page = exited_page
        self.time_spent = time_spent
        self.updated_at = datetime.now(timezone.utc)

    def mark_converted(self):
        """Mark visit as converted when user signs up"""
        self.was_converted = True
        self.updated_at = datetime.now(timezone.utc)

    def increment_pages_viewed(self):
        """Increment the number of pages viewed"""
        self.pages_viewed += 1
        self.updated_at = datetime.now(timezone.utc)

    def __repr__(self):
        return f"<VisitTracking id={self.visit_id} session={self.session_id} time={self.visit_time}>"

    def serialize(self):
        """Convert visit tracking data to dictionary format"""
        return {
            "visit_id": self.visit_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "visit_time": self.visit_time.isoformat() if self.visit_time else None,
            "user_agent": self.user_agent,
            "landing_page": self.landing_page,
            "exited_page": self.exited_page,
            "was_converted": self.was_converted,
            "referrer_url": self.referrer_url,
            "device_type": self.device_type,
            "browser": self.browser,
            "os": self.os,
            "country": self.country,
            "city": self.city,
            "time_spent": self.time_spent,
            "pages_viewed": self.pages_viewed,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted
        } 