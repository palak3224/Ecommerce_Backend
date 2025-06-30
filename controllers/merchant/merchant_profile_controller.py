from flask import current_app
from common.database import db
from auth.models import MerchantProfile
from models.product_placement import ProductPlacement
from models.subscription import SubscriptionPlan, SubscriptionHistory
from datetime import datetime, timedelta

class MerchantProfileController:
    @staticmethod
    def get_profile(user_id):
        """Get merchant profile by user ID."""
        try:
            profile = MerchantProfile.get_by_user_id(user_id)
            if not profile:
                raise ValueError("Merchant profile not found")
            return profile
        except Exception as e:
            current_app.logger.error(f"Error getting merchant profile: {str(e)}")
            raise

    @staticmethod
    def subscribe_to_plan(user_id, plan_id):
        """Subscribe merchant to a subscription plan."""
        try:
            profile = MerchantProfile.get_by_user_id(user_id)
            if not profile:
                raise ValueError("Merchant profile not found")

            plan = SubscriptionPlan.get_by_id(plan_id)
            if not plan:
                raise ValueError("Subscription plan not found")
            
            if not plan.active_flag:
                raise ValueError("This subscription plan is no longer active")

            # Create subscription history entry
            subscription_history = SubscriptionHistory(
                merchant_id=profile.id,
                subscription_plan_id=plan.plan_id,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=plan.duration_days),
                status='active',
                payment_status='pending'  # This should be updated after payment processing
            )
            db.session.add(subscription_history)

            # Update merchant profile
            profile.is_subscribed = True
            profile.subscription_plan_id = plan.plan_id
            profile.subscription_started_at = datetime.utcnow()
            profile.subscription_expires_at = subscription_history.end_date
            # Set can_place_premium based on subscription status
            profile.can_place_premium = True  # All subscribed users can place premium products
            
            db.session.commit()
            # Reactivate any previous soft-deleted placements up to plan limits when subscribing to a plan
            ProductPlacement.reactivate_placements_for_merchant(
                profile.id,
                subscription_duration_days=plan.duration_days,
                placement_limit_per_type=plan.featured_limit
            )
            ProductPlacement.reactivate_placements_for_merchant(
                profile.id,
                subscription_duration_days=plan.duration_days,
                placement_limit_per_type=plan.promo_limit
            )
            return profile
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error subscribing to plan: {str(e)}")
            raise

    @staticmethod
    def cancel_subscription(user_id):
        """Cancel merchant's current subscription."""
        try:
            profile = MerchantProfile.get_by_user_id(user_id)
            if not profile:
                raise ValueError("Merchant profile not found")

            if not profile.is_subscribed:
                raise ValueError("No active subscription to cancel")

            # Get active subscription history
            active_subscription = SubscriptionHistory.get_active_subscription(profile.id)
            if active_subscription:
                active_subscription.status = 'cancelled'
                active_subscription.updated_at = datetime.utcnow()

            # Delete all existing placements so slots reset on cancellation
            db.session.query(ProductPlacement).filter_by(merchant_id=profile.id).delete()
            # Update merchant profile
            profile.is_subscribed = False
            profile.subscription_plan_id = None
            profile.subscription_started_at = None
            profile.subscription_expires_at = None
            profile.can_place_premium = False  # Remove premium placement ability on cancellation
            # All placements have been deleted; no soft-deactivation needed
            
            db.session.commit()
            return profile
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling subscription: {str(e)}")
            raise

    @staticmethod
    def get_subscription_status(user_id):
        """Get merchant's current subscription status."""
        try:
            profile = MerchantProfile.get_by_user_id(user_id)
            if not profile:
                raise ValueError("Merchant profile not found")
            
            # Ensure can_place_premium is set correctly based on subscription status
            if profile.is_subscribed and not profile.can_place_premium:
                profile.can_place_premium = True
                db.session.commit()
            
            # Import here to avoid circular imports
            from controllers.merchant.product_placement_controller import MerchantProductPlacementController
            
            # Get monthly usage tracking
            monthly_usage = MerchantProductPlacementController.get_monthly_placement_usage(
                profile.id,
                profile.subscription_started_at.isoformat() if profile.subscription_started_at else None
            )
            
            return {
                "is_subscribed": profile.is_subscribed,
                "can_place_premium": profile.can_place_premium,
                "subscription_started_at": profile.subscription_started_at.isoformat() if profile.subscription_started_at else None,
                "subscription_expires_at": profile.subscription_expires_at.isoformat() if profile.subscription_expires_at else None,
                "monthly_featured_used": monthly_usage.get('monthly_featured_used', 0),
                "monthly_promo_used": monthly_usage.get('monthly_promo_used', 0),
                "plan": profile.subscription_plan.serialize() if profile.subscription_plan else None
            }
        except Exception as e:
            current_app.logger.error(f"Error getting subscription status: {str(e)}")
            raise