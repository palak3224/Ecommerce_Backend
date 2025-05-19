from models.product_meta import ProductMeta
from common.database import db
from flask_jwt_extended import get_jwt_identity

class MerchantProductMetaController:
    @staticmethod
    def get(pid):
        return ProductMeta.query.get_or_404(pid)

    @staticmethod
    def upsert(pid, data):
        meta = ProductMeta.query.get(pid)
        if not meta:
            meta = ProductMeta(product_id=pid, **data)
            db.session.add(meta)
        else:
            for k, v in data.items():
                setattr(meta, k, v)
        db.session.commit()
        return meta
