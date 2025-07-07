from models.attribute import Attribute
from common.database import db
from sqlalchemy.exc import IntegrityError
from models.enums import AttributeInputType

class AttributeController:
    @staticmethod
    def list_all():
        return Attribute.query.all()

    @staticmethod
    def get(attribute_id):
        attr = Attribute.query.get_or_404(attribute_id)
        return attr

    @staticmethod
    def create(data):
        # Check for existing attribute
        existing_attribute = Attribute.query.filter_by(code=data['code']).first()
        if existing_attribute:
            # Handle duplication case (can raise error or return a message)
            raise ValueError(f"Attribute with code '{data['code']}' already exists.")

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

        db.session.add(attr)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            raise e

        # If this is a boolean attribute, automatically create true/false values
        if input_type == AttributeInputType.BOOLEAN:
            from models.attribute_value import AttributeValue
            
            # Create 'true' value
            true_value = AttributeValue(
                attribute_id=attr.attribute_id,
                value_code='true',
                value_label='Yes'
            )
            
            # Create 'false' value
            false_value = AttributeValue(
                attribute_id=attr.attribute_id,
                value_code='false',
                value_label='No'
            )
            
            db.session.add(true_value)
            db.session.add(false_value)
            
            try:
                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                # If we can't create the boolean values, delete the attribute
                db.session.delete(attr)
                db.session.commit()
                raise ValueError(f"Failed to create boolean attribute values: {str(e)}")

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
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            raise e

        return True
