from common.database import db
from datetime import datetime


class ExploreBanner(db.Model):
    """
    Banner shown on the "Explore" screen of the mobile application.

    The Explore screen shows 1-3 banners as a carousel. Each banner has an
    image, a title, and a call-to-action (button text + navigation path).
    Carousel order is controlled by `display_order`. Managed from the
    Superadmin panel (Catalog > Explore Screen).
    """
    __tablename__ = 'explore_banners'

    # Maximum number of (non-deleted) banners in the explore carousel.
    MAX_BANNERS = 3

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    cta_text = db.Column(db.String(100), nullable=False)   # CTA button label, e.g. "Shop Now"
    cta_path = db.Column(db.String(500), nullable=False)   # In-app navigation path, e.g. "/collections/summer"
    display_order = db.Column(db.Integer, nullable=False, default=0)  # carousel position (0-based)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # soft delete

    def __repr__(self):
        return f'<ExploreBanner {self.id}: {self.title}>'

    def serialize(self):
        return {
            'id': self.id,
            'image_url': self.image_url,
            'title': self.title,
            'cta_text': self.cta_text,
            'cta_path': self.cta_path,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
