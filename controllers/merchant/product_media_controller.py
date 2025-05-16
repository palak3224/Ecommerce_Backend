from models.product_media import ProductMedia
from common.database import db

class MerchantProductMediaController:
    @staticmethod
    def list(pid):
        return ProductMedia.query.filter_by(product_id=pid, deleted_at=None).all()

    @staticmethod
    def create(pid, data):
        pm = ProductMedia(product_id=pid, **data)
        db.session.add(pm)
        db.session.commit()
        return pm

    @staticmethod
    def delete(mid):
        pm = ProductMedia.query.get_or_404(mid)
        pm.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return pm
