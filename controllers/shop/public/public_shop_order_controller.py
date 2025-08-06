# controllers/shop/public/public_shop_order_controller.py
import logging
from flask import jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from common.response import success_response, error_response
from models.shop.shop_order import ShopOrder, ShopOrderItem, ShopOrderStatusHistory
from models.shop.shop_product import ShopProduct
from models.shop.shop_product_stock import ShopProductStock
from models.shop.shop_cart import ShopCartItem
from models.shop.shop_gst_rule import ShopGSTRule
from models.enums import OrderStatusEnum, PaymentStatusEnum, OrderItemStatusEnum
from models.user_address import UserAddress
from models.shop.shop import Shop
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

class PublicShopOrderController:
    
    @staticmethod
    def create_shop_order(shop_id, order_data):
        """
        Create a new shop order from cart items or direct purchase
        """
        try:
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate shop exists and is active
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).first()
            if not shop:
                return error_response("Shop not found or inactive", 404)

            # Validate required order data
            required_fields = ['shipping_address_id', 'payment_method']
            for field in required_fields:
                if field not in order_data:
                    return error_response(f"Missing required field: {field}", 400)

            # Validate shipping address belongs to user
            shipping_address = UserAddress.query.filter_by(
                address_id=order_data['shipping_address_id'],
                user_id=user_id
            ).first()
            if not shipping_address:
                return error_response("Invalid shipping address", 400)

            # Get cart items for this shop
            cart_items = ShopCartItem.query.options(
                joinedload(ShopCartItem.product).joinedload(ShopProduct.stock)
            ).filter_by(user_id=user_id, shop_id=shop_id).all()

            if not cart_items:
                return error_response("No items in cart for this shop", 400)

            # Validate stock availability and calculate totals
            order_items = []
            subtotal = Decimal('0.00')
            
            for cart_item in cart_items:
                product = cart_item.product
                if not product or not product.active_flag or not product.is_published:
                    return error_response(f"Product '{product.name if product else 'Unknown'}' is not available", 400)

                # Check stock availability
                stock = product.stock
                if not stock or stock.stock_qty < cart_item.quantity:
                    available_qty = stock.stock_qty if stock else 0
                    return error_response(
                        f"Insufficient stock for '{product.name}'. Available: {available_qty}, Requested: {cart_item.quantity}", 
                        400
                    )

                # Calculate pricing with GST
                unit_price = product.selling_price or product.cost_price or Decimal('0.00')
                
                # Find applicable GST rule for this product
                applicable_gst_rule = ShopGSTRule.find_applicable_rule(
                    db_session=db.session,
                    shop_id=shop_id,
                    product_category_id=product.category_id,
                    product_inclusive_price=unit_price
                )
                
                item_gst_rate_percentage = Decimal("0.00")
                if applicable_gst_rule:
                    item_gst_rate_percentage = Decimal(applicable_gst_rule.gst_rate_percentage)
                
                # Back-calculate base price and GST amount from unit price (assuming unit price is inclusive)
                denominator = Decimal("1.00") + (item_gst_rate_percentage / Decimal("100.00"))
                final_base_price_for_gst_calc = unit_price / denominator
                gst_amount_per_unit = unit_price - final_base_price_for_gst_calc
                
                # Calculate totals for this line item
                line_gst_amount = gst_amount_per_unit * cart_item.quantity
                line_total_base = final_base_price_for_gst_calc * cart_item.quantity
                line_total_inclusive = unit_price * cart_item.quantity
                
                subtotal += line_total_base  # Base amount without GST
                tax_amount += line_gst_amount  # Total GST amount

                # Prepare order item data
                order_item_data = {
                    'product_id': product.product_id,
                    'product_name_at_purchase': product.name,
                    'sku_at_purchase': product.sku,
                    'quantity': cart_item.quantity,
                    'final_base_price_for_gst_calc': final_base_price_for_gst_calc,
                    'unit_price_inclusive_gst': unit_price,
                    'line_item_total_inclusive_gst': line_total_inclusive,
                    'original_listed_inclusive_price_per_unit': unit_price,
                    'gst_rate_percentage': item_gst_rate_percentage,
                    'line_gst_amount': line_gst_amount,
                    'selected_attributes': cart_item.selected_attributes,
                    'shop_id': shop_id
                }
                order_items.append(order_item_data)

            # Calculate totals
            discount_amount = Decimal('0.00')
            shipping_amount = Decimal('0.00')  # Global shipping rules
            # subtotal already contains base amount without GST
            # tax_amount already contains total GST amount
            total_amount = subtotal + tax_amount + shipping_amount - discount_amount

            # Create the shop order
            shop_order = ShopOrder(
                shop_id=shop_id,
                user_id=user_id,
                subtotal_amount=subtotal,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                shipping_amount=shipping_amount,
                total_amount=total_amount,
                currency=order_data.get('currency', 'USD'),
                payment_method=order_data['payment_method'],
                payment_status=PaymentStatusEnum.PENDING,
                shipping_address_id=order_data['shipping_address_id'],
                billing_address_id=order_data.get('billing_address_id', order_data['shipping_address_id']),
                shipping_method_name=order_data.get('shipping_method_name', 'Standard Shipping'),
                customer_notes=order_data.get('customer_notes'),
                order_status=OrderStatusEnum.PENDING_PAYMENT
            )

            db.session.add(shop_order)
            db.session.flush()  # Get the order_id

            # Create order items and update stock
            for item_data in order_items:
                order_item = ShopOrderItem(
                    order_id=shop_order.order_id,
                    **item_data
                )
                db.session.add(order_item)

                # Update stock quantity
                product = ShopProduct.query.get(item_data['product_id'])
                if product and product.stock:
                    product.stock.stock_qty -= item_data['quantity']

            # Create initial status history
            status_history = ShopOrderStatusHistory(
                order_id=shop_order.order_id,
                status=OrderStatusEnum.PENDING_PAYMENT,
                changed_by_user_id=user_id,
                notes="Order created"
            )
            db.session.add(status_history)

            # Clear cart items for this shop
            for cart_item in cart_items:
                db.session.delete(cart_item)

            db.session.commit()

            return success_response(
                "Order created successfully",
                shop_order.serialize(include_items=True)
            )

        except Exception as e:
            logger.error(f"Error creating shop order: {str(e)}")
            db.session.rollback()
            return error_response("Failed to create order", 500)

    @staticmethod
    def get_user_shop_orders(shop_id, page=1, per_page=10):
        """
        Get user's orders for a specific shop
        """
        try:
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate shop exists
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).first()
            if not shop:
                return error_response("Shop not found or inactive", 404)

            # Query user's orders for this shop
            orders_query = ShopOrder.query.filter_by(
                user_id=user_id,
                shop_id=shop_id
            ).order_by(ShopOrder.order_date.desc())

            # Apply pagination
            paginated_orders = orders_query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )

            orders_data = [order.serialize(include_items=True) for order in paginated_orders.items]

            return success_response(
                "Orders retrieved successfully",
                {
                    'orders': orders_data,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': paginated_orders.total,
                        'pages': paginated_orders.pages,
                        'has_next': paginated_orders.has_next,
                        'has_prev': paginated_orders.has_prev
                    }
                }
            )

        except Exception as e:
            logger.error(f"Error getting user shop orders: {str(e)}")
            return error_response("Failed to get orders", 500)

    @staticmethod
    def get_shop_order_details(shop_id, order_id):
        """
        Get detailed information for a specific shop order
        """
        try:
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate shop exists
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).first()
            if not shop:
                return error_response("Shop not found or inactive", 404)

            # Get order with user validation
            order = ShopOrder.query.filter_by(
                order_id=order_id,
                shop_id=shop_id,
                user_id=user_id
            ).first()

            if not order:
                return error_response("Order not found", 404)

            return success_response(
                "Order details retrieved successfully",
                order.serialize(include_items=True, include_history=True)
            )

        except Exception as e:
            logger.error(f"Error getting shop order details: {str(e)}")
            return error_response("Failed to get order details", 500)

    @staticmethod
    def get_all_shop_orders(page=1, per_page=20, shop_id=None, status=None):
        """
        Get all shop orders (for superadmin access)
        """
        try:
            # This method is for superadmin access - should be protected at route level
            query = ShopOrder.query

            # Filter by shop if specified
            if shop_id:
                query = query.filter_by(shop_id=shop_id)

            # Filter by status if specified
            if status:
                query = query.filter_by(order_status=status)

            # Order by newest first
            query = query.order_by(ShopOrder.order_date.desc())

            # Apply pagination
            paginated_orders = query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )

            orders_data = [order.serialize(include_items=True) for order in paginated_orders.items]

            return success_response(
                "All shop orders retrieved successfully",
                {
                    'orders': orders_data,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': paginated_orders.total,
                        'pages': paginated_orders.pages,
                        'has_next': paginated_orders.has_next,
                        'has_prev': paginated_orders.has_prev
                    }
                }
            )

        except Exception as e:
            logger.error(f"Error getting all shop orders: {str(e)}")
            return error_response("Failed to get orders", 500)

    @staticmethod
    def update_order_status(order_id, new_status, notes=None):
        """
        Update shop order status (for admin/shop management)
        """
        try:
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            order = ShopOrder.query.filter_by(order_id=order_id).first()
            if not order:
                return error_response("Order not found", 404)

            # Update order status
            old_status = order.order_status
            order.order_status = new_status

            # Create status history entry
            status_history = ShopOrderStatusHistory(
                order_id=order_id,
                status=new_status,
                changed_by_user_id=user_id,
                notes=notes or f"Status changed from {old_status.value} to {new_status.value}"
            )
            db.session.add(status_history)
            db.session.commit()

            return success_response(
                "Order status updated successfully",
                order.serialize(include_items=True, include_history=True)
            )

        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            db.session.rollback()
            return error_response("Failed to update order status", 500)
