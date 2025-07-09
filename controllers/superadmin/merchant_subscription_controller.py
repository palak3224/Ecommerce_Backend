
from flask import jsonify, request
from common.database import db
from auth.models.models import MerchantProfile
from models.subscription import SubscriptionPlan
from sqlalchemy import func, case
from auth.models.models import User

class MerchantSubscriptionController:
    @staticmethod
    def get_subscribed_merchants():
        """
        Retrieves a paginated, sorted, and filtered list of subscribed merchants.
        """
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        sort_by = request.args.get('sort_by', 'subscription_started_at')
        sort_order = request.args.get('sort_order', 'desc')
        plan_id = request.args.get('plan_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = MerchantProfile.query.filter(MerchantProfile.is_subscribed == True)

        if plan_id:
            query = query.filter(MerchantProfile.subscription_plan_id == plan_id)
        if start_date:
            query = query.filter(MerchantProfile.subscription_started_at >= start_date)
        if end_date:
            query = query.filter(MerchantProfile.subscription_expires_at <= end_date)

        if hasattr(MerchantProfile, sort_by):
            if sort_order == 'desc':
                query = query.order_by(getattr(MerchantProfile, sort_by).desc())
            else:
                query = query.order_by(getattr(MerchantProfile, sort_by).asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        merchants = pagination.items

        serialized_merchants = []
        for merchant in merchants:
            user = User.query.get(merchant.user_id)
            serialized_merchants.append({
                'id': merchant.id,
                'business_name': merchant.business_name,
                'business_email': merchant.business_email,
                'subscription_plan': merchant.subscription_plan.name if merchant.subscription_plan else None,
                'subscription_started_at': merchant.subscription_started_at.isoformat() if merchant.subscription_started_at else None,
                'subscription_expires_at': merchant.subscription_expires_at.isoformat() if merchant.subscription_expires_at else None,
                'slots_used': 0, # Replace with actual logic
                'slots_vacant': 0 # Replace with actual logic
            })

        return {
            'merchants': serialized_merchants,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        }

    @staticmethod
    def get_subscription_summary():
        """
        Retrieves a summary of merchant subscriptions.
        """
        total_subscribed_merchants = db.session.query(func.count(MerchantProfile.id)).filter(MerchantProfile.is_subscribed == True).scalar()

        plan_summary = db.session.query(
            SubscriptionPlan.name,
            func.count(MerchantProfile.id)
        ).join(MerchantProfile, MerchantProfile.subscription_plan_id == SubscriptionPlan.plan_id)\
        .filter(MerchantProfile.is_subscribed == True)\
        .group_by(SubscriptionPlan.name).all()

        return {
            'total_subscribed_merchants': total_subscribed_merchants,
            'plan_summary': [{'plan_name': name, 'merchant_count': count} for name, count in plan_summary]
        }
