from models.attribute import Attribute
from common.database import db

class AttributeController:
    @staticmethod
    def list_all():
        return Attribute.query.all()

    @staticmethod
    def create(data):
        attr = Attribute(
            code=data['code'],
            name=data['name'],
            input_type=data['input_type']
        )
        attr.save()
        return attr

    @staticmethod
    def update(attribute_id, data):
        attr = Attribute.query.get_or_404(attribute_id)
        attr.name = data.get('name', attr.name)
        attr.input_type = data.get('input_type', attr.input_type)
        db.session.commit()
        return attr

    @staticmethod
    def delete(attribute_id):
        attr = Attribute.query.get_or_404(attribute_id)
        db.session.delete(attr)
        db.session.commit()
        return True
