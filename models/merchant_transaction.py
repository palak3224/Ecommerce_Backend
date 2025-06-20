from datetime import datetime
from common.database import db, BaseModel
from models.order import Order
from auth.models.models import MerchantProfile

class MerchantTransaction(BaseModel):
    __tablename__ = 'merchant_transactions'

    id = db.Column(db.Integer, primary_key=True)
    
    order_id = db.Column(db.String(50), db.ForeignKey('orders.order_id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)

    order_amount = db.Column(db.Numeric(10, 2), nullable=False)
    platform_fee_percent = db.Column(db.Numeric(5, 2), nullable=False)
    platform_fee_amount = db.Column(db.Numeric(10, 2), nullable=False)
    gst_on_fee_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_gateway_fee = db.Column(db.Numeric(10, 2), nullable=False)
    final_payable_amount = db.Column(db.Numeric(10, 2), nullable=False)

    payment_status = db.Column(db.Enum('pending', 'paid', name='payment_status_enum'), default='pending', nullable=False)
    settlement_date = db.Column(db.Date, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    merchant = db.relationship('MerchantProfile', backref='merchant_transactions')
    order = db.relationship('Order', backref='merchant_transactions')

    def serialize(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "merchant_id": self.merchant_id,
            "order_amount": float(self.order_amount),
            "platform_fee_percent": float(self.platform_fee_percent),
            "platform_fee_amount": float(self.platform_fee_amount),
            "gst_on_fee_amount": float(self.gst_on_fee_amount),
            "payment_gateway_fee": float(self.payment_gateway_fee),
            "final_payable_amount": float(self.final_payable_amount),
            "payment_status": self.payment_status,
            "settlement_date": self.settlement_date.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
