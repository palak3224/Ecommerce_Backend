from common.database import db, BaseModel
from models.enums import AttributeInputType

class Attribute(BaseModel):
    __tablename__ = 'attributes'

    attribute_id = db.Column(db.Integer, primary_key=True)
    code         = db.Column(db.String(50), nullable=False, unique=True)
    name         = db.Column(db.String(100), nullable=False)
    input_type   = db.Column(db.Enum(AttributeInputType), nullable=False)  # import this Enum appropriately
    created_at   = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # ←— Association to CategoryAttribute
    categories = db.relationship(
        'CategoryAttribute',
        back_populates='attribute',
        cascade='all, delete-orphan'
    )
