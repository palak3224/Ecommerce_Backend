from datetime import datetime, timezone
from common.database import db, BaseModel

class CustomerProfile(BaseModel):
    __tablename__ = 'customer_profiles'

   
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    loyalty_points = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    preferences = db.Column(db.JSON, nullable=True) 
    
    
    
    user = db.relationship('User', back_populates='customer_specific_profile')

    def __repr__(self):
        return f"<CustomerProfile user_id={self.user_id}>"

    def serialize(self):
        return {
            "user_id": self.user_id,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "loyalty_points": self.loyalty_points,
            "preferences": self.preferences if self.preferences else {},
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }

    @classmethod
    def get_by_user_id(cls, user_id):
        return cls.query.filter_by(user_id=user_id).first()