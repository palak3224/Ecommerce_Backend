from flask_sqlalchemy import SQLAlchemy

# Initialize the database instance
db = SQLAlchemy()

# Base model with common fields for all tables
class BaseModel(db.Model):
    """Base model with common fields for all tables."""
    __abstract__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
                          onupdate=db.func.current_timestamp())
    
    def save(self):
        """Save model to database."""
        db.session.add(self)
        db.session.commit()
        
    def delete(self):
        """Delete model from database."""
        db.session.delete(self)
        db.session.commit()
        
    @classmethod
    def get_by_id(cls, id):
        """Get a record by ID."""
        return cls.query.filter_by(id=id).first()
    
    @classmethod
    def get_all(cls):
        """Get all records."""
        return cls.query.all()