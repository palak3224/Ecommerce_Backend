# controllers/order_controller.py
from flask import jsonify, request, current_app
from models.order import Order, OrderItem, OrderStatusHistory
from models.enums import OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum,CardStatusEnum , MediaType
from models.product_stock import ProductStock
from models.payment_card import PaymentCard
from common.database import db
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import desc, func 
from models.product import Product
from models.product_media import ProductMedia
from models.gst_rule import GSTRule 
from models.shipment import Shipment, ShipmentItem

class OrderController:
    @staticmethod
    def create_order(user_id, order_data):
        """
        Creates a new order, calculates GST in real-time based on the final discounted inclusive price,
        and stores the detailed breakdown.

        Args:
            user_id (int): The ID of the user placing the order.
            order_data (dict): Data from the frontend, expected to contain:
                - items: list of dicts, each with:
                    - product_id (int)
                    - quantity (int)
                    - item_discount_inclusive (str/Decimal, optional): Discount applied to this item's inclusive price.
                                                                        Defaults to 0 if not provided.
                - payment_method (str): From PaymentMethodEnum.
                - payment_card_id (int, optional): Required if card payment.
                - shipping_address_id (int)
                - billing_address_id (int)
                - shipping_amount (str/Decimal, optional): Shipping cost.
                - order_level_discount_amount (str/Decimal, optional): Overall discount on the order.
                - currency (str, optional): Defaults to "USD" or your system default.
                - customer_notes (str, optional)
                - internal_notes (str, optional)
        """
        try:
            db.session.begin_nested()

            payment_card = None
            payment_method_enum = PaymentMethodEnum(order_data.get('payment_method'))
            if payment_method_enum in [PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.DEBIT_CARD]:
                if not order_data.get('payment_card_id'):
                    raise ValueError("Payment card ID is required for card payments")
                payment_card = PaymentCard.query.filter_by(
                    card_id=order_data['payment_card_id'],
                    user_id=user_id,
                    status=CardStatusEnum.ACTIVE 
                ).first()
                if not payment_card:
                    raise ValueError("Invalid or inactive payment card provided.")
                payment_card.update_last_used()

            new_order_items = []
            total_order_base_price_after_all_discounts = Decimal("0.00")
            total_order_gst_amount = Decimal("0.00")
            
            # For item-specific discounts, we don't need to prorate order-level discounts
            # because each item already has its specific discount applied
            
            for cart_item_data in order_data.get('items', []):
                product = Product.query.get(cart_item_data['product_id'])
                if not product: 
                    raise ValueError(f"Product with ID {cart_item_data['product_id']} not found.")
                
                quantity = int(cart_item_data['quantity'])
                if quantity <= 0:
                    raise ValueError(f"Quantity for product {product.product_name} must be positive.")

                current_listed_inclusive_price_per_unit, _ = product.get_current_listed_inclusive_price()
                
                # Get item-specific discount from the cart (promo discount already applied to specific items)
                item_specific_discount_inclusive_per_unit = Decimal(cart_item_data.get('item_discount_inclusive', "0.00"))
                
                # This is the price customer effectively pays for one unit of this item, inclusive of all taxes and discounts
                final_customer_pays_for_item_inclusive_per_unit = current_listed_inclusive_price_per_unit - item_specific_discount_inclusive_per_unit
                
                if final_customer_pays_for_item_inclusive_per_unit < Decimal("0.00"):
                    final_customer_pays_for_item_inclusive_per_unit = Decimal("0.00") # Cannot be negative

                # Find GST rule based on original listed price for rate determination
                applicable_gst_rule = GSTRule.find_applicable_rule(
                    db_session=db.session,
                    product_category_id=product.category_id,
                    product_inclusive_price=current_listed_inclusive_price_per_unit 
                )

                item_gst_rate_percentage = Decimal("0.00")
                if applicable_gst_rule:
                    item_gst_rate_percentage = Decimal(applicable_gst_rule.gst_rate_percentage)
                
                # Back-calculate base price and GST amount from final_customer_pays_for_item_inclusive_per_unit
                denominator = Decimal("1.00") + (item_gst_rate_percentage / Decimal("100.00"))
                final_base_price_for_gst_calc_unit = Decimal("0.00")
                gst_amount_per_unit = Decimal("0.00")

                if denominator > Decimal("0.00"):
                    final_base_price_for_gst_calc_unit = (final_customer_pays_for_item_inclusive_per_unit / denominator).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    gst_amount_per_unit = (final_customer_pays_for_item_inclusive_per_unit - final_base_price_for_gst_calc_unit).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                else:
                    final_base_price_for_gst_calc_unit = final_customer_pays_for_item_inclusive_per_unit

                # Stock check
                product_stock = ProductStock.query.filter_by(product_id=product.product_id).first()
                if not product_stock:
                     raise ValueError(f"Stock record not found for product {product.product_name} (ID: {product.product_id}).")
                if product_stock.stock_qty < quantity:
                    raise ValueError(f"Insufficient stock for product {product.product_name}. Available: {product_stock.stock_qty}, Requested: {quantity}")
                product_stock.stock_qty -= quantity

                order_item = OrderItem(
                    product_id=product.product_id,
                    merchant_id=product.merchant_id,
                    product_name_at_purchase=product.product_name,
                    sku_at_purchase=product.sku,
                    quantity=quantity,
                    final_base_price_for_gst_calc=final_base_price_for_gst_calc_unit,
                    gst_rate_applied_at_purchase=item_gst_rate_percentage,
                    gst_amount_per_unit=gst_amount_per_unit,
                    unit_price_inclusive_gst=final_customer_pays_for_item_inclusive_per_unit, # What customer pays per unit after all discounts
                    line_item_total_inclusive_gst=(final_customer_pays_for_item_inclusive_per_unit * quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    original_listed_inclusive_price_per_unit=current_listed_inclusive_price_per_unit,
                    discount_amount_per_unit_applied=item_specific_discount_inclusive_per_unit # Only item-specific discount
                )
                new_order_items.append(order_item)

                total_order_base_price_after_all_discounts += final_base_price_for_gst_calc_unit * quantity
                total_order_gst_amount += gst_amount_per_unit * quantity
            
            order_subtotal_amount = total_order_base_price_after_all_discounts.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            order_tax_amount = total_order_gst_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            order_shipping_amount = Decimal(order_data.get('shipping_amount', "0.00")).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Calculate total item discounts for record keeping
            total_item_discounts = sum(Decimal(item_data.get('item_discount_inclusive', "0.00")) for item_data in order_data.get('items', []))
            final_order_discount_amount = total_item_discounts

            # Total amount customer pays = (sum of line_item_total_inclusive_gst for all items) + shipping_amount
            calculated_order_total_from_lines = sum(item.line_item_total_inclusive_gst for item in new_order_items)
            final_order_total_amount = (calculated_order_total_from_lines + order_shipping_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # For the `Order` table:
            # subtotal_amount: sum of (base price *after all discounts*)
            # discount_amount: the total item-specific discount amount for record-keeping
            # tax_amount: sum of (GST per item * quantity)
            # total_amount: final amount customer pays
            
            new_order = Order(
                user_id=user_id,
                subtotal_amount=order_subtotal_amount, # Sum of final base prices
                discount_amount=final_order_discount_amount, # Total item-specific discounts
                tax_amount=order_tax_amount,
                shipping_amount=order_shipping_amount,
                total_amount=final_order_total_amount, # Final payable
                currency=order_data.get('currency', current_app.config.get("DEFAULT_CURRENCY", "USD")),
                payment_method=payment_method_enum,
                payment_status=PaymentStatusEnum.PENDING,
                order_status=OrderStatusEnum.PENDING_PAYMENT,
                shipping_address_id=order_data.get('shipping_address_id'),
                billing_address_id=order_data.get('billing_address_id'),
                shipping_method_name=order_data.get('shipping_method_name'),
                customer_notes=order_data.get('customer_notes'),
                internal_notes=order_data.get('internal_notes') # Good place for promo code used
            )
            new_order.items.extend(new_order_items)

            status_history = OrderStatusHistory(
                status=OrderStatusEnum.PENDING_PAYMENT,
                changed_by_user_id=user_id,
                notes=f"Order created. {order_data.get('internal_notes', '')}".strip()
            )
            new_order.status_history.append(status_history)

            db.session.add(new_order)
            db.session.flush() 

            if payment_card:
                payment_succeeded_simulation = True # Simulate success
                if payment_succeeded_simulation:
                    new_order.payment_status = PaymentStatusEnum.SUCCESSFUL
                    new_order.order_status = OrderStatusEnum.PROCESSING
                    new_order.payment_gateway_transaction_id = f"SIM_TXN_{new_order.order_id}"
                    
                    payment_history_notes = f"Payment successful via {payment_card.card_brand} ending in {payment_card.last_four_digits}."
                    if new_order.payment_gateway_transaction_id:
                        payment_history_notes += f" Transaction ID: {new_order.payment_gateway_transaction_id}."

                    payment_success_history = OrderStatusHistory(
                        order_id=new_order.order_id, status=new_order.order_status, 
                        changed_by_user_id=user_id, notes=payment_history_notes
                    )
                    db.session.add(payment_success_history)
                else: 
                    new_order.payment_status = PaymentStatusEnum.FAILED
                    new_order.order_status = OrderStatusEnum.PAYMENT_FAILED
                    payment_failure_history = OrderStatusHistory(
                        order_id=new_order.order_id, status=OrderStatusEnum.PAYMENT_FAILED,
                        changed_by_user_id=user_id, notes=f"Payment failed for card ending in {payment_card.last_four_digits}."
                    )
                    db.session.add(payment_failure_history)
                    for item_in_order in new_order.items:
                        stock_to_revert = ProductStock.query.filter_by(product_id=item_in_order.product_id).first()
                        if stock_to_revert: stock_to_revert.stock_qty += item_in_order.quantity
                    current_app.logger.info(f"Stock reverted for failed payment on order attempt by user {user_id}.")
            
            db.session.commit()
            return new_order.serialize(include_items=True, include_history=True)

        except ValueError as ve:
            db.session.rollback()
            current_app.logger.error(f"Order creation ValueError for user {user_id}: {ve}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Order creation generic error for user {user_id}: {e}", exc_info=True)
            raise
        
    @staticmethod
    def get_order(order_id):
        order = Order.query.options(
            db.joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.media), # Eager load product media
            db.joinedload(Order.shipping_address_obj),
            db.joinedload(Order.billing_address_obj),
            db.joinedload(Order.status_history).joinedload(OrderStatusHistory.changed_by_user),
            db.joinedload(Order.shipments).joinedload(Shipment.items).joinedload(ShipmentItem.order_item)
        ).get(order_id) # Use .get() for primary key lookup
        
        if not order:
            return None
        return order.serialize(include_items=True, include_history=True, include_shipments=True)

    @staticmethod
    def get_user_orders(user_id, page=1, per_page=10, status_filter_str=None): # Renamed status to status_filter_str
        query = Order.query.filter_by(user_id=user_id)
        
        if status_filter_str:
            try:
                status_enum = OrderStatusEnum(status_filter_str.lower()) # Convert to lower for case-insensitivity
                query = query.filter(Order.order_status == status_enum)
            except ValueError:
                current_app.logger.warning(f"Invalid order status filter: {status_filter_str}")
                # Optionally, raise an error or return empty if status is invalid
                # For now, it ignores invalid status
                pass 
        
        # Eager load items for efficiency in serialization loop
        paginated_orders = query.options(db.joinedload(Order.items))\
                                .order_by(Order.order_date.desc())\
                                .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'orders': [order.serialize(include_items=True) for order in paginated_orders.items], # include_items=True
            'total': paginated_orders.total,
            'pages': paginated_orders.pages,
            'current_page': paginated_orders.page,
            'per_page': paginated_orders.per_page,
            'has_next': paginated_orders.has_next,
            'has_prev': paginated_orders.has_prev,
        }

    @staticmethod
    def update_order_status(order_id, new_status_enum: OrderStatusEnum, user_id_performing_action, notes=None):
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found.")

        if order.order_status == new_status_enum:
            current_app.logger.info(f"Order {order_id} already in status {new_status_enum.value}. No update performed.")
            return order.serialize(include_items=True, include_history=True) # Or return a specific message

        previous_status_val = order.order_status.value
        order.order_status = new_status_enum
        
        history_note = notes or f"Order status changed from {previous_status_val} to {new_status_enum.value}."
        status_history = OrderStatusHistory(
            order_id=order.order_id, # Ensure order_id is linked
            status=new_status_enum,
            changed_by_user_id=user_id_performing_action,
            notes=history_note
        )
        db.session.add(status_history)
        
        # Handle specific status transitions if needed (e.g., if DELIVERED, update actual_delivery_date)
        if new_status_enum == OrderStatusEnum.DELIVERED and hasattr(order, 'actual_delivery_date') and order.actual_delivery_date is None:
            # If you have shipments, this might be set on the shipment.
            # For simplicity, if order has direct actual_delivery_date:
            # order.actual_delivery_date = datetime.now(timezone.utc)
            pass


        try:
            db.session.commit()
            return order.serialize(include_items=True, include_history=True)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating order status for {order_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def update_payment_status(order_id, payment_status_enum: PaymentStatusEnum, transaction_id=None, gateway_name=None, changed_by_user_id=None):
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order not found with ID: {order_id}")

        order.payment_status = payment_status_enum
        if transaction_id:
            order.payment_gateway_transaction_id = transaction_id
        if gateway_name:
            order.payment_gateway_name = gateway_name

        history_notes = f"Payment status updated to {payment_status_enum.value}."
        if gateway_name: history_notes += f" Gateway: {gateway_name}."
        if transaction_id: history_notes += f" Txn ID: {transaction_id}."

        # Automatically adjust order status based on payment status
        current_order_status_is_payment_related = order.order_status in [
            OrderStatusEnum.PENDING_PAYMENT, OrderStatusEnum.PAYMENT_FAILED
        ]

        if payment_status_enum == PaymentStatusEnum.SUCCESSFUL and current_order_status_is_payment_related:
            order.order_status = OrderStatusEnum.PROCESSING # Or AWAITING_FULFILLMENT
            history_notes += f" Order status changed to {order.order_status.value}."
        elif payment_status_enum == PaymentStatusEnum.FAILED and current_order_status_is_payment_related:
            order.order_status = OrderStatusEnum.PAYMENT_FAILED
            history_notes += f" Order status changed to {order.order_status.value}."
            # Stock should be reverted here if not done immediately upon gateway failure response
            # This depends on your payment flow. If payment is attempted, fails, and this method is called,
            # then stock revert here is appropriate.
            for item_in_order in order.items:
                stock_to_revert = ProductStock.query.filter_by(product_id=item_in_order.product_id).first()
                if stock_to_revert:
                    stock_to_revert.stock_qty += item_in_order.quantity
            current_app.logger.info(f"Stock reverted due to payment status update to FAILED for order {order_id}.")


        status_history = OrderStatusHistory(
            order_id=order.order_id, # Ensure order_id is linked
            status=order.order_status, # Log the resulting order_status
            changed_by_user_id=changed_by_user_id, # Can be system (None) or user
            notes=history_notes
        )
        db.session.add(status_history)
        
        try:
            db.session.commit()
            return order.serialize(include_items=True, include_history=True)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating payment status for {order_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def cancel_order(order_id, user_id_cancelling, notes=None, cancelled_by_role="CUSTOMER"):
        # cancelled_by_role can be "CUSTOMER", "MERCHANT", "ADMIN"
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        if order.order_status in [OrderStatusEnum.DELIVERED, OrderStatusEnum.SHIPPED, OrderStatusEnum.CANCELLED_BY_CUSTOMER, OrderStatusEnum.CANCELLED_BY_MERCHANT, OrderStatusEnum.CANCELLED_BY_ADMIN]:
            raise ValueError(f"Order is already {order.order_status.value} and cannot be cancelled by {cancelled_by_role}.")
        
        # Determine the correct cancelled status based on role
        if cancelled_by_role == "MERCHANT":
            new_status = OrderStatusEnum.CANCELLED_BY_MERCHANT
        elif cancelled_by_role == "ADMIN":
            new_status = OrderStatusEnum.CANCELLED_BY_ADMIN
        else: # Default to CUSTOMER
            new_status = OrderStatusEnum.CANCELLED_BY_CUSTOMER


        order.order_status = new_status
        # If payment was successful, cancellation might trigger a refund process.
        # For now, we just mark as cancelled. Refund is a separate flow.
        if order.payment_status == PaymentStatusEnum.SUCCESSFUL:
            # Potentially set order.payment_status to PENDING_REFUND or trigger refund
            current_app.logger.info(f"Order {order_id} cancelled by {cancelled_by_role} with successful payment. Manual refund may be required.")

        cancellation_note = notes or f"Order cancelled by {cancelled_by_role.lower()}."
        status_history = OrderStatusHistory(
            order_id=order.order_id,
            status=new_status,
            changed_by_user_id=user_id_cancelling,
            notes=cancellation_note
        )
        db.session.add(status_history)
        
        # Restore stock quantities
        for item in order.items:
            if item.product_id:
                product_stock = ProductStock.query.filter_by(product_id=item.product_id).first()
                if product_stock:
                    product_stock.stock_qty += item.quantity
        
        try:
            db.session.commit()
            return order.serialize(include_items=True, include_history=True)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling order {order_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def get_all_orders(page=1, per_page=10, status_filter_str=None, merchant_id_filter=None): # Renamed params
        query = Order.query
        
        if status_filter_str:
            try:
                status_enum = OrderStatusEnum(status_filter_str.lower())
                query = query.filter(Order.order_status == status_enum)
            except ValueError:
                current_app.logger.warning(f"Admin/Merchant: Invalid order status filter: {status_filter_str}")
                pass
                
        if merchant_id_filter:
            # Ensure distinct orders if a merchant has multiple items in one order
            query = query.join(OrderItem).filter(OrderItem.merchant_id == merchant_id_filter).distinct(Order.order_id)
        
        paginated_orders = query.options(db.joinedload(Order.items))\
                                .order_by(Order.order_date.desc())\
                                .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'orders': [order.serialize(include_items=True) for order in paginated_orders.items],
            'total': paginated_orders.total,
            'pages': paginated_orders.pages,
            'current_page': paginated_orders.page,
            'per_page': paginated_orders.per_page,
            'has_next': paginated_orders.has_next,
            'has_prev': paginated_orders.has_prev,
        }

    @staticmethod
    def track_order(order_id):
        order = Order.query.options(
            db.joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.media),
            db.joinedload(Order.shipping_address_obj),
            db.joinedload(Order.status_history).joinedload(OrderStatusHistory.changed_by_user) 
        ).get(order_id)
        
        if not order:
            raise ValueError(f"Order not found with ID: {order_id}")

        tracking_items = []
        for item in order.items:
            product_image = None
            if item.product and item.product.media:
                # Find the first image media, ordered by sort_order
                image_media = sorted([m for m in item.product.media if m.type == MediaType.IMAGE], key=lambda m: m.sort_order)
                if image_media:
                    product_image = image_media[0].url
            
            # Use prices from OrderItem as they reflect values at time of purchase
            tracking_item = {
                "order_item_id": item.order_item_id,
                "product_name": item.product_name_at_purchase,
                "quantity": item.quantity,
                "unit_price_inclusive_gst": str(item.unit_price_inclusive_gst), # What customer paid per unit
                "line_total_inclusive_gst": str(item.line_item_total_inclusive_gst), # Total for this line
                "product_image": product_image,
                "item_status": item.item_status.value
            }
            tracking_items.append(tracking_item)

        serialized_history = []
        if order.status_history: # Check if history exists
             # Ensure status_history is queryable (if lazy='dynamic') or directly iterable
            history_query = order.status_history if hasattr(order.status_history, 'limit') else order.status_history
            for hist in history_query.limit(10).all() if hasattr(history_query, 'limit') else history_query[:10]:
                serialized_history.append({
                    "status": hist.status.value,
                    "changed_at": hist.changed_at.isoformat(),
                    "notes": hist.notes,
                    "changed_by": hist.changed_by_user.first_name if hist.changed_by_user else "System"
                })


        tracking_info = {
            "order_id": order.order_id,
            "order_status": order.order_status.value,
            "order_date": order.order_date.isoformat(),
            "total_amount": str(order.total_amount),
            "currency": order.currency,
            "shipping_address": order.shipping_address_obj.serialize() if order.shipping_address_obj else None,
            "items": tracking_items,
            "status_history": serialized_history
        }
        return tracking_info
         