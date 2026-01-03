from flask_sqlalchemy import SQLAlchemy
import logging

# Initialize the database instance
db = SQLAlchemy()

# Logger for database operations
logger = logging.getLogger(__name__)

# Base model with common fields for all tables
class BaseModel(db.Model):
    """Base model with common fields for all tables."""
    __abstract__ = True
    
    # No default ID field - each model will define its own primary key
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
                          onupdate=db.func.current_timestamp())
    
    def save(self):
        """Save model to database."""
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log the error for observability
            logger.error(f"Failed to save {self.__class__.__name__}: {str(e)}", exc_info=True)
            # Re-raise to preserve original exception behavior
            raise
        
    def delete(self):
        """Delete model from database."""
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log the error for observability
            logger.error(f"Failed to delete {self.__class__.__name__}: {str(e)}", exc_info=True)
            # Re-raise to preserve original exception behavior
            raise
    
    @classmethod
    def get_all(cls):
        """Get all records."""
        return cls.query.all()