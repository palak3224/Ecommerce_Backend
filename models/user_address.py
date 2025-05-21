from datetime import datetime, timezone
from common.database import db, BaseModel
from models.enums import AddressTypeEnum 

class UserAddress(BaseModel):
    __tablename__ = 'user_addresses'

    address_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    contact_name = db.Column(db.String(150), nullable=True) 
    contact_phone = db.Column(db.String(20), nullable=True)  

    address_line1 = db.Column(db.String(255), nullable=False) 
    address_line2 = db.Column(db.String(255), nullable=True)  
    landmark = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state_province = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False, index=True)
    country_code = db.Column(db.String(3), nullable=False) 
    
    address_type = db.Column(db.Enum(AddressTypeEnum), nullable=False, default=AddressTypeEnum.SHIPPING)
    
   
    is_default_shipping = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    is_default_billing = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())


    user = db.relationship('User', back_populates='addresses')

    def __repr__(self):
        return f"<UserAddress id={self.address_id} user_id={self.user_id} type='{self.address_type.value}'>"

    def get_full_address_str(self):
        parts = [self.address_line1, self.address_line2, self.city, self.state_province, self.postal_code, self.country_code]
        return ", ".join(filter(None, parts))

    def serialize(self):
        return {
            "address_id": self.address_id,
            "user_id": self.user_id,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "landmark": self.landmark,
            "city": self.city,
            "state_province": self.state_province,
            "postal_code": self.postal_code,
            "country_code": self.country_code,
            "address_type": self.address_type.value,
            "is_default_shipping": self.is_default_shipping,
            "is_default_billing": self.is_default_billing,
            "full_address_str": self.get_full_address_str(), 
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }