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
            # Create new meta with product_id from URL parameter
            meta = ProductMeta(product_id=pid)
            db.session.add(meta)
        
        # Update meta fields
        for k, v in data.items():
            if k in ['short_desc', 'full_desc', 'meta_title', 'meta_desc', 'meta_keywords']:
                setattr(meta, k, v)
            
        db.session.commit()
        return meta
