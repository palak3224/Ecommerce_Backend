# models/shop/shop_shipment.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from models.enums import ShipmentStatusEnum 

class ShopShipment(BaseModel):
    __tablename__ = 'shop_shipments'

    shipment_id = db.Column(db.Integer, primary_key=True)
    shop_order_id = db.Column(db.String(50), db.ForeignKey('shop_orders.order_id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id', ondelete='CASCADE'), nullable=False, index=True)
    
    carrier_name = db.Column(db.String(100), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True, index=True)
    shipped_date = db.Column(db.DateTime, nullable=True)
    estimated_delivery_date = db.Column(db.Date, nullable=True)
    actual_delivery_date = db.Column(db.DateTime, nullable=True)
    
    shipment_status = db.Column(db.Enum(ShipmentStatusEnum), nullable=False, default=ShipmentStatusEnum.PENDING_PICKUP)
    
    # ShipRocket specific fields
    shiprocket_order_id = db.Column(db.Integer, nullable=True, index=True)
    shiprocket_shipment_id = db.Column(db.Integer, nullable=True, index=True)
    awb_code = db.Column(db.String(50), nullable=True, index=True)
    courier_id = db.Column(db.Integer, nullable=True)
    pickup_generated = db.Column(db.Boolean, default=False, nullable=False)
    pickup_generated_at = db.Column(db.DateTime, nullable=True)
    
    # Pickup and delivery addresses
    pickup_address_id = db.Column(db.Integer, db.ForeignKey('user_addresses.address_id', ondelete='SET NULL'), nullable=True)
    delivery_address_id = db.Column(db.Integer, db.ForeignKey('user_addresses.address_id', ondelete='SET NULL'), nullable=True)

    # Relationships
    shop_order = db.relationship('ShopOrder', back_populates='shipments')
    shop = db.relationship('Shop', lazy='joined') 
    items = db.relationship('ShopShipmentItem', back_populates='shipment', cascade='all, delete-orphan', lazy='joined', order_by='ShopShipmentItem.shipment_item_id')
    
    # Address relationships
    pickup_address = db.relationship('UserAddress', foreign_keys=[pickup_address_id], lazy='joined')
    delivery_address = db.relationship('UserAddress', foreign_keys=[delivery_address_id], lazy='joined')

    def __repr__(self):
        return f"<ShopShipment id={self.shipment_id} shop_order_id={self.shop_order_id} tracking='{self.tracking_number}'>"

    def serialize(self, include_items=True):
        data = {
            "shipment_id": self.shipment_id,
            "shop_order_id": self.shop_order_id,
            "shop_id": self.shop_id,
            "carrier_name": self.carrier_name,
            "tracking_number": self.tracking_number,
            "shipped_date": self.shipped_date.isoformat() if self.shipped_date else None,
            "estimated_delivery_date": self.estimated_delivery_date.isoformat() if self.estimated_delivery_date else None,
            "actual_delivery_date": self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            "shipment_status": self.shipment_status.value,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
            
            # ShipRocket specific fields
            "shiprocket_order_id": self.shiprocket_order_id,
            "shiprocket_shipment_id": self.shiprocket_shipment_id,
            "awb_code": self.awb_code,
            "courier_id": self.courier_id,
            "pickup_generated": self.pickup_generated,
            "pickup_generated_at": self.pickup_generated_at.isoformat() if self.pickup_generated_at else None,
            "pickup_address_id": self.pickup_address_id,
            "delivery_address_id": self.delivery_address_id,
            "pickup_address": self.pickup_address.serialize() if self.pickup_address else None,
            "delivery_address": self.delivery_address.serialize() if self.delivery_address else None,
        }
        
        if include_items: 
            data["items"] = [item.serialize() for item in (self.items if self.items is not None else [])]
        return data

class ShopShipmentItem(BaseModel): 
    __tablename__ = 'shop_shipment_items'

    shipment_item_id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shop_shipments.shipment_id', ondelete='CASCADE'), nullable=False, index=True)
    shop_order_item_id = db.Column(db.Integer, db.ForeignKey('shop_order_items.order_item_id', ondelete='CASCADE'), nullable=False, index=True)
    
    quantity_shipped = db.Column(db.Integer, nullable=False)

    shipment = db.relationship('ShopShipment', back_populates='items')
    shop_order_item = db.relationship('ShopOrderItem', backref=db.backref('shipment_inclusions', lazy='dynamic'), lazy='joined') 

    __table_args__ = (
        db.UniqueConstraint('shipment_id', 'shop_order_item_id', name='uq_shop_shipment_order_item_inclusion'),
    )

    def __repr__(self):
        return f"<ShopShipmentItem id={self.shipment_item_id} shipment_id={self.shipment_id} shop_order_item_id={self.shop_order_item_id}>"

    def serialize(self):
        shop_order_item_summary = None
        if self.shop_order_item: # shop_order_item is eager loaded
            shop_order_item_summary = {
                "order_item_id": self.shop_order_item.order_item_id,
                "product_name": self.shop_order_item.product_name_at_purchase,
                "sku": self.shop_order_item.sku_at_purchase,
                "quantity": self.shop_order_item.quantity,
                "unit_price": self.shop_order_item.unit_price_inclusive_gst,
            }
        
        return {
            "shipment_item_id": self.shipment_item_id,
            "shipment_id": self.shipment_id,
            "shop_order_item_id": self.shop_order_item_id,
            "quantity_shipped": self.quantity_shipped,
            "shop_order_item": shop_order_item_summary,
        }
