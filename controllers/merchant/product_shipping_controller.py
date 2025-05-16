from models.product_shipping import ProductShipping
from common.database import db

class MerchantProductShippingController:
    @staticmethod
    def get(pid):
        return ProductShipping.query.get_or_404(pid)

    @staticmethod
    def upsert(pid, data):
        ship = ProductShipping.query.get(pid)
        if not ship:
            ship = ProductShipping(product_id=pid, **data)
            db.session.add(ship)
        else:
            for k, v in data.items():
                setattr(ship, k, v)
        db.session.commit()
        return ship
