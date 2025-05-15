from models.review import Review
from common.database import db

class ReviewController:
    @staticmethod
    def list_recent(limit=50):
        return Review.query.filter_by(deleted_at=None).order_by(Review.created_at.desc()).limit(limit).all()

    @staticmethod
    def delete(review_id):
        r = Review.query.get_or_404(review_id)
        r.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return r
