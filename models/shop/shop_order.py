# models/shop/shop_order.py
import uuid
from datetime import datetime, timezone
from common.database import db, BaseModel
from models.enums import OrderStatusEnum, PaymentMethodEnum, PaymentStatusEnum, OrderItemStatusEnum
from decimal import Decimal, ROUND_HALF_UP
import json


def generate_shop_order_id_string(shop_id):
    """Generate shop-specific order ID with format: SHOP{shop_id}-ORD-{timestamp}-{random}"""
    now = datetime.now(timezone.utc)
    return f"SHOP{shop_id}-ORD-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

class ShopOrder(BaseModel):
    __tablename__ = 'shop_orders'

    order_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id', ondelete='CASCADE'), nullable=False, index=True)
    
    order_status = db.Column(db.Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True)
    order_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    subtotal_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0.00'), server_default='0.00')
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0.00'), server_default='0.00')
    shipping_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0.00'), server_default='0.00')
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")

    payment_method = db.Column(db.Enum(PaymentMethodEnum), nullable=True)
    payment_status = db.Column(db.Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING, index=True)
    payment_gateway_transaction_id = db.Column(db.String(255), nullable=True, index=True)
    payment_gateway_name = db.Column(db.String(50), nullable=True)

    shipping_address_id = db.Column(db.Integer, db.ForeignKey('user_addresses.address_id', ondelete='SET NULL'), nullable=True)
    billing_address_id = db.Column(db.Integer, db.ForeignKey('user_addresses.address_id', ondelete='SET NULL'), nullable=True)
    
    shipping_method_name = db.Column(db.String(100), nullable=True)
    customer_notes = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref='shop_orders')
    shop = db.relationship('Shop', backref='orders')
    
    items = db.relationship('ShopOrderItem', back_populates='order', cascade='all, delete-orphan', lazy='joined', order_by='ShopOrderItem.order_item_id')
    status_history = db.relationship('ShopOrderStatusHistory', back_populates='order', cascade='all, delete-orphan', lazy='dynamic', order_by='ShopOrderStatusHistory.changed_at.desc()')
    shipments = db.relationship('ShopShipment', back_populates='shop_order', cascade='all, delete-orphan', lazy='dynamic')
    
    shipping_address_obj = db.relationship('UserAddress', foreign_keys=[shipping_address_id], lazy='joined')
    billing_address_obj = db.relationship('UserAddress', foreign_keys=[billing_address_id], lazy='joined')

    def __init__(self, shop_id=None, **kwargs):
        if shop_id and 'order_id' not in kwargs:
            kwargs['order_id'] = generate_shop_order_id_string(shop_id)
        # Ensure the DB column shop_id is set on the instance
        if shop_id is not None and 'shop_id' not in kwargs:
            kwargs['shop_id'] = shop_id
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ShopOrder id={self.order_id} shop_id={self.shop_id} user_id={self.user_id} status='{self.order_status.value}'>"

    def serialize(self, include_items=True, include_history=False):
        data = {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "shop_id": self.shop_id,
            "order_status": self.order_status.value,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "subtotal_amount": str(self.subtotal_amount),
            "discount_amount": str(self.discount_amount),
            "tax_amount": str(self.tax_amount),
            "shipping_amount": str(self.shipping_amount),
            "total_amount": str(self.total_amount),
            "currency": self.currency,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "payment_status": self.payment_status.value if self.payment_status else None,
            "payment_gateway_transaction_id": self.payment_gateway_transaction_id,
            "shipping_address_id": self.shipping_address_id,
            "billing_address_id": self.billing_address_id,
            "shipping_method_name": self.shipping_method_name,
            "customer_notes": self.customer_notes,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
            "shipping_address_details": self.shipping_address_obj.serialize() if self.shipping_address_obj else None,
            "billing_address_details": self.billing_address_obj.serialize() if self.billing_address_obj else None,
        }
        
        if include_items: 
            data["items"] = [item.serialize() for item in (self.items if self.items is not None else [])]
        if include_history: 
            data["status_history"] = [hist.serialize() for hist in self.status_history.all()] 
        
        return data


