from common.database import db
from sqlalchemy import Column, Integer, String, Numeric

class TaxCategory(db.Model):
    __tablename__ = 'tax_categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    tax_rate = Column(Numeric(5, 2), nullable=False, default=0)

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'tax_rate': float(self.tax_rate) if self.tax_rate is not None else 0
        } 