
from models.attribute import Attribute
from common.database import db
from sqlalchemy.exc import IntegrityError 

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
        
        existing_attribute = Attribute.query.filter_by(code=data['code']).first()
        if existing_attribute:
           
            pass

        attr = Attribute(
            code=data['code'],
            name=data['name'],
            input_type=data['input_type'] 
        )
       
        db.session.add(attr)
        try:
            db.session.commit() 
        except IntegrityError as e:
            db.session.rollback()
            raise e 
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
        try:
            db.session.commit()
        except IntegrityError as e: 
            db.session.rollback()
            raise e 
        return True 