from models.brand import Brand
from common.database import db

class BrandController:
    @staticmethod
    def list_all():
        return Brand.query.filter_by(deleted_at=None).all()

    @staticmethod
    def get(brand_id):
        return Brand.query.get_or_404(brand_id)

    @staticmethod
    def delete(brand_id):
        b = Brand.query.get_or_404(brand_id)
        b.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return b
