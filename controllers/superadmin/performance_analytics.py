from datetime import datetime, timezone, timedelta
from sqlalchemy import func, and_, extract, case
from models.order import Order,  OrderItem
from auth.models.models import User, MerchantProfile, UserRole
from models.user_address import UserAddress
from models.product import Product
from models.category import Category
from common.database import db
from models.review import Review
from models.visit_tracking import VisitTracking

class PerformanceAnalyticsController:
    @staticmethod
    def calculate_month_over_month_change(current_value, previous_value):
        """Calculate month over month change percentage"""
        if previous_value == 0:
            return 0
        return ((current_value - previous_value) / previous_value) * 100

    @staticmethod
    def get_total_revenue():
        """Calculate total revenue from all orders"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Current month revenue
            current_revenue = db.session.query(
                func.sum(Order.total_amount)
            ).filter(
                Order.order_date >= current_month_start
            ).scalar() or 0

            # Previous month revenue
            previous_revenue = db.session.query(
                func.sum(Order.total_amount)
            ).filter(
                and_(
                    Order.order_date >= previous_month_start,
                    Order.order_date < current_month_start
                )
            ).scalar() or 0

            change_percentage = PerformanceAnalyticsController.calculate_month_over_month_change(
                float(current_revenue), float(previous_revenue)
            )

            return {
                "status": "success",
                "total_revenue": float(current_revenue),
                "previous_revenue": float(previous_revenue),
                "change_percentage": round(change_percentage, 1),
                "currency": "INR"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_active_users():
        """Get count of active users"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Current month active users with role USER
            current_users = db.session.query(
                func.count(User.id)
            ).filter(
                and_(
                    User.is_active == True,
                    User.role == UserRole.USER,
                    User.created_at >= current_month_start
                )
            ).scalar() or 0

            # Previous month active users with role USER
            previous_users = db.session.query(
                func.count(User.id)
            ).filter(
                and_(
                    User.is_active == True,
                    User.role == UserRole.USER,
                    User.created_at >= previous_month_start,
                    User.created_at < current_month_start
                )
            ).scalar() or 0

            change_percentage = PerformanceAnalyticsController.calculate_month_over_month_change(
                current_users, previous_users
            )

            return {
                "status": "success",
                "active_users": current_users,
                "previous_users": previous_users,
                "change_percentage": round(change_percentage, 1)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_total_merchants():
        """Get count of total merchants"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Current month merchants
            current_merchants = db.session.query(
                func.count(MerchantProfile.id)
            ).filter(
                and_(
                    MerchantProfile.is_verified == True,
                    MerchantProfile.created_at >= current_month_start
                )
            ).scalar() or 0

            # Previous month merchants
            previous_merchants = db.session.query(
                func.count(MerchantProfile.id)
            ).filter(
                and_(
                    MerchantProfile.is_verified == True,
                    MerchantProfile.created_at >= previous_month_start,
                    MerchantProfile.created_at < current_month_start
                )
            ).scalar() or 0

            change_percentage = PerformanceAnalyticsController.calculate_month_over_month_change(
                current_merchants, previous_merchants
            )

            return {
                "status": "success",
                "total_merchants": current_merchants,
                "previous_merchants": previous_merchants,
                "change_percentage": round(change_percentage, 1)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_orders_this_month():
        """Get count and total amount of orders in current month"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            
            # Current month orders - count all orders
            current_orders_count = db.session.query(
                func.count(Order.order_id)
            ).filter(
                Order.order_date >= current_month_start
            ).scalar() or 0

            current_orders_amount = db.session.query(
                func.sum(Order.total_amount)
            ).filter(
                Order.order_date >= current_month_start
            ).scalar() or 0

            # Previous month orders - count all orders
            previous_orders_count = db.session.query(
                func.count(Order.order_id)
            ).filter(
                and_(
                    Order.order_date >= previous_month_start,
                    Order.order_date < current_month_start
                )
            ).scalar() or 0

            previous_orders_amount = db.session.query(
                func.sum(Order.total_amount)
            ).filter(
                and_(
                    Order.order_date >= previous_month_start,
                    Order.order_date < current_month_start
                )
            ).scalar() or 0

            count_change = PerformanceAnalyticsController.calculate_month_over_month_change(
                current_orders_count, previous_orders_count
            )

            amount_change = PerformanceAnalyticsController.calculate_month_over_month_change(
                float(current_orders_amount), float(previous_orders_amount)
            )

            return {
                "status": "success",
                "orders_count": current_orders_count,
                "previous_orders_count": previous_orders_count,
                "orders_amount": float(current_orders_amount),
                "previous_orders_amount": float(previous_orders_amount),
                "count_change_percentage": round(count_change, 1),
                "amount_change_percentage": round(amount_change, 1),
                "currency": "INR",
                "month": current_month_start.strftime("%B %Y")
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_all_metrics():
        """Get all performance metrics in one call"""
        try:
            revenue = PerformanceAnalyticsController.get_total_revenue()
            active_users = PerformanceAnalyticsController.get_active_users()
            total_merchants = PerformanceAnalyticsController.get_total_merchants()
            monthly_orders = PerformanceAnalyticsController.get_orders_this_month()

            return {
                "status": "success",
                "data": {
                    "revenue": {
                        "current": revenue.get("total_revenue", 0),
                        "previous": revenue.get("previous_revenue", 0),
                        "change_percentage": revenue.get("change_percentage", 0),
                        "currency": "INR"
                    },
                    "active_users": {
                        "current": active_users.get("active_users", 0),
                        "previous": active_users.get("previous_users", 0),
                        "change_percentage": active_users.get("change_percentage", 0)
                    },
                    "total_merchants": {
                        "current": total_merchants.get("total_merchants", 0),
                        "previous": total_merchants.get("previous_merchants", 0),
                        "change_percentage": total_merchants.get("change_percentage", 0)
                    },
                    "monthly_orders": {
                        "count": {
                            "current": monthly_orders.get("orders_count", 0),
                            "previous": monthly_orders.get("previous_orders_count", 0),
                            "change_percentage": monthly_orders.get("count_change_percentage", 0)
                        },
                        "amount": {
                            "current": monthly_orders.get("orders_amount", 0),
                            "previous": monthly_orders.get("previous_orders_amount", 0),
                            "change_percentage": monthly_orders.get("amount_change_percentage", 0),
                            "currency": "INR"
                        },
                        "month": monthly_orders.get("month", "")
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_revenue_orders_trend(months=12):
        """Get revenue and orders trend for the last N months"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Query to get monthly revenue and orders
            monthly_data = db.session.query(
                extract('year', Order.order_date).label('year'),
                extract('month', Order.order_date).label('month'),
                func.sum(OrderItem.final_price_for_item).label('revenue'),
                func.count(func.distinct(Order.order_id)).label('orders')
            ).join(
                OrderItem,
                OrderItem.order_id == Order.order_id
            ).filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date
                )
            ).group_by(
                extract('year', Order.order_date),
                extract('month', Order.order_date)
            ).order_by(
                extract('year', Order.order_date),
                extract('month', Order.order_date)
            ).all()

            # Format the data
            trend_data = []
            for data in monthly_data:
                trend_data.append({
                    "month": f"{int(data.year)}-{int(data.month):02d}",
                    "revenue": float(data.revenue or 0),
                    "orders": int(data.orders or 0)
                })

            # Calculate average order value
            for data in trend_data:
                data["average_order_value"] = round(
                    data["revenue"] / data["orders"] if data["orders"] > 0 else 0,
                    2
                )

            return {
                "status": "success",
                "data": {
                    "trend": trend_data,
                    "summary": {
                        "total_revenue": sum(item["revenue"] for item in trend_data),
                        "total_orders": sum(item["orders"] for item in trend_data),
                        "average_order_value": round(
                            sum(item["revenue"] for item in trend_data) / 
                            sum(item["orders"] for item in trend_data) 
                            if sum(item["orders"] for item in trend_data) > 0 else 0,
                            2
                        ),
                        "currency": "INR"
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_merchant_performance(months=12):
        """Get merchant performance metrics for the last N months"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Get merchant performance data
            merchant_data = db.session.query(
                MerchantProfile.id,
                MerchantProfile.business_name,
                func.sum(OrderItem.final_price_for_item).label('total_revenue'),
                func.count(func.distinct(Order.order_id)).label('total_orders')
            ).join(
                OrderItem,
                OrderItem.merchant_id == MerchantProfile.id
            ).join(
                Order,
                Order.order_id == OrderItem.order_id
            ).filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date
                )
            ).group_by(
                MerchantProfile.id,
                MerchantProfile.business_name
            ).order_by(
                func.sum(OrderItem.final_price_for_item).desc()
            ).all()

            # Format the data
            merchant_performance = []
            for data in merchant_data:
                merchant_performance.append({
                    "merchant_id": data.id,
                    "business_name": data.business_name,
                    "total_revenue": float(data.total_revenue or 0),
                    "total_orders": int(data.total_orders or 0),
                    "average_order_value": round(
                        float(data.total_revenue or 0) / int(data.total_orders or 1),
                        2
                    )
                })

            return {
                "status": "success",
                "data": {
                    "merchants": merchant_performance,
                    "summary": {
                        "total_merchants": len(merchant_performance),
                        "total_revenue": sum(item["total_revenue"] for item in merchant_performance),
                        "total_orders": sum(item["total_orders"] for item in merchant_performance),
                        "currency": "INR"
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_user_growth_trend(months=12):
        """Get user growth trend for the last N months"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Query to get monthly customer growth using UserAddress table
            customer_data = db.session.query(
                extract('year', UserAddress.created_at).label('year'),
                extract('month', UserAddress.created_at).label('month'),
                func.count(func.distinct(UserAddress.user_id)).label('customers')
            ).filter(
                and_(
                    UserAddress.created_at >= start_date,
                    UserAddress.created_at <= end_date
                )
            ).group_by(
                extract('year', UserAddress.created_at),
                extract('month', UserAddress.created_at)
            ).order_by(
                extract('year', UserAddress.created_at),
                extract('month', UserAddress.created_at)
            ).all()

            # Query to get monthly merchant growth
            merchant_data = db.session.query(
                extract('year', MerchantProfile.created_at).label('year'),
                extract('month', MerchantProfile.created_at).label('month'),
                func.count(MerchantProfile.id).label('merchants')
            ).filter(
                and_(
                    MerchantProfile.created_at >= start_date,
                    MerchantProfile.created_at <= end_date,
                    MerchantProfile.is_verified == True
                )
            ).group_by(
                extract('year', MerchantProfile.created_at),
                extract('month', MerchantProfile.created_at)
            ).order_by(
                extract('year', MerchantProfile.created_at),
                extract('month', MerchantProfile.created_at)
            ).all()

            # Create a dictionary to store all months
            all_months = {}
            for data in customer_data:
                month_key = f"{int(data.year)}-{int(data.month):02d}"
                all_months[month_key] = {
                    "month": month_key,
                    "customers": int(data.customers or 0),
                    "merchants": 0
                }

            # Add merchant data
            for data in merchant_data:
                month_key = f"{int(data.year)}-{int(data.month):02d}"
                if month_key in all_months:
                    all_months[month_key]["merchants"] = int(data.merchants or 0)
                else:
                    all_months[month_key] = {
                        "month": month_key,
                        "customers": 0,
                        "merchants": int(data.merchants or 0)
                    }

            # Convert to list and sort by month
            trend_data = list(all_months.values())
            trend_data.sort(key=lambda x: x["month"])

            # Calculate total users and growth rates
            total_customers = sum(item["customers"] for item in trend_data)
            total_merchants = sum(item["merchants"] for item in trend_data)

            # Calculate month-over-month growth rates
            for i in range(1, len(trend_data)):
                prev_customers = trend_data[i-1]["customers"]
                prev_merchants = trend_data[i-1]["merchants"]
                
                current_customers = trend_data[i]["customers"]
                current_merchants = trend_data[i]["merchants"]

                # Calculate growth rates
                customer_growth = ((current_customers - prev_customers) / prev_customers * 100) if prev_customers > 0 else 0
                merchant_growth = ((current_merchants - prev_merchants) / prev_merchants * 100) if prev_merchants > 0 else 0

                trend_data[i]["customer_growth"] = round(customer_growth, 1)
                trend_data[i]["merchant_growth"] = round(merchant_growth, 1)

            # Add growth rates for first month
            if trend_data:
                trend_data[0]["customer_growth"] = 0
                trend_data[0]["merchant_growth"] = 0

            return {
                "status": "success",
                "data": {
                    "trend": trend_data,
                    "summary": {
                        "total_customers": total_customers,
                        "total_merchants": total_merchants,
                        "total_users": total_customers + total_merchants,
                        "average_customer_growth": round(
                            sum(item["customer_growth"] for item in trend_data) / len(trend_data) if trend_data else 0,
                            1
                        ),
                        "average_merchant_growth": round(
                            sum(item["merchant_growth"] for item in trend_data) / len(trend_data) if trend_data else 0,
                            1
                        )
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_average_order_value():
        """Calculate average order value for current and previous month"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Current month AOV
            current_month_data = db.session.query(
                func.sum(Order.total_amount).label('total_revenue'),
                func.count(Order.order_id).label('total_orders')
            ).filter(
                Order.order_date >= current_month_start
            ).first()

            current_revenue = float(current_month_data.total_revenue or 0)
            current_orders = int(current_month_data.total_orders or 0)
            current_aov = current_revenue / current_orders if current_orders > 0 else 0

            # Previous month AOV
            previous_month_data = db.session.query(
                func.sum(Order.total_amount).label('total_revenue'),
                func.count(Order.order_id).label('total_orders')
            ).filter(
                and_(
                    Order.order_date >= previous_month_start,
                    Order.order_date < current_month_start
                )
            ).first()

            previous_revenue = float(previous_month_data.total_revenue or 0)
            previous_orders = int(previous_month_data.total_orders or 0)
            previous_aov = previous_revenue / previous_orders if previous_orders > 0 else 0

            change_percentage = PerformanceAnalyticsController.calculate_month_over_month_change(
                current_aov, previous_aov
            )

            return {
                "status": "success",
                "data": {
                    "current": round(current_aov, 2),
                    "previous": round(previous_aov, 2),
                    "change_percentage": round(change_percentage, 1),
                    "currency": "INR"
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_total_products():
        """Calculate total products and their growth"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Current month products
            current_products = db.session.query(
                func.count(Product.product_id)
            ).filter(
                and_(
                    Product.active_flag == True,
                    Product.approval_status == 'approved',
                    Product.created_at >= current_month_start
                )
            ).scalar() or 0

            # Previous month products
            previous_products = db.session.query(
                func.count(Product.product_id)
            ).filter(
                and_(
                    Product.active_flag == True,
                    Product.approval_status == 'approved',
                    Product.created_at >= previous_month_start,
                    Product.created_at < current_month_start
                )
            ).scalar() or 0

            # Total active products
            total_active_products = db.session.query(
                func.count(Product.product_id)
            ).filter(
                and_(
                    Product.active_flag == True,
                    Product.approval_status == 'approved'
                )
            ).scalar() or 0

            change_percentage = PerformanceAnalyticsController.calculate_month_over_month_change(
                current_products, previous_products
            )

            return {
                "status": "success",
                "data": {
                    "current": current_products,
                    "previous": previous_products,
                    "total_active": total_active_products,
                    "change_percentage": round(change_percentage, 1)
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_category_distribution():
        """Calculate the distribution of products across categories"""
        try:
            # Get total count of active and approved products
            total_products = db.session.query(
                func.count(Product.product_id)
            ).filter(
                and_(
                    Product.active_flag == True,
                    Product.approval_status == 'approved'
                )
            ).scalar() or 0

            # Get product count per category
            category_data = db.session.query(
                Category.name,
                func.count(Product.product_id).label('product_count')
            ).join(
                Product,
                Product.category_id == Category.category_id
            ).filter(
                and_(
                    Product.active_flag == True,
                    Product.approval_status == 'approved',
                    Category.deleted_at.is_(None)  # Only include active categories
                )
            ).group_by(
                Category.name
            ).order_by(
                func.count(Product.product_id).desc()
            ).all()

            # Calculate percentages and format data
            category_distribution = []
            for category in category_data:
                percentage = (category.product_count / total_products * 100) if total_products > 0 else 0
                category_distribution.append({
                    "name": category.name,
                    "value": round(percentage, 1),
                    "count": category.product_count,
                    "color": "#" + ''.join([format(hash(category.name + str(i)) % 256, '02x') for i in range(3)])  # Generate consistent color based on category name
                })

            return {
                "status": "success",
                "data": {
                    "categories": category_distribution,
                    "total_products": total_products
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_top_merchants(limit=5):
        """Get top merchants based on revenue and orders"""
        try:
            # Get current month start date
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

            # Query to get merchant performance data
            merchant_data = db.session.query(
                MerchantProfile.id,
                MerchantProfile.business_name,
                func.sum(OrderItem.final_price_for_item).label('total_revenue'),
                func.count(func.distinct(Order.order_id)).label('total_orders')
            ).join(
                OrderItem,
                OrderItem.merchant_id == MerchantProfile.id
            ).join(
                Order,
                Order.order_id == OrderItem.order_id
            ).filter(
                Order.order_date >= current_month_start
            ).group_by(
                MerchantProfile.id,
                MerchantProfile.business_name
            ).order_by(
                func.sum(OrderItem.final_price_for_item).desc()
            ).limit(limit).all()

            # Get previous month data for growth calculation
            previous_month_data = db.session.query(
                MerchantProfile.id,
                func.sum(OrderItem.final_price_for_item).label('previous_revenue')
            ).join(
                OrderItem,
                OrderItem.merchant_id == MerchantProfile.id
            ).join(
                Order,
                Order.order_id == OrderItem.order_id
            ).filter(
                and_(
                    Order.order_date >= previous_month_start,
                    Order.order_date < current_month_start,
                    MerchantProfile.id.in_([m.id for m in merchant_data])
                )
            ).group_by(
                MerchantProfile.id
            ).all()

            # Create a dictionary of previous month revenue for quick lookup
            previous_revenue_dict = {m.id: float(m.previous_revenue or 0) for m in previous_month_data}

            # Format the data
            top_merchants = []
            for merchant in merchant_data:
                current_revenue = float(merchant.total_revenue or 0)
                previous_revenue = previous_revenue_dict.get(merchant.id, 0)
                
                # Calculate growth percentage
                growth = ((current_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0

                top_merchants.append({
                    "name": merchant.business_name,
                    "revenue": f"₹{current_revenue:,.0f}",
                    "orders": merchant.total_orders,
                    "growth": f"{'+' if growth >= 0 else ''}{growth:.0f}%"
                })

            return {
                "status": "success",
                "data": {
                    "merchants": top_merchants
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_merchant_performance_details(months=12):
        """Get detailed merchant performance metrics including revenue, orders, and ratings"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Get merchant performance data with revenue and orders
            merchant_data = db.session.query(
                MerchantProfile.id,
                MerchantProfile.business_name,
                func.sum(OrderItem.final_price_for_item).label('total_revenue'),
                func.count(func.distinct(Order.order_id)).label('total_orders'),
                func.avg(Review.rating).label('average_rating')
            ).join(
                OrderItem,
                OrderItem.merchant_id == MerchantProfile.id
            ).join(
                Order,
                Order.order_id == OrderItem.order_id
            ).outerjoin(
                Product,
                Product.merchant_id == MerchantProfile.id
            ).outerjoin(
                Review,
                Review.product_id == Product.product_id
            ).filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date
                )
            ).group_by(
                MerchantProfile.id,
                MerchantProfile.business_name
            ).order_by(
                func.sum(OrderItem.final_price_for_item).desc()
            ).all()

            # Format the data
            merchant_performance = []
            for data in merchant_data:
                # Get product count for this merchant
                product_count = db.session.query(
                    func.count(Product.product_id)
                ).filter(
                    and_(
                        Product.merchant_id == data.id,
                        Product.active_flag == True,
                        Product.approval_status == 'approved'
                    )
                ).scalar() or 0

                # Get review count for this merchant's products
                review_count = db.session.query(
                    func.count(Review.review_id)
                ).join(
                    Product,
                    Product.product_id == Review.product_id
                ).filter(
                    Product.merchant_id == data.id
                ).scalar() or 0

                merchant_performance.append({
                    "merchant_id": data.id,
                    "name": data.business_name,
                    "revenue": float(data.total_revenue or 0),
                    "orders": int(data.total_orders or 0),
                    "average_order_value": round(
                        float(data.total_revenue or 0) / int(data.total_orders or 1),
                        2
                    ),
                    "rating": round(float(data.average_rating or 0), 1),
                    "product_count": product_count,
                    "review_count": review_count,
                    "metrics": {
                        "revenue_per_product": round(
                            float(data.total_revenue or 0) / product_count if product_count > 0 else 0,
                            2
                        ),
                        "orders_per_product": round(
                            float(data.total_orders or 0) / product_count if product_count > 0 else 0,
                            2
                        ),
                        "reviews_per_product": round(
                            float(review_count) / product_count if product_count > 0 else 0,
                            2
                        )
                    }
                })

            return {
                "status": "success",
                "data": {
                    "merchants": merchant_performance,
                    "summary": {
                        "total_merchants": len(merchant_performance),
                        "total_revenue": sum(item["revenue"] for item in merchant_performance),
                        "total_orders": sum(item["orders"] for item in merchant_performance),
                        "average_rating": round(
                            sum(item["rating"] for item in merchant_performance) / len(merchant_performance) if merchant_performance else 0,
                            1
                        ),
                        "total_products": sum(item["product_count"] for item in merchant_performance),
                        "total_reviews": sum(item["review_count"] for item in merchant_performance),
                        "currency": "INR"
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_conversion_rate(months=12):
        """Calculate conversion rate based on visit tracking and orders"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Get total unique visitors (from visit_tracking)
            total_visitors = db.session.query(
                func.count(func.distinct(VisitTracking.session_id))
            ).filter(
                and_(
                    VisitTracking.visit_time >= start_date,
                    VisitTracking.visit_time <= end_date,
                    VisitTracking.is_deleted == False
                )
            ).scalar() or 0

            # Get total purchases (from orders)
            total_purchases = db.session.query(
                func.count(func.distinct(Order.order_id))
            ).filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.user_id.isnot(None)  # Only count orders from registered users
                )
            ).scalar() or 0

            # Calculate conversion rate
            conversion_rate = (total_purchases / total_visitors * 100) if total_visitors > 0 else 0

            # Get monthly breakdown
            monthly_data = db.session.query(
                extract('year', VisitTracking.visit_time).label('year'),
                extract('month', VisitTracking.visit_time).label('month'),
                func.count(func.distinct(VisitTracking.session_id)).label('visitors'),
                func.count(func.distinct(Order.order_id)).label('purchases')
            ).outerjoin(
                Order,
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.user_id.isnot(None)
                )
            ).filter(
                and_(
                    VisitTracking.visit_time >= start_date,
                    VisitTracking.visit_time <= end_date,
                    VisitTracking.is_deleted == False
                )
            ).group_by(
                extract('year', VisitTracking.visit_time),
                extract('month', VisitTracking.visit_time)
            ).order_by(
                extract('year', VisitTracking.visit_time),
                extract('month', VisitTracking.visit_time)
            ).all()

            # Format monthly data
            monthly_breakdown = []
            for data in monthly_data:
                month_rate = (data.purchases / data.visitors * 100) if data.visitors > 0 else 0
                monthly_breakdown.append({
                    "month": f"{int(data.year)}-{int(data.month):02d}",
                    "visitors": int(data.visitors or 0),
                    "purchases": int(data.purchases or 0),
                    "conversion_rate": round(month_rate, 2)
                })

            return {
                "status": "success",
                "data": {
                    "overall": {
                        "total_visitors": total_visitors,
                        "total_purchases": total_purchases,
                        "conversion_rate": round(conversion_rate, 2)
                    },
                    "monthly_breakdown": monthly_breakdown,
                    "summary": {
                        "average_monthly_conversion": round(
                            sum(item["conversion_rate"] for item in monthly_breakdown) / len(monthly_breakdown) if monthly_breakdown else 0,
                            2
                        ),
                        "best_month": max(monthly_breakdown, key=lambda x: x["conversion_rate"]) if monthly_breakdown else None,
                        "worst_month": min(monthly_breakdown, key=lambda x: x["conversion_rate"]) if monthly_breakdown else None
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_hourly_analytics(months=12):
        """Get hourly analytics including page views, unique visitors, bounce rate, and conversion rate"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30 * months)

            # Get hourly visit data
            hourly_data = db.session.query(
                extract('hour', VisitTracking.visit_time).label('hour'),
                func.count(VisitTracking.visit_id).label('total_visits'),
                func.count(func.distinct(VisitTracking.session_id)).label('unique_visitors'),
                func.count(case(
                    (VisitTracking.pages_viewed == 1, 1),
                    else_=None
                )).label('bounced_visits'),
                func.count(case(
                    (VisitTracking.was_converted == True, 1),
                    else_=None
                )).label('conversions')
            ).filter(
                and_(
                    VisitTracking.visit_time >= start_date,
                    VisitTracking.visit_time <= end_date,
                    VisitTracking.is_deleted == False
                )
            ).group_by(
                extract('hour', VisitTracking.visit_time)
            ).order_by(
                extract('hour', VisitTracking.visit_time)
            ).all()

            # Format the data and convert UTC to IST
            hourly_analytics = []
            for data in hourly_data:
                total_visits = int(data.total_visits or 0)
                unique_visitors = int(data.unique_visitors or 0)
                bounced_visits = int(data.bounced_visits or 0)
                conversions = int(data.conversions or 0)

                # Convert UTC hour to IST (UTC+5:30)
                utc_hour = int(data.hour)
                ist_hour = (utc_hour + 5) % 24  # Add 5 hours for IST
                if utc_hour >= 18:  # If UTC hour is 18 or later, we need to add 30 minutes
                    ist_hour = (ist_hour + 1) % 24

                # Calculate rates
                bounce_rate = (bounced_visits / total_visits * 100) if total_visits > 0 else 0
                conversion_rate = (conversions / unique_visitors * 100) if unique_visitors > 0 else 0

                hourly_analytics.append({
                    "hour": ist_hour,
                    "hour_display": f"{ist_hour:02d}:00 IST",
                    "total_visits": total_visits,
                    "unique_visitors": unique_visitors,
                    "bounced_visits": bounced_visits,
                    "conversions": conversions,
                    "bounce_rate": round(bounce_rate, 2),
                    "conversion_rate": round(conversion_rate, 2)
                })

            # Calculate overall metrics
            total_visits = sum(item["total_visits"] for item in hourly_analytics)
            total_unique_visitors = sum(item["unique_visitors"] for item in hourly_analytics)
            total_bounced_visits = sum(item["bounced_visits"] for item in hourly_analytics)
            total_conversions = sum(item["conversions"] for item in hourly_analytics)

            overall_bounce_rate = (total_bounced_visits / total_visits * 100) if total_visits > 0 else 0
            overall_conversion_rate = (total_conversions / total_unique_visitors * 100) if total_unique_visitors > 0 else 0

            # Find peak hours
            peak_visits_hour = max(hourly_analytics, key=lambda x: x["total_visits"]) if hourly_analytics else None
            peak_conversion_hour = max(hourly_analytics, key=lambda x: x["conversion_rate"]) if hourly_analytics else None

            return {
                "status": "success",
                "data": {
                    "hourly_breakdown": hourly_analytics,
                    "summary": {
                        "total_visits": total_visits,
                        "total_unique_visitors": total_unique_visitors,
                        "total_bounced_visits": total_bounced_visits,
                        "total_conversions": total_conversions,
                        "overall_bounce_rate": round(overall_bounce_rate, 2),
                        "overall_conversion_rate": round(overall_conversion_rate, 2),
                        "peak_hours": {
                            "most_visits": {
                                "hour": peak_visits_hour["hour_display"] if peak_visits_hour else None,
                                "visits": peak_visits_hour["total_visits"] if peak_visits_hour else 0
                            },
                            "best_conversion": {
                                "hour": peak_conversion_hour["hour_display"] if peak_conversion_hour else None,
                                "rate": peak_conversion_hour["conversion_rate"] if peak_conversion_hour else 0
                            }
                        }
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
