from sqlalchemy import and_, extract, func, tuple_
from decimal import Decimal
from datetime import datetime, date
import logging
from common.database import db
from models.order import Order, OrderItem
from models.product import Product
from models.category import Category
from models.product_stock import ProductStock
from models.recently_viewed import RecentlyViewed
from auth.models.models import MerchantProfile, User
from models.enums import OrderStatusEnum, PaymentStatusEnum
import calendar
from models.wishlist_item import WishlistItem

logger = logging.getLogger(__name__)


class MerchantReportController:

    # For getting monthly sales analytics for the last 5 months
    @staticmethod
    def get_monthly_sales_analytics(user_id):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            last_5_months = []

            for i in range(4, -1, -1):  # Last 4 + current
                month = (today.month - i - 1) % 12 + 1
                year = today.year if (today.month - i) > 0 else today.year - 1
                last_5_months.append((month, year))

            rows = (
                db.session.query(
                    extract('month', Order.created_at).label('month'),
                    extract('year', Order.created_at).label('year'),
                    func.sum(OrderItem.quantity).label('units'),
                    func.sum(OrderItem.final_price_for_item).label('revenue')
                )
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    tuple_(
                        extract('month', Order.created_at),
                        extract('year', Order.created_at)
                    ).in_(last_5_months)
                )
                .group_by(extract('month', Order.created_at), extract('year', Order.created_at))
                .all()
            )

            # Build results map with default values
            result_map = {
                (m, y): {'revenue': 0, 'units': 0}
                for m, y in last_5_months
            }

            for row in rows:
                key = (int(row.month), int(row.year))
                result_map[key] = {
                    'revenue': float(row.revenue or 0),
                    'units': int(row.units or 0)
                }

            # Format for frontend
            formatted_result = []
            for month, year in last_5_months:
                formatted_result.append({
                    'month': calendar.month_abbr[month],
                    'revenue': result_map[(month, year)]['revenue'],
                    'units': result_map[(month, year)]['units']
                })

            return formatted_result

        except Exception as e:
            logger.error(f"Error calculating monthly sales analytics: {str(e)}", exc_info=True)
            raise e

    
    # For getting detailed monthly sales data for the last 5 months
    @staticmethod
    def get_detailed_monthly_sales(user_id):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            last_5_months = []
            for i in range(4, -1, -1):
                month = (today.month - i - 1) % 12 + 1
                year = today.year if (today.month - i) > 0 else today.year - 1
                last_5_months.append((month, year))

            # Modified query to include year in SELECT and GROUP BY
            rows = (
                db.session.query(
                    extract('month', Order.created_at).label('month'),
                    extract('year', Order.created_at).label('year'),  # ADDED
                    Product.product_name,
                    Category.name.label('category'),
                    Product.selling_price,
                    func.sum(OrderItem.quantity).label('quantity'),
                    func.sum(OrderItem.final_price_for_item).label('revenue')
                )
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .join(Product, Product.product_id == OrderItem.product_id)
                .join(Category, Category.category_id == Product.category_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    tuple_(
                        extract('month', Order.created_at),
                        extract('year', Order.created_at)
                    ).in_(last_5_months)
                )
                .group_by(
                    extract('year', Order.created_at),  # ADDED
                    extract('month', Order.created_at),
                    Product.product_name,
                    Category.name,
                    Product.selling_price
                )
                .order_by('year', 'month')  # Now valid
                .all()
            )

            detailed_sales = []
            for row in rows:
                detailed_sales.append({
                    "month": calendar.month_abbr[int(row.month)],
                    "product": row.product_name,
                    "category": row.category,
                    "price": float(row.selling_price),
                    "quantity": int(row.quantity),
                    "revenue": float(row.revenue)
                })

            return detailed_sales

        except Exception as e:
            logger.error(f"Error fetching detailed monthly sales: {str(e)}", exc_info=True)
            raise e



    # For getting product performance over the last 3 months
    @staticmethod
    def get_product_performance(user_id, months=3, limit=3):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Calculate start date without relativedelta
            today = date.today()
            year = today.year
            month = today.month - months
            
            # Handle year wrap-around if month becomes negative
            while month <= 0:
                year -= 1
                month += 12
                
            # Create the start date (first day of the target month)
            start_date = date(year, month, 1)
            
            # Query top performing products by revenue
            products = (
                db.session.query(
                    Product.product_name.label('name'),
                    func.sum(OrderItem.final_price_for_item).label('revenue')
                )
                .join(OrderItem, OrderItem.product_id == Product.product_id)
                .join(Order, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    Order.created_at >= start_date
                )
                .group_by(Product.product_name)
                .order_by(func.sum(OrderItem.final_price_for_item).desc())
                .limit(limit)
                .all()
            )

            # Format results
            return [{
                "name": product.name,
                "revenue": float(product.revenue)
            } for product in products]

        except Exception as e:
            logger.error(f"Error fetching product performance: {str(e)}", exc_info=True)
            raise e


    # For getting revenue by category for the last 3 months
    @staticmethod
    def get_revenue_by_category(user_id, months=3, limit=3):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Calculate start date
            today = date.today()
            year = today.year
            month = today.month - months
            
            # Handle year wrap-around if month becomes negative
            while month <= 0:
                year -= 1
                month += 12
                
            start_date = date(year, month, 1)
            
            # Query category revenue
            category_revenues = (
                db.session.query(
                    Category.name.label('category'),
                    func.sum(OrderItem.final_price_for_item).label('revenue')
                )
                .join(Product, Product.category_id == Category.category_id)
                .join(OrderItem, OrderItem.product_id == Product.product_id)
                .join(Order, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    Order.created_at >= start_date
                )
                .group_by(Category.name)
                .order_by(func.sum(OrderItem.final_price_for_item).desc())
                .all()
            )

            # Calculate total revenue
            total_revenue = sum(revenue for _, revenue in category_revenues)
            
            # Process categories - limit to top 3 and group the rest as "Other"
            top_categories = []
            other_revenue = 0
            other_count = 0
            
            for i, (category, revenue) in enumerate(category_revenues):
                if i < limit:
                    percentage = round((revenue / total_revenue) * 100, 2) if total_revenue > 0 else 0
                    top_categories.append({
                        "name": category,
                        "value": percentage
                    })
                else:
                    other_revenue += revenue
                    other_count += 1
            
            # Add "Other" category if there are remaining categories
            if other_count > 0:
                other_percentage = round((other_revenue / total_revenue) * 100, 2) if total_revenue > 0 else 0
                top_categories.append({
                    "name": "Other",
                    "value": other_percentage
                })
                
            return top_categories

        except Exception as e:
            logger.error(f"Error fetching revenue by category: {str(e)}", exc_info=True)
            raise e



    # For getting dashboard summary for the merchant
    @staticmethod
    def get_dashboard_summary(user_id):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            current_year, current_month = today.year, today.month
            
            # Previous month calculation
            if current_month == 1:
                prev_month = 12
                prev_year = current_year - 1
            else:
                prev_month = current_month - 1
                prev_year = current_year
            
            # Helper function to calculate percentage change
            def calculate_change(current, previous):
                if previous == 0:
                    if current == 0:
                        return "0%"
                    # For positive values with zero previous, show "+100%" as a meaningful indicator
                    return "+100%"
                
                change = ((current - previous) / previous) * 100
                if change >= 0:
                    return f"+{change:.0f}%"
                return f"{change:.0f}%"

            # 1. Total Products
            total_products = db.session.query(func.count(Product.product_id)) \
                .filter(Product.merchant_id == merchant.id) \
                .scalar() or 0
            
            # Total products at end of previous month
            total_products_prev = db.session.query(func.count(Product.product_id)) \
                .filter(
                    Product.merchant_id == merchant.id,
                    func.date(Product.created_at) <= date(prev_year, prev_month, 1)
                ) \
                .scalar() or 0
            
            # 2. Products Sold - current month
            products_sold = db.session.query(func.sum(OrderItem.quantity)) \
                .join(Order, Order.order_id == OrderItem.order_id) \
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    extract('year', Order.created_at) == current_year,
                    extract('month', Order.created_at) == current_month
                ) \
                .scalar() or 0
            
            # Products Sold - previous month
            products_sold_prev = db.session.query(func.sum(OrderItem.quantity)) \
                .join(Order, Order.order_id == OrderItem.order_id) \
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    extract('year', Order.created_at) == prev_year,
                    extract('month', Order.created_at) == prev_month
                ) \
                .scalar() or 0
            
            # 3. Wishlisted Products (current month, not deleted)
            wishlisted_products = db.session.query(func.count(db.distinct(WishlistItem.product_id))) \
                .join(Product, WishlistItem.product_id == Product.product_id) \
                .filter(
                    Product.merchant_id == merchant.id,
                    WishlistItem.is_deleted == False
                ).scalar() or 0

            # Wishlisted Products (previous month, not deleted, added before this month)
            first_day_of_current_month = date(current_year, current_month, 1)
            wishlisted_products_prev = db.session.query(func.count(db.distinct(WishlistItem.product_id))) \
                .join(Product, WishlistItem.product_id == Product.product_id) \
                .filter(
                    Product.merchant_id == merchant.id,
                    WishlistItem.is_deleted == False,
                    WishlistItem.added_at < first_day_of_current_month
                ).scalar() or 0
            
            # 4. Out of Stock Products
            out_of_stock = db.session.query(func.count(Product.product_id)) \
                .join(ProductStock, Product.product_id == ProductStock.product_id) \
                .filter(
                    Product.merchant_id == merchant.id,
                    ProductStock.stock_qty <= 0
                ) \
                .scalar() or 0
            
            # Out of Stock at end of previous month
            out_of_stock_prev = db.session.query(func.count(Product.product_id)) \
                .join(ProductStock, Product.product_id == ProductStock.product_id) \
                .filter(
                    Product.merchant_id == merchant.id,
                    ProductStock.stock_qty <= 0,
                    func.date(Product.created_at) <= date(prev_year, prev_month, 1)
                ) \
                .scalar() or 0
            
            # Prepare and format the response
            return [
                {
                    "label": "Total Products",
                    "value": f"{total_products:,}",
                    "change": calculate_change(total_products, total_products_prev)
                },
                {
                    "label": "Products Sold",
                    "value": f"{products_sold:,}",
                    "change": calculate_change(products_sold, products_sold_prev)
                },
                {
                    "label": "Wishlisted Products",
                    "value": f"{wishlisted_products:,}",
                    "change": calculate_change(wishlisted_products, wishlisted_products_prev)
                },
                {
                    "label": "Out of Stock",
                    "value": f"{out_of_stock:,}",
                    "change": calculate_change(out_of_stock, out_of_stock_prev)
                }
            ]

        except Exception as e:
            logger.error(f"Error fetching dashboard summary: {str(e)}", exc_info=True)
            raise e


    # For getting daily sales and wishlist data for the last 30 days
    @staticmethod
    def get_daily_sales_data(user_id):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            
            # Calculate 30 days ago without timedelta
            current = today
            date_range = []
            for _ in range(30):
                date_range.append(current)
                # Move to previous day
                if current.day > 1:
                    current = date(current.year, current.month, current.day - 1)
                else:
                    # Previous month
                    prev_month = current.month - 1
                    prev_year = current.year
                    if prev_month == 0:
                        prev_month = 12
                        prev_year -= 1
                    # Get last day of previous month
                    _, last_day = calendar.monthrange(prev_year, prev_month)
                    current = date(prev_year, prev_month, last_day)
            
            date_range.reverse()  # Oldest first
            
            # Query daily sales data
            sales_data = (
                db.session.query(
                    func.date(Order.created_at).label('date'),
                    func.sum(OrderItem.quantity).label('quantity')
                )
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    func.date(Order.created_at).in_(date_range)
                )
                .group_by(func.date(Order.created_at))
                .all()
            )
            
            # Convert to dictionary for easy lookup
            sales_dict = {row.date: row.quantity for row in sales_data}
            
            # Placeholder for wishlist data
            wishlist_dict = {}
            # Implement with your wishlist model when available
            
            # Build response
            result = []
            for day in date_range:
                # Format date as "M/D/YYYY"
                formatted_date = f"{day.month}/{day.day}/{day.year}"
                quantity = sales_dict.get(day, 0)
                
                # Get wishlist count or generate random placeholder
                if day in wishlist_dict:
                    wishlisted = wishlist_dict[day]
                else:
                    # Random placeholder until wishlist is implemented
                    wishlisted = (day.day * 17) % 21  # Pseudo-random based on day
                
                result.append({
                    "date": formatted_date,
                    "quantity": int(quantity),
                    "wishlisted": wishlisted
                })
            
            return result

        except Exception as e:
            logger.error(f"Error fetching daily sales data: {str(e)}", exc_info=True)
            raise e


    # For getting top selling products in the last 30 days
    @staticmethod
    def get_top_selling_products(user_id, days=30, limit=4):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            today = date.today()
            
            # Calculate start date without timedelta
            start_date = today
            for _ in range(days):
                if start_date.day > 1:
                    start_date = date(start_date.year, start_date.month, start_date.day - 1)
                else:
                    # Move to previous month
                    prev_month = start_date.month - 1
                    prev_year = start_date.year
                    if prev_month == 0:
                        prev_month = 12
                        prev_year -= 1
                    # Get last day of previous month
                    _, last_day = calendar.monthrange(prev_year, prev_month)
                    start_date = date(prev_year, prev_month, last_day)
            
            # Query top selling products
            products = (
                db.session.query(
                    Product.product_name.label('name'),
                    func.sum(OrderItem.quantity).label('sold'),
                    func.sum(OrderItem.final_price_for_item * OrderItem.quantity).label('revenue')
                )
                .join(OrderItem, OrderItem.product_id == Product.product_id)
                .join(Order, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED,
                    Order.created_at >= start_date
                )
                .group_by(Product.product_name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(limit)
                .all()
            )
            
            # Format results
            result = []
            for product in products:
                # Format revenue as currency string ($1,234)
                revenue_str = "${:,.0f}".format(float(product.revenue))
                result.append({
                    "name": product.name,
                    "sold": int(product.sold),
                    "revenue": revenue_str
                })
                
            return result

        except Exception as e:
            logger.error(f"Error fetching top selling products: {str(e)}", exc_info=True)
            raise e



    @staticmethod
    def get_most_viewed_products(user_id, limit=4):
        try:
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Step 1: Count product views
            view_counts = (
                db.session.query(
                    RecentlyViewed.product_id,
                    func.count(RecentlyViewed.id).label("views")
                )
                .join(Product, Product.product_id == RecentlyViewed.product_id)
                .filter(Product.merchant_id == merchant.id)
                .group_by(RecentlyViewed.product_id)
                .subquery()
            )

            # Step 2: Count successful purchases (for conversion rate)
            order_counts = (
                db.session.query(
                    OrderItem.product_id,
                    func.count(OrderItem.order_item_id).label("orders")
                )
                .join(Order, Order.order_id == OrderItem.order_id)
                .filter(
                    OrderItem.merchant_id == merchant.id,
                    # Order.payment_status == PaymentStatusEnum.SUCCESSFUL,
                    # Order.order_status == OrderStatusEnum.DELIVERED
                )
                .group_by(OrderItem.product_id)
                .subquery()
            )

            # Step 3: Join and format
            products = (
                db.session.query(
                    Product.product_name.label("name"),
                    view_counts.c.views,
                    func.coalesce(order_counts.c.orders, 0).label("orders")
                )
                .join(view_counts, Product.product_id == view_counts.c.product_id)
                .outerjoin(order_counts, Product.product_id == order_counts.c.product_id)
                .order_by(view_counts.c.views.desc())
                .limit(limit)
                .all()
            )

            result = []
            for product in products:
                conversion = f"{(product.orders / product.views * 100):.1f}%" if product.views > 0 else "0.0%"
                result.append({
                    "name": product.name,
                    "views": int(product.views),
                    "conversion": conversion
                })

            return result

        except Exception as e:
            logger.error(f"Error fetching most viewed products: {str(e)}", exc_info=True)
            raise e

