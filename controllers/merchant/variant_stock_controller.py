from models.variant_stock import VariantStock
from common.database import db

class MerchantVariantStockController:
    @staticmethod
    def get(vid):
        return VariantStock.query.get_or_404(vid)

    @staticmethod
    def upsert(vid, data):
        vs = VariantStock.query.get(vid)
        if not vs:
            vs = VariantStock(variant_id=vid, **data)
            db.session.add(vs)
        else:
            for k, v in data.items():
                setattr(vs, k, v)
        db.session.commit()
        return vs
