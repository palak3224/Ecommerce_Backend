from common.database import db, BaseModel

class Category(BaseModel):
    __tablename__ = 'categories'

    category_id = db.Column(db.Integer, primary_key=True)
    parent_id   = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    slug        = db.Column(db.String(100), nullable=False, unique=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at  = db.Column(db.DateTime, nullable=False,
                            default=db.func.current_timestamp(),
                            onupdate=db.func.current_timestamp())
    deleted_at  = db.Column(db.DateTime, nullable=True)

    # ←— Association to CategoryAttribute
    attributes = db.relationship(
        'CategoryAttribute',
        back_populates='category',
        cascade='all, delete-orphan'
    )
