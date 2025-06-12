from sqlalchemy import and_, extract, func, tuple_
from decimal import Decimal
from datetime import datetime, date
import logging
from common.database import db
from models.order import Order, OrderItem
from models.product import Product
from models.category import Category
from auth.models.models import MerchantProfile, User
from models.enums import OrderStatusEnum, PaymentStatusEnum
import calendar

logger = logging.getLogger(__name__)

class MerchantDashboardController:

    # For getting recent five orders for a particular merchant
    @staticmethod
    def get_recent_orders(user_id):
        try:
            # Step 1: Get the merchant profile using user_id
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Step 2: Join Order -> OrderItem -> User, filter by OrderItem.merchant_id
            recent_orders = (
                db.session.query(Order, User)
                .join(OrderItem, Order.order_id == OrderItem.order_id)   # use order_id here
                .join(User, Order.user_id == User.id)
                .filter(OrderItem.merchant_id == merchant.id)
                .order_by(Order.created_at.desc())
                .limit(5)
                .all()
            )

            # Step 3: Format the response
            orders_list = []
            for order, customer in recent_orders:
                customer_name = f"{customer.first_name} {customer.last_name}" if customer else "Unknown Customer"
                orders_list.append({
                    "order_id": order.order_id,
                    "customer_name": customer_name,
                    "total_amount": order.total_amount,
                    "order_status": order.order_status.value,
                    "payment_status": order.payment_status.value,
                    "order_date": order.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })

            return orders_list

        except Exception as e:
            logger.error(f"Error fetching recent orders: {str(e)}")
            raise e
        


    # For getting monthly metrices and difference from previous month
    @staticmethod
    def get_monthly_summary(user_id):
        try:
            # Get the merchant
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            now = datetime.now()
            current_month = now.month
            current_year = now.year
            prev_month = current_month - 1 if current_month > 1 else 12
            prev_year = current_year if current_month > 1 else current_year - 1

            def fetch_monthly_data(month, year):
                stats = (
                    db.session.query(
                        func.coalesce(func.sum(Order.total_amount), 0).label("total_sales"),
                        func.count(func.distinct(Order.order_id)).label("total_orders")
                    )
                    .join(OrderItem, Order.order_id == OrderItem.order_id)
                    .filter(
                        OrderItem.merchant_id == merchant.id,
                        extract('month', Order.order_date) == month,
                        extract('year', Order.order_date) == year,
                        # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                        # Order.order_status == OrderStatusEnum.DELIVERED
                    )
                    .first()
                )

                total_sales = float(stats.total_sales or 0)
                total_orders = stats.total_orders or 0
                avg_order_value = total_sales / total_orders if total_orders > 0 else 0

                return {
                    "total_sales": total_sales,
                    "total_orders": total_orders,
                    "avg_order_value": avg_order_value
                }

            current = fetch_monthly_data(current_month, current_year)
            previous = fetch_monthly_data(prev_month, prev_year)

            def calc_percentage(curr, prev):
                if prev == 0:
                    return 100.0 if curr > 0 else 0.0
                return round(((curr - prev) / prev) * 100, 2)

            return {
                "total_sales": {
                    "value": current["total_sales"],
                    "change_percent": calc_percentage(current["total_sales"], previous["total_sales"])
                },
                "total_orders": {
                    "value": current["total_orders"],
                    "change_percent": calc_percentage(current["total_orders"], previous["total_orders"])
                },
                "average_order_value": {
                    "value": round(current["avg_order_value"], 2),
                    "change_percent": calc_percentage(current["avg_order_value"], previous["avg_order_value"])
                }
            }

        except Exception as e:
            logger.error(f"Error calculating monthly summary: {str(e)}")
            raise e



    # For getting last 7 months monthly sales insights like total orders, total sales, total visitor count
    @staticmethod
    def get_sales_data(user_id):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            last_7_months = []

            for i in range(6, -1, -1):  # Last 6 months + current
                month = (today.month - i - 1) % 12 + 1
                year = today.year if (today.month - i) > 0 else today.year - 1
                last_7_months.append((month, year))

            rows = (
                db.session.query(
                    extract('month', Order.created_at).label('month'),
                    extract('year', Order.created_at).label('year'),
                    func.count(Order.order_id).label('orders'),
                    func.sum(Order.total_amount).label('sales')
                )
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    tuple_(
                        extract('month', Order.created_at),
                        extract('year', Order.created_at)
                    ).in_(last_7_months)
                )
                .group_by(extract('month', Order.created_at), extract('year', Order.created_at))
                .all()
            )

            # Create a default dictionary for the past 7 months
            result_map = {
                (m, y): {'sales': 0, 'orders': 0, 'visitors': 2000}
                for m, y in last_7_months
            }

            for row in rows:
                key = (int(row.month), int(row.year))
                result_map[key] = {
                    'sales': float(row.sales or 0),
                    'orders': row.orders,
                    'visitors': 2000  # dummy visitors for now
                }

            # Format final result with proper month labels
            formatted_result = []
            for month, year in last_7_months:
                formatted_result.append({
                    'month': f"{calendar.month_abbr[month]} {year}",
                    'sales': result_map[(month, year)]['sales'],
                    'orders': result_map[(month, year)]['orders'],
                    'visitors': result_map[(month, year)]['visitors']
                })

            return formatted_result

        except Exception as e:
            logger.error(f"Error calculating sales data: {str(e)}", exc_info=True)
            raise e
        
    
    # For getting top 5 products sold by a merchant
    @staticmethod
    def get_top_products(user_id, limit=5):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Join order_items and products
            results = (
                db.session.query(
                    OrderItem.product_id,
                    Product.product_name,
                    func.sum(OrderItem.quantity).label("sold"),
                    func.sum(OrderItem.final_price_for_item).label("revenue")
                )
                .join(Product, Product.product_id == OrderItem.product_id)
                .filter(OrderItem.merchant_id == merchant.id)
                .group_by(OrderItem.product_id, Product.product_name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(limit)
                .all()
            )

            top_products = []
            for idx, row in enumerate(results, start=1):
                top_products.append({
                    "id": idx,
                    "name": row.product_name,
                    "sold": int(row.sold or 0),
                    "revenue": float(row.revenue or 0),
                })

            return top_products

        except Exception as e:
            logger.error(f"Error fetching top products: {str(e)}")
            raise e
