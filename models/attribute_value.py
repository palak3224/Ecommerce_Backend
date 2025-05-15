from datetime import datetime
from common.database import db, BaseModel
from auth.models.models import MerchantProfile
from models.category import Category
from models.brand import Brand
class AttributeValue(BaseModel):
    __tablename__ = 'attribute_values'
    attribute_id = db.Column(db.Integer, db.ForeignKey('attributes.attribute_id'), primary_key=True)
    value_code   = db.Column(db.String(50), primary_key=True)
    value_label  = db.Column(db.String(100), nullable=False)
    def serialize(self):
        return {
            'attribute_id': self.attribute_id,
            'value_code': self.value_code,
            'value_label': self.value_label
        }