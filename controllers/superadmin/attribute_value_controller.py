from models.attribute_value import AttributeValue
from common.database import db

class AttributeValueController:
    @staticmethod
    def list_all():
        
        return AttributeValue.query.all()

    @staticmethod
    def list_for_attribute(attribute_id):
        # filter only for one attribute
        return AttributeValue.query.filter_by(attribute_id=attribute_id).all()

    @staticmethod
    def create(data):
        # expects attribute_id, value_code, value_label
        av = AttributeValue(
            attribute_id = data['attribute_id'],
            value_code   = data['value_code'],
            value_label  = data['value_label']
        )
        av.save()
        return av

    @staticmethod
    def update(attribute_id, value_code, data):
        av = AttributeValue.query.get_or_404((attribute_id, value_code))
        av.value_label = data.get('value_label', av.value_label)
        db.session.commit()
        return av

    @staticmethod
    def delete(attribute_id, value_code):
        av = AttributeValue.query.filter_by(attribute_id=attribute_id, value_code=value_code).first()
        if not av:
            # Optionally raise a custom error or return False
            raise ValueError("Attribute value not found")
        db.session.delete(av)
        db.session.commit()
        return True
