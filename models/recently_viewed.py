from datetime import datetime
from common.database import db

class RecentlyViewed(db.Model):
    __tablename__ = 'recently_viewed'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('recently_viewed', lazy=True))
    product = db.relationship('Product', backref=db.backref('viewed_by', lazy=True))

    def __init__(self, user_id, product_id, viewed_at=None):
        self.user_id = user_id
        self.product_id = product_id
        self.viewed_at = viewed_at or datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None
        } 