class ShopOrderItem(BaseModel): 
    __tablename__ = 'shop_order_items'

    order_item_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), db.ForeignKey('shop_orders.order_id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('shop_products.product_id', ondelete='SET NULL'), nullable=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id', ondelete='CASCADE'), nullable=False, index=True)

    product_name_at_purchase = db.Column(db.String(255), nullable=False)
    sku_at_purchase = db.Column(db.String(100), nullable=True) 

    quantity = db.Column(db.Integer, nullable=False)
    final_base_price_for_gst_calc = db.Column(db.Numeric(10, 2), nullable=False) 
    
    gst_rate_applied_at_purchase = db.Column(db.Numeric(5,2), nullable=True)
    gst_amount_per_unit = db.Column(db.Numeric(12, 2), nullable=True) # GST amount for a single unit

    # Final price for one unit, inclusive of its GST (final_base_price_for_gst_calc + gst_amount_per_unit)
    unit_price_inclusive_gst = db.Column(db.Numeric(10, 2), nullable=False)

    # Store selected attributes as JSON
    selected_attributes = db.Column(db.Text, nullable=True)  # JSON string of selected attributes

    item_status = db.Column(db.Enum(OrderItemStatusEnum), nullable=False, default=OrderItemStatusEnum.PENDING_FULFILLMENT)

    # Total for this line item (quantity * unit_price_inclusive_gst)
    line_item_total_inclusive_gst = db.Column(db.Numeric(12, 2), nullable=False)

    # Original GST-inclusive price listed by shop for this product (standard or special) before cart discounts. For reference.
    original_listed_inclusive_price_per_unit = db.Column(db.Numeric(10,2), nullable=True)
    # Amount of discount applied to this item from cart-level promotions, calculated on a per-unit pre-GST basis.
    discount_amount_per_unit_applied = db.Column(db.Numeric(10,2), default=Decimal("0.00"))

    # Relationships
    order = db.relationship('ShopOrder', back_populates='items')
    product = db.relationship('ShopProduct', lazy='select')
    shop = db.relationship('Shop', lazy='select')

    def get_selected_attributes(self):
        """Get selected attributes as a dictionary"""
        if self.selected_attributes:
            try:
                return json.loads(self.selected_attributes)
            except json.JSONDecodeError:
                return {}
        return {}

    def serialize(self):
        total_gst_for_line_item = (self.gst_amount_per_unit or Decimal(0)) * self.quantity
        
        # Get product image from shop product media
        product_image = None
        if self.product and hasattr(self.product, 'media') and self.product.media:
            # Find the primary image first, then fallback to first available
            primary_media = [m for m in self.product.media if m.is_primary and m.deleted_at is None]
            if primary_media:
                product_image = primary_media[0].url
            else:
                # Fallback to first available image
                available_media = [m for m in self.product.media if m.deleted_at is None]
                if available_media:
                    product_image = available_media[0].url
        
        return {
            "order_item_id": self.order_item_id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "shop_id": self.shop_id,
            "product_name_at_purchase": self.product_name_at_purchase,
            "sku_at_purchase": self.sku_at_purchase,
            "quantity": self.quantity,

            # Internal GST calculation fields
            "final_base_price_for_gst_calc_unit": str(self.final_base_price_for_gst_calc), # Pre-GST, post-discount unit price
            "gst_rate_applied_at_purchase": str(self.gst_rate_applied_at_purchase) if self.gst_rate_applied_at_purchase is not None else None,
            "gst_amount_per_unit": str(self.gst_amount_per_unit) if self.gst_amount_per_unit is not None else None,
            "total_gst_for_line_item": str(total_gst_for_line_item.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),

            "unit_price_inclusive_gst": str(self.unit_price_inclusive_gst), # What customer effectively pays per unit after all
            "line_item_total_inclusive_gst": str(self.line_item_total_inclusive_gst), # Total for this line
            
            "original_listed_inclusive_price_per_unit": str(self.original_listed_inclusive_price_per_unit) if self.original_listed_inclusive_price_per_unit is not None else None,
            "discount_amount_per_unit_applied": str(self.discount_amount_per_unit_applied),
            
            # Frontend compatibility field names
            "unit_price_at_purchase": str(self.unit_price_inclusive_gst),
            "item_subtotal_amount": str(self.line_item_total_inclusive_gst),
            "final_price_for_item": str(self.line_item_total_inclusive_gst),
            "selected_attributes": self.get_selected_attributes(),
            "product_image": product_image,  # Add product image

            "item_status": self.item_status.value,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }


class ShopOrderStatusHistory(BaseModel): 
    __tablename__ = 'shop_order_status_history'

    history_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), db.ForeignKey('shop_orders.order_id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.Enum(OrderStatusEnum), nullable=False)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    order = db.relationship('ShopOrder', back_populates='status_history')
    changed_by_user = db.relationship('User', lazy='joined') 

    def __repr__(self):
        return f"<ShopOrderStatusHistory order_id={self.order_id} status='{self.status.value}'>"

    def serialize(self):
        return {
            "history_id": self.history_id,
            "order_id": self.order_id,
            "status": self.status.value,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by_user_id": self.changed_by_user_id,
            "user_email": self.changed_by_user.email if self.changed_by_user else None, 
            "notes": self.notes,
        }
