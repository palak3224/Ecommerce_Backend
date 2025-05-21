from common.database import db, BaseModel
from models.enums import AttributeInputType

class Attribute(BaseModel):
    __tablename__ = 'attributes'

    attribute_id = db.Column(db.Integer, primary_key=True)
    code         = db.Column(db.String(50), nullable=False, unique=True)
    name         = db.Column(db.String(100), nullable=False)
    input_type   = db.Column(db.Enum(AttributeInputType), nullable=False)
    created_at   = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # ←— Association to CategoryAttribute
    categories = db.relationship(
        'CategoryAttribute',
        back_populates='attribute',
        cascade='all, delete-orphan'
    )
    
    attribute_values = db.relationship('AttributeValue', back_populates='attribute', cascade='all, delete-orphan')

    def serialize(self):
        """Turn this Attribute into a JSON‑friendly dict."""
        return {
            'attribute_id': self.attribute_id,
            'code': self.code,
            'name': self.name,
            'input_type': self.input_type.value if self.input_type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def validate_input_type(input_type_str):
        """Validate and convert string input type to enum value."""
        try:
            return AttributeInputType(input_type_str)
        except ValueError:
            valid_types = [t.value for t in AttributeInputType]
            raise ValueError(f"Invalid input type. Must be one of: {', '.join(valid_types)}")