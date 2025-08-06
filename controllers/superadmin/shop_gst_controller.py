from flask import current_app
from common.database import db
from models.shop.shop_gst_rule import ShopGSTRule
from models.shop.shop import Shop
from models.shop.shop_category import ShopCategory
from models.enums import ProductPriceConditionType
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from decimal import Decimal

class ShopGSTManagementController:
    
    @staticmethod
    def list_shops():
        """Get all active shops for dropdown selection"""
        try:
            shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
            return [{"shop_id": shop.shop_id, "name": shop.name} for shop in shops]
        except Exception as e:
            current_app.logger.error(f"Error listing shops: {e}")
            raise
    
    @staticmethod
    def get_shop_categories(shop_id):
        """Get all categories for a specific shop"""
        try:
            # Verify shop exists
            shop = Shop.query.get(shop_id)
            if not shop:
                raise BadRequest(f"Shop with ID {shop_id} not found.")
            
            categories = ShopCategory.query.filter_by(shop_id=shop_id).order_by(ShopCategory.name).all()
            return [category.serialize() for category in categories]
        except Exception as e:
            current_app.logger.error(f"Error fetching shop categories: {e}")
            raise

    @staticmethod
    def list_all_rules():
        """List all shop GST rules"""
        try:
            rules = ShopGSTRule.query.order_by(ShopGSTRule.shop_id, ShopGSTRule.name).all()
            return [rule.serialize() for rule in rules]
        except Exception as e:
            current_app.logger.error(f"Error listing shop GST rules: {e}")
            raise

    @staticmethod
    def list_rules_by_shop(shop_id):
        """List GST rules for a specific shop"""
        try:
            # Verify shop exists
            shop = Shop.query.get(shop_id)
            if not shop:
                raise BadRequest(f"Shop with ID {shop_id} not found.")
            
            rules = ShopGSTRule.query.filter_by(shop_id=shop_id).order_by(ShopGSTRule.name).all()
            return [rule.serialize() for rule in rules]
        except Exception as e:
            current_app.logger.error(f"Error listing shop GST rules for shop {shop_id}: {e}")
            raise

    @staticmethod
    def get_rule(rule_id):
        """Get a specific GST rule by ID"""
        rule = ShopGSTRule.query.get(rule_id)
        if not rule:
            raise NotFound(f"Shop GST Rule with ID {rule_id} not found.")
        return rule.serialize()

    @staticmethod
    def create_rule(data, admin_id):
        """Create a new shop GST rule"""
        # Validate shop exists
        shop = Shop.query.get(data['shop_id'])
        if not shop:
            raise BadRequest(f"Shop with ID {data['shop_id']} not found.")

        # Validate category exists and belongs to the shop
        category = ShopCategory.query.filter_by(
            category_id=data['category_id'], 
            shop_id=data['shop_id']
        ).first()
        if not category:
            raise BadRequest(f"Category with ID {data['category_id']} not found in shop {data['shop_id']}.")

        # Check for existing rule name within the same shop
        if ShopGSTRule.query.filter_by(name=data['name'], shop_id=data['shop_id']).first():
            raise BadRequest(f"A GST Rule with the name '{data['name']}' already exists for this shop.")

        try:
            new_rule = ShopGSTRule(
                name=data['name'],
                shop_id=data['shop_id'],
                category_id=data['category_id'],
                price_condition_type=data['price_condition_type'],
                price_condition_value=data.get('price_condition_value'),
                gst_rate_percentage=Decimal(data['gst_rate_percentage']),
                is_active=data.get('is_active', True),
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                created_by=admin_id,
                updated_by=admin_id
            )

            db.session.add(new_rule)
            db.session.commit()

            current_app.logger.info(f"Shop GST Rule '{new_rule.name}' created successfully by admin {admin_id}")
            return new_rule.serialize()

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Database integrity error creating shop GST rule: {e}")
            if 'uq_shop_gst_rule_name_shop' in str(e):
                raise BadRequest("A GST Rule with this name already exists for this shop.")
            raise BadRequest("Failed to create GST rule due to data constraint violation.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error creating shop GST rule: {e}")
            raise

    @staticmethod
    def update_rule(rule_id, data, admin_id):
        """Update an existing shop GST rule"""
        rule = ShopGSTRule.query.get(rule_id)
        if not rule:
            raise NotFound(f"Shop GST Rule with ID {rule_id} not found.")

        # If shop_id is being changed, validate new shop
        if 'shop_id' in data and data['shop_id'] != rule.shop_id:
            shop = Shop.query.get(data['shop_id'])
            if not shop:
                raise BadRequest(f"Shop with ID {data['shop_id']} not found.")

        # If category_id is being changed, validate it exists and belongs to the shop
        if 'category_id' in data and data['category_id'] != rule.category_id:
            shop_id = data.get('shop_id', rule.shop_id)
            category = ShopCategory.query.filter_by(
                category_id=data['category_id'], 
                shop_id=shop_id
            ).first()
            if not category:
                raise BadRequest(f"Category with ID {data['category_id']} not found in shop {shop_id}.")

        # Check for duplicate name within the same shop
        if 'name' in data and data['name'] != rule.name:
            shop_id = data.get('shop_id', rule.shop_id)
            if ShopGSTRule.query.filter(
                ShopGSTRule.id != rule_id, 
                ShopGSTRule.name == data['name'], 
                ShopGSTRule.shop_id == shop_id
            ).first():
                raise BadRequest(f"A GST Rule with the name '{data['name']}' already exists for this shop.")

        try:
            # Update fields
            if 'name' in data:
                rule.name = data['name']
            if 'shop_id' in data:
                rule.shop_id = data['shop_id']
            if 'category_id' in data:
                rule.category_id = data['category_id']
            if 'price_condition_type' in data:
                rule.price_condition_type = data['price_condition_type']
            if 'price_condition_value' in data:
                rule.price_condition_value = data['price_condition_value']
            if 'gst_rate_percentage' in data:
                rule.gst_rate_percentage = Decimal(data['gst_rate_percentage'])
            if 'is_active' in data:
                rule.is_active = data['is_active']
            if 'start_date' in data:
                rule.start_date = data['start_date']
            if 'end_date' in data:
                rule.end_date = data['end_date']
            
            rule.updated_by = admin_id

            db.session.commit()

            current_app.logger.info(f"Shop GST Rule ID {rule_id} updated successfully by admin {admin_id}")
            return rule.serialize()

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Database integrity error updating shop GST rule {rule_id}: {e}")
            if 'uq_shop_gst_rule_name_shop' in str(e):
                raise BadRequest("A GST Rule with this name already exists for this shop.")
            raise BadRequest("Failed to update GST rule due to data constraint violation.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error updating shop GST rule {rule_id}: {e}")
            raise

    @staticmethod
    def delete_rule(rule_id, admin_id):
        """Delete a shop GST rule"""
        rule = ShopGSTRule.query.get(rule_id)
        if not rule:
            raise NotFound(f"Shop GST Rule with ID {rule_id} not found.")

        try:
            rule_name = rule.name
            shop_name = rule.shop.name if rule.shop else f"Shop {rule.shop_id}"
            
            db.session.delete(rule)
            db.session.commit()

            current_app.logger.info(f"Shop GST Rule '{rule_name}' from {shop_name} deleted successfully by admin {admin_id}")
            return {"message": f"Shop GST Rule '{rule_name}' deleted successfully."}

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Database integrity error deleting shop GST rule {rule_id}: {e}")
            # Check if it's a foreign key constraint violation
            if 'foreign key constraint' in str(e).lower():
                raise BadRequest("Cannot delete GST rule as it is referenced by other records.")
            raise BadRequest("Failed to delete GST rule due to database constraint.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error deleting shop GST rule {rule_id}: {e}")
            raise
