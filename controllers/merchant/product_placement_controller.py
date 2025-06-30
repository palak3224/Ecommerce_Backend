# controllers/merchant/product_placement_controller.py
from flask import current_app
from flask_jwt_extended import get_jwt_identity
from models.product_placement import ProductPlacement, PlacementTypeEnum 
from models.product import Product 
from auth.models.models import MerchantProfile 
from common.database import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta

class MerchantProductPlacementController:
    # Default limits if no subscription plan is found
    DEFAULT_PLACEMENT_LIMIT_PER_TYPE = 10 

    @staticmethod
    def _get_current_merchant():
        """Helper to get current authenticated merchant's profile."""
        user_id = get_jwt_identity()
        merchant = MerchantProfile.query.filter_by(user_id=user_id).first_or_404(
            description="Merchant profile not found for the current user."
        )
        return merchant

    @staticmethod
    def list_placements(placement_type_filter_str=None):
        """
        Lists only currently active placements for the current merchant.
        Optionally filters by placement_type.
        """
        merchant = MerchantProductPlacementController._get_current_merchant()
        
        # Only show active, non-expired placements
        now_utc = datetime.now(timezone.utc)
        query = ProductPlacement.query.filter(
            ProductPlacement.merchant_id == merchant.id,
            ProductPlacement.is_active == True,
            (ProductPlacement.expires_at == None) | (ProductPlacement.expires_at > now_utc)
        )
        
        if placement_type_filter_str:
            try:
                placement_type_enum = PlacementTypeEnum[placement_type_filter_str.upper()]
                query = query.filter_by(placement_type=placement_type_enum)
            except KeyError:
                raise ValueError(f"Invalid placement_type filter: {placement_type_filter_str}")
                
        return query.order_by(ProductPlacement.placement_type, ProductPlacement.sort_order, ProductPlacement.added_at.desc()).all()

    @staticmethod
    def get_placement_details(placement_id):
        """Gets details of a specific placement owned by the current merchant."""
        merchant = MerchantProductPlacementController._get_current_merchant()
        placement = ProductPlacement.query.filter_by(
            placement_id=placement_id,
            merchant_id=merchant.id
        ).first_or_404(
            description=f"Product placement with ID {placement_id} not found or not owned by you."
        )
        return placement

    @staticmethod
    def add_product_to_placement(product_id, placement_type_str, sort_order=0, promotional_price=None, special_start=None, special_end=None):
        """
        Adds a merchant's product to a specific placement type (FEATURED or PROMOTED).
        For PROMOTED placements, also updates the product's special pricing and dates.
        """
        merchant = MerchantProductPlacementController._get_current_merchant()

        if not merchant.can_place_premium:
            raise PermissionError("Your account does not have an active subscription for premium product placements.")

        try:
            placement_type_enum = PlacementTypeEnum[placement_type_str.upper()]
        except KeyError:
            allowed_types = [t.name for t in PlacementTypeEnum]
            raise ValueError(f"Invalid placement_type '{placement_type_str}'. Allowed types are: {', '.join(allowed_types)}")

        product = Product.query.filter_by(
            product_id=product_id,
            merchant_id=merchant.id,
            deleted_at=None 
        ).first_or_404(
            description=f"Product with ID {product_id} not found or does not belong to you."
        )

        # Validate promotional data for PROMOTED placements
        if placement_type_enum == PlacementTypeEnum.PROMOTED:
            if not promotional_price or not special_start or not special_end:
                raise ValueError("Promotional price, start date, and end date are required for promoted products.")
            
            try:
                promotional_price = float(promotional_price)
                if promotional_price <= 0:
                    raise ValueError("Promotional price must be greater than 0.")
            except ValueError:
                raise ValueError("Invalid promotional price format.")

            try:
                special_start_date = datetime.strptime(special_start, '%Y-%m-%d').date()
                special_end_date = datetime.strptime(special_end, '%Y-%m-%d').date()
                
                if special_start_date < datetime.now().date():
                    raise ValueError("Special start date cannot be in the past.")
                if special_end_date <= special_start_date:
                    raise ValueError("Special end date must be after start date.")
                if (special_end_date - special_start_date).days > 30:
                    raise ValueError("Promotion period cannot exceed 30 days.")
                
                # Check if promotional end date exceeds subscription end date
                if merchant.subscription_expires_at and special_end_date > merchant.subscription_expires_at.date():
                    raise ValueError(f"Promotional end date cannot be beyond your subscription expiry date ({merchant.subscription_expires_at.date()}).")
                    
            except ValueError as e:
                if 'Invalid date format' not in str(e):
                    raise ValueError(str(e))
                raise ValueError(f"Invalid date format or {str(e)}")

        # Check monthly slot usage instead of current active count
        monthly_usage = MerchantProductPlacementController.get_monthly_placement_usage(
            merchant.id, 
            merchant.subscription_started_at.isoformat() if merchant.subscription_started_at else None
        )
        
        # Get plan limits
        plan_limits = MerchantProductPlacementController.get_plan_limits(merchant)
        placement_limit = plan_limits['featured_limit'] if placement_type_enum == PlacementTypeEnum.FEATURED else plan_limits['promo_limit']
        
        monthly_used = monthly_usage['monthly_featured_used'] if placement_type_enum == PlacementTypeEnum.FEATURED else monthly_usage['monthly_promo_used']
        
        if monthly_used >= placement_limit:
            raise ValueError(f"You have reached your monthly limit of {placement_limit} products for '{placement_type_enum.value}' placements. This limit resets each month based on your subscription cycle.")

        try:
            # Update product with promotional data if it's a PROMOTED placement
            if placement_type_enum == PlacementTypeEnum.PROMOTED:
                product.special_price = promotional_price
                product.special_start = special_start_date
                product.special_end = special_end_date
                db.session.add(product)

            # Reactivate existing soft-deleted placement if exists, or block duplicates
            existing = ProductPlacement.query.filter_by(
                product_id=product.product_id,
                merchant_id=merchant.id,
                placement_type=placement_type_enum
            ).first()
            if existing:
                if not existing.is_active:
                    # Reactivate without counting as new monthly usage
                    existing.is_active = True
                    existing.sort_order = int(sort_order)
                    # reset expiry for promoted placements
                    existing.expires_at = special_end_date if placement_type_enum == PlacementTypeEnum.PROMOTED else None
                    db.session.add(existing)
                    db.session.commit()
                    return existing
                # Already active => duplicate
                raise ValueError(f"This product is already in '{placement_type_str}' placements.")

            # Reactivate existing soft-deleted placement if exists
            existing = ProductPlacement.query.filter_by(
                product_id=product.product_id,
                merchant_id=merchant.id,
                placement_type=placement_type_enum
            ).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.sort_order = int(sort_order)
                    existing.expires_at = special_end_date if placement_type_enum == PlacementTypeEnum.PROMOTED else None
                    db.session.add(existing)
                    db.session.commit()
                    return existing
                # Already active => duplicate
                raise ValueError(f"This product is already in '{placement_type_str}' placements.")

            # Create the placement
            new_placement = ProductPlacement(
                product_id=product.product_id,
                merchant_id=merchant.id,
                placement_type=placement_type_enum,
                sort_order=int(sort_order),
                is_active=True,
                expires_at=special_end_date if placement_type_enum == PlacementTypeEnum.PROMOTED else None,
                added_at=datetime.now(timezone.utc)
            )
            db.session.add(new_placement)
            db.session.commit()
            return new_placement
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.warning(f"IntegrityError adding product {product_id} to {placement_type_str} for merchant {merchant.id}: {e}")
            raise ValueError(f"This product is already in '{placement_type_str}' placements.") from e
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding product {product_id} to {placement_type_str} for merchant {merchant.id}: {e}")
            raise RuntimeError("An unexpected error occurred while adding product to placement.") from e

    @staticmethod
    def update_placement_sort_order(placement_id, new_sort_order):
        """Updates the sort order of a merchant's product placement."""
        merchant = MerchantProductPlacementController._get_current_merchant()
        
        placement = ProductPlacement.query.filter_by(
            placement_id=placement_id,
            merchant_id=merchant.id
        ).first_or_404(
             description=f"Product placement with ID {placement_id} not found or not owned by you."
        )

        try:
            placement.sort_order = int(new_sort_order)
            db.session.commit()
            return placement
        except ValueError:
            raise ValueError("Sort order must be an integer.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating sort order for placement {placement_id}: {e}")
            raise RuntimeError("Could not update sort order.")

    @staticmethod
    def remove_product_from_placement(placement_id, cleanup_promotion=False):
        """
        Soft-deletes a product placement for the current merchant by marking it inactive and setting expiry.
        This ensures the placement is no longer active for display but retains history for monthly usage.
        If cleanup_promotion is True, also cleans up promotional pricing from the product.
        """
        merchant = MerchantProductPlacementController._get_current_merchant()
        
        placement = ProductPlacement.query.filter_by(
            placement_id=placement_id,
            merchant_id=merchant.id
        ).first_or_404(
             description=f"Product placement with ID {placement_id} not found or not owned by you."
        )
        
        try:
            # Clean up promotional pricing if it's a promoted placement
            if cleanup_promotion and placement.placement_type == PlacementTypeEnum.PROMOTED:
                product = Product.query.filter_by(product_id=placement.product_id).first()
                if product:
                    product.special_price = None
                    product.special_start = None
                    product.special_end = None
                    if hasattr(product, 'is_on_special_offer'):
                        product.is_on_special_offer = False
                    db.session.add(product)

            # Soft delete placement: mark inactive and expire now
            placement.is_active = False
            placement.expires_at = datetime.now(timezone.utc)
            db.session.add(placement)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error hard deleting placement {placement_id}: {e}")
            raise RuntimeError("Could not remove product from placement.")

    @staticmethod
    def update_promoted_placement(placement_id, promotional_price, special_start, special_end):
        """
        Updates a promoted placement's promotional details.
        Only allows updating promotional price and dates for promoted placements.
        """
        merchant = MerchantProductPlacementController._get_current_merchant()
        
        placement = ProductPlacement.query.filter_by(
            placement_id=placement_id,
            merchant_id=merchant.id
        ).first_or_404(
             description=f"Product placement with ID {placement_id} not found or not owned by you."
        )
        
        if placement.placement_type != PlacementTypeEnum.PROMOTED:
            raise ValueError("Only promoted placements can be updated with promotional details.")
        
        # Validate promotional data
        if not promotional_price or not special_start or not special_end:
            raise ValueError("Promotional price, start date, and end date are required.")
        
        try:
            promotional_price = float(promotional_price)
            if promotional_price <= 0:
                raise ValueError("Promotional price must be greater than 0.")
        except ValueError:
            raise ValueError("Invalid promotional price format.")

        try:
            special_start_date = datetime.strptime(special_start, '%Y-%m-%d').date()
            special_end_date = datetime.strptime(special_end, '%Y-%m-%d').date()
            
            if special_start_date < datetime.now().date():
                raise ValueError("Special start date cannot be in the past.")
            if special_end_date <= special_start_date:
                raise ValueError("Special end date must be after start date.")
            if (special_end_date - special_start_date).days > 30:
                raise ValueError("Promotion period cannot exceed 30 days.")
            
            # Check if promotional end date exceeds subscription end date
            if merchant.subscription_expires_at and special_end_date > merchant.subscription_expires_at.date():
                raise ValueError(f"Promotional end date cannot be beyond your subscription expiry date ({merchant.subscription_expires_at.date()}).")
                
        except ValueError as e:
            if 'Invalid date format' in str(e):
                raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            raise ValueError(str(e))

        try:
            # Update the product's promotional details
            product = Product.query.filter_by(product_id=placement.product_id).first()
            if product:
                product.special_price = promotional_price
                product.special_start = special_start_date
                product.special_end = special_end_date
                if hasattr(product, 'is_on_special_offer'):
                    product.is_on_special_offer = True
                db.session.add(product)
            
            # Update placement expiry date
            placement.expires_at = datetime.combine(special_end_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            db.session.add(placement)
            db.session.commit()
            return placement
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating promoted placement {placement_id}: {e}")
            raise RuntimeError("Could not update promoted placement.")

    @staticmethod
    def get_plan_limits(merchant):
        """Get the placement limits for the merchant's subscription plan."""
        if merchant.subscription_plan:
            return {
                'featured_limit': merchant.subscription_plan.featured_limit,
                'promo_limit': merchant.subscription_plan.promo_limit
            }
        else:
            # Return default limits if no subscription plan
            return {
                'featured_limit': MerchantProductPlacementController.DEFAULT_PLACEMENT_LIMIT_PER_TYPE,
                'promo_limit': MerchantProductPlacementController.DEFAULT_PLACEMENT_LIMIT_PER_TYPE
            }

    @staticmethod
    def get_monthly_placement_usage(merchant_id, subscription_started_at):
        """
        Calculate monthly usage for featured and promoted placements.
        Returns the total number of placements added this month based on subscription cycle.
        This counts ALL placements added in the current monthly cycle, regardless of deletion.
        """
        if not subscription_started_at:
            return {'monthly_featured_used': 0, 'monthly_promo_used': 0}
        
        try:
            # Parse subscription start date
            subscription_start = datetime.fromisoformat(subscription_started_at.replace('Z', '+00:00'))
            current_date = datetime.now(timezone.utc)
            
            # Calculate current monthly cycle start
            cycle_start = MerchantProductPlacementController._calculate_current_cycle_start(
                subscription_start, current_date
            )
            
            # Count ALL placements added in this monthly cycle (including deleted ones)
            # This ensures monthly quota is properly enforced
            featured_count = ProductPlacement.query.filter(
                ProductPlacement.merchant_id == merchant_id,
                ProductPlacement.placement_type == PlacementTypeEnum.FEATURED,
                ProductPlacement.added_at >= cycle_start
            ).count()
            
            promoted_count = ProductPlacement.query.filter(
                ProductPlacement.merchant_id == merchant_id,
                ProductPlacement.placement_type == PlacementTypeEnum.PROMOTED,
                ProductPlacement.added_at >= cycle_start
            ).count()
            
            return {
                'monthly_featured_used': featured_count,
                'monthly_promo_used': promoted_count
            }
        except Exception as e:
            current_app.logger.error(f"Error calculating monthly usage: {str(e)}")
            return {'monthly_featured_used': 0, 'monthly_promo_used': 0}

    @staticmethod
    def _calculate_current_cycle_start(subscription_start, current_date):
        """
        Calculate the start of the current monthly billing cycle.
        Handles edge cases like different month lengths.
        """
        # Start with subscription start date components
        start_day = subscription_start.day
        
        # Find how many full months have passed
        months_diff = (current_date.year - subscription_start.year) * 12 + (current_date.month - subscription_start.month)
        
        # If current day is before the subscription day, we're still in the previous cycle
        if current_date.day < start_day:
            months_diff -= 1
        
        # Calculate cycle start year and month
        cycle_year = subscription_start.year + months_diff // 12
        cycle_month = subscription_start.month + months_diff % 12
        
        # Handle month overflow
        if cycle_month > 12:
            cycle_year += 1
            cycle_month -= 12
        
        # Handle day edge cases (e.g., subscription started on 31st but current month has 30 days)
        import calendar
        max_day_in_cycle_month = calendar.monthrange(cycle_year, cycle_month)[1]
        cycle_day = min(start_day, max_day_in_cycle_month)
        
        # Create the cycle start datetime
        cycle_start = subscription_start.replace(
            year=cycle_year,
            month=cycle_month,
            day=cycle_day
        )
        
        return cycle_start