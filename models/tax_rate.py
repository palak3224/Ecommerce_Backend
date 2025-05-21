from datetime import datetime, timezone
from common.database import db, BaseModel 

class TaxRate(BaseModel):
    __tablename__ = 'tax_rates'

    tax_rate_id = db.Column(db.Integer, primary_key=True) 
    name = db.Column(db.String(100), unique=True, nullable=False) # e.g., "Standard VAT", "Reduced Rate", "Zero Rate"
    description = db.Column(db.String(255), nullable=True) # Optional description of what this rate applies to
    rate_percentage = db.Column(db.Numeric(5, 2), nullable=False) 
    # Optional: For country-specific tax rates
    country_code = db.Column(db.String(3), nullable=True, index=True) 

    
    is_default = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())

    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True) 

   

    def __repr__(self):
        return f"<TaxRate id={self.tax_rate_id} name='{self.name}' rate='{self.rate_percentage}%'>"

    def serialize(self):
        return {
            "tax_rate_id": self.tax_rate_id,
            "name": self.name,
            "description": self.description,
            "rate_percentage": str(self.rate_percentage) if self.rate_percentage is not None else None, 
            "country_code": self.country_code,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if hasattr(self, 'deleted_at') and self.deleted_at else None,
        }

    @classmethod
    def get_by_name(cls, name, country_code=None):
        query = cls.query.filter(cls.name == name)
        if country_code:
            query = query.filter(cls.country_code == country_code)
        return query.first()