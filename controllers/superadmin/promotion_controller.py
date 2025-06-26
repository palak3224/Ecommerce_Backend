# FILE: controllers/superadmin/promotion_controller.py
import secrets
from datetime import datetime
from sqlalchemy.orm import joinedload
from models.promotion import Promotion
from common.database import db

class PromotionController:
    @staticmethod
    def list_all():
        """Lists all non-deleted promotions, eager loading related targets."""
        return Promotion.query.options(
            joinedload(Promotion.product),
            joinedload(Promotion.category),
            joinedload(Promotion.brand)
        ).filter_by(deleted_at=None).order_by(Promotion.created_at.desc()).all()

    @staticmethod
    def create(data):
        """Creates a new promotion."""
        # Validate that only one target is provided
        targets = ['product_id', 'category_id', 'brand_id']
        provided_targets = [t for t in targets if data.get(t)]
        if len(provided_targets) > 1:
            raise ValueError("A promotion can only be applied to one target (product, category, or brand).")

        # Handle promotion code
        if data.get('code'):
            code = data['code'].upper()
            if Promotion.query.filter_by(code=code).first():
                raise ValueError(f"Promotion code '{code}' already exists.")
        else:
            # Generate a unique code
            while True:
                code = secrets.token_hex(4).upper()
                if not Promotion.query.filter_by(code=code).first():
                    break
        
        # Validate dates
        try:
            # Handle ISO format with or without 'Z'
            start_date_str = data['start_date'].replace('Z', '+00:00')
            end_date_str = data['end_date'].replace('Z', '+00:00')
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            if end_date < start_date:
                raise ValueError("End date cannot be before the start date.")
        except (ValueError, TypeError, KeyError):
            raise ValueError("Invalid or missing date format. Use ISO 8601 format (YYYY-MM-DD).")

        promo = Promotion(
            code=code,
            description=data.get('description'),
            discount_type=data['discount_type'],
            discount_value=data['discount_value'],
            product_id=data.get('product_id'),
            category_id=data.get('category_id'),
            brand_id=data.get('brand_id'),
            start_date=start_date,
            end_date=end_date,
            active_flag=data.get('active_flag', True)
        )
        promo.save()
        return promo

    @staticmethod
    def update(promo_id, data):
        """Updates an existing promotion."""
        p = Promotion.query.get_or_404(promo_id)
        
      
        original_target_field = None
        if p.product_id: original_target_field = 'product_id'
        elif p.category_id: original_target_field = 'category_id'
        elif p.brand_id: original_target_field = 'brand_id'

        # 2. Check if the incoming data tries to set a *different* target type.
        new_target_fields = [
            field for field in ['product_id', 'category_id', 'brand_id'] 
            if field in data and data[field] is not None
        ]
        
        if len(new_target_fields) > 1:
            raise ValueError("Cannot set more than one target type (product, category, brand) in an update.")
        
        # If there's a new target, check if it conflicts with the original.
        if new_target_fields:
            new_target_field = new_target_fields[0]
            if original_target_field and new_target_field != original_target_field:
                raise ValueError(f"Cannot change target type from '{original_target_field}' to '{new_target_field}'. Please create a new promotion.")


        # Updateable fields
        if 'description' in data:
            p.description = data['description']
        if 'discount_type' in data:
            p.discount_type = data['discount_type']
        if 'discount_value' in data:
            p.discount_value = data['discount_value']
        
        if 'start_date' in data:
            p.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')).date()
        if 'end_date' in data:
            p.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')).date()
            
        if 'active_flag' in data:
            p.active_flag = data['active_flag']
            
        if 'code' in data and data['code'].upper() != p.code:
            new_code = data['code'].upper()
            if Promotion.query.filter(Promotion.promotion_id != promo_id, Promotion.code == new_code).first():
                raise ValueError(f"Promotion code '{new_code}' is already in use.")
            p.code = new_code
        
        if p.end_date < p.start_date:
            raise ValueError("End date cannot be before the start date.")

        db.session.commit()
        return p

    @staticmethod
    def soft_delete(promo_id):
        """Soft deletes a promotion and deactivates it.""" 
        p = Promotion.query.get_or_404(promo_id)
        db.session.delete(p)    #update hard delete 
        db.session.commit()
        return p