from models.product_attribute import ProductAttribute
from common.database import db
from flask_jwt_extended import get_jwt_identity

class MerchantProductAttributeController:
    @staticmethod
    def list(pid):
        return ProductAttribute.query.filter_by(product_id=pid).all()

    @staticmethod
    def create(pid, data):
        pa = ProductAttribute(
            product_id=pid,
            attribute_id=data['attribute_id'],
            value_code=data.get('value_code'),
            value_text=data.get('value_text')
        )
        db.session.add(pa)
        db.session.commit()
        return pa

    @staticmethod
    def update(pid, aid, code, data):
        pa = ProductAttribute.query.get_or_404((pid, aid, code))
        pa.value_text = data.get('value_text', pa.value_text)
        db.session.commit()
        return pa

    @staticmethod
    def delete(pid, aid, code):
        pa = ProductAttribute.query.get_or_404((pid, aid, code))
        db.session.delete(pa)
        db.session.commit()
        return True
