# models/shipment.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from models.enums import ShipmentStatusEnum 

class Shipment(BaseModel):
    __tablename__ = 'shipments'

    shipment_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), db.ForeignKey('orders.order_id', ondelete='CASCADE'), nullable=False, index=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id', ondelete='SET NULL'), nullable=True, index=True) 
    
    carrier_name = db.Column(db.String(100), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True, index=True)
    shipped_date = db.Column(db.DateTime, nullable=True)
    estimated_delivery_date = db.Column(db.Date, nullable=True)
    actual_delivery_date = db.Column(db.DateTime, nullable=True)
    
    shipment_status = db.Column(db.Enum(ShipmentStatusEnum), nullable=False, default=ShipmentStatusEnum.PENDING_PICKUP)
    
    

    order = db.relationship('Order', back_populates='shipments')
    merchant = db.relationship('MerchantProfile', lazy='joined') 
    items = db.relationship('ShipmentItem', back_populates='shipment', cascade='all, delete-orphan', lazy='joined', order_by='ShipmentItem.shipment_item_id')

    def __repr__(self):
        return f"<Shipment id={self.shipment_id} order_id={self.order_id} tracking='{self.tracking_number}'>"

    def serialize(self, include_items=True):
        data = {
            "shipment_id": self.shipment_id,
            "order_id": self.order_id,
            "merchant_id": self.merchant_id,
            "carrier_name": self.carrier_name,
            "tracking_number": self.tracking_number,
            "shipped_date": self.shipped_date.isoformat() if self.shipped_date else None,
            "estimated_delivery_date": self.estimated_delivery_date.isoformat() if self.estimated_delivery_date else None,
            "actual_delivery_date": self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            "shipment_status": self.shipment_status.value,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }
        
        if include_items: data["items"] = [item.serialize() for item in (self.items if self.items is not None else [])]
        return data

class ShipmentItem(BaseModel): 
    __tablename__ = 'shipment_items'

    shipment_item_id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.shipment_id', ondelete='CASCADE'), nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.order_item_id', ondelete='CASCADE'), nullable=False, index=True)
    
    quantity_shipped = db.Column(db.Integer, nullable=False)


    shipment = db.relationship('Shipment', back_populates='items')
    order_item = db.relationship('OrderItem', backref=db.backref('shipment_inclusions', lazy='dynamic'), lazy='joined') 

    __table_args__ = (
        db.UniqueConstraint('shipment_id', 'order_item_id', name='uq_shipment_order_item_inclusion'),
    )

    def __repr__(self):
        return f"<ShipmentItem id={self.shipment_item_id} shipment_id={self.shipment_id} order_item_id={self.order_item_id}>"

    def serialize(self):
        order_item_summary = None
        if self.order_item: # order_item is eager loaded
            order_item_summary = {
                "order_item_id": self.order_item.order_item_id,
                "product_name": self.order_item.product_name_at_purchase,
                "sku": self.order_item.sku_at_purchase,
                "variant_details": self.order_item.variant_details_at_purchase
            }
        return {
            "shipment_item_id": self.shipment_item_id,
            "shipment_id": self.shipment_id,
            "order_item_id": self.order_item_id,
            "quantity_shipped": self.quantity_shipped,
            "order_item_details": order_item_summary,
        }