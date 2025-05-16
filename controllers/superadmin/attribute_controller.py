from models.attribute import Attribute
from common.database import db
from models.enums import AttributeInputType

class AttributeController:
    @staticmethod
    def list_all():
        return Attribute.query.all()

    @staticmethod
    def create(data):
        # Validate and convert input_type to enum
        try:
            input_type = AttributeInputType(data['input_type'])
        except ValueError:
            valid_types = [t.value for t in AttributeInputType]
            raise ValueError(f"Invalid input type. Must be one of: {', '.join(valid_types)}")

        attr = Attribute(
            code=data['code'],
            name=data['name'],
            input_type=input_type
        )
        attr.save()
        return attr

    @staticmethod
    def update(attribute_id, data):
        attr = Attribute.query.get_or_404(attribute_id)
        
        if 'name' in data:
            attr.name = data['name']
        
        if 'input_type' in data:
            try:
                attr.input_type = AttributeInputType(data['input_type'])
            except ValueError:
                valid_types = [t.value for t in AttributeInputType]
                raise ValueError(f"Invalid input type. Must be one of: {', '.join(valid_types)}")

        db.session.commit()
        return attr

    @staticmethod
    def delete(attribute_id):
        attr = Attribute.query.get_or_404(attribute_id)
        db.session.delete(attr)
        db.session.commit()
        return True
