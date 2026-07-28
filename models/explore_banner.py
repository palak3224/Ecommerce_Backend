from common.database import db
from datetime import datetime


class ExploreBanner(db.Model):
    """
    Banner shown on the "Explore" screen of the mobile application.

    The Explore screen supports a maximum of 3 banners. Each banner has an
    image, a title, and a call-to-action (button text + navigation path).
    Managed from the Superadmin panel (Catalog > Explore Screen).
    """
    __tablename__ = 'explore_banners'

    # The explore screen has three fixed, named banner slots.
    SLOTS = ('hero', 'spotlight', 'category')
    SLOT_LABELS = {
        'hero': 'Hero Banner',
        'spotlight': 'Spotlight Banner',
        'category': 'Category Banner',
    }
    # Maximum number of (non-deleted) banners allowed on the explore screen.
    MAX_BANNERS = len(SLOTS)

    id = db.Column(db.Integer, primary_key=True)
    slot = db.Column(db.String(20), nullable=False)        # 'hero' | 'spotlight' | 'category'
    image_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    cta_text = db.Column(db.String(100), nullable=False)   # CTA button label, e.g. "Shop Now"
    cta_path = db.Column(db.String(500), nullable=False)   # In-app navigation path, e.g. "/collections/summer"
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # soft delete

    def __repr__(self):
        return f'<ExploreBanner {self.id}: {self.title}>'

    def serialize(self):
        return {
            'id': self.id,
            'slot': self.slot,
            'slot_label': self.SLOT_LABELS.get(self.slot, self.slot),
            'image_url': self.image_url,
            'title': self.title,
            'cta_text': self.cta_text,
            'cta_path': self.cta_path,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
