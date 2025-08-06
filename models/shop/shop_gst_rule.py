from datetime import datetime, timezone, date as DDate
from common.database import db, BaseModel
from models.enums import ProductPriceConditionType
from models.shop.shop_category import ShopCategory
from models.shop.shop import Shop
from sqlalchemy import or_, and_, desc
from decimal import Decimal, InvalidOperation

class ShopGSTRule(BaseModel):
    __tablename__ = 'shop_gst_rules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Shop and Category association
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.category_id'), nullable=False, index=True)
    
    price_condition_type = db.Column(db.Enum(ProductPriceConditionType), nullable=False, default=ProductPriceConditionType.ANY)
    price_condition_value = db.Column(db.Numeric(10, 2), nullable=True)  # e.g., 1000.00
    
    gst_rate_percentage = db.Column(db.Numeric(5, 2), nullable=False)  # e.g., 5.00 for 5%

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # created_at and updated_at are inherited from BaseModel

    # Relationships
    shop = db.relationship('Shop', foreign_keys=[shop_id])
    category = db.relationship('ShopCategory', foreign_keys=[category_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])

    # Unique constraint to prevent duplicate rules for same shop+category combination
    __table_args__ = (
        db.UniqueConstraint('name', 'shop_id', name='uq_shop_gst_rule_name_shop'),
    )

    def __repr__(self):
        return f"<ShopGSTRule id={self.id} name='{self.name}' shop_id='{self.shop_id}' category_id='{self.category_id}' rate='{self.gst_rate_percentage}%'>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "shop_id": self.shop_id,
            "shop_name": self.shop.name if self.shop else "N/A",
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "N/A",
            "price_condition_type": self.price_condition_type.value,
            "price_condition_value": str(self.price_condition_value) if self.price_condition_value is not None else None,
            "gst_rate_percentage": str(self.gst_rate_percentage),
            "is_active": self.is_active,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }

    @staticmethod
    def _get_category_lineage_ids(shop_category_id, db_session):
        """
        Get category lineage IDs for shop categories (similar to merchant categories)
        Returns a list of category IDs from most specific to most general
        """
        try:
            category = db_session.query(ShopCategory).get(shop_category_id)
            if not category:
                return []
            
            lineage_ids = [shop_category_id]
            current_category = category
            
            # Traverse up the parent hierarchy
            while current_category and current_category.parent_id:
                parent = db_session.query(ShopCategory).get(current_category.parent_id)
                if parent:
                    lineage_ids.append(parent.category_id)
                    current_category = parent
                else:
                    break
            
            return lineage_ids
            
        except Exception:
            return [shop_category_id]  # Return at least the original category ID

    @staticmethod
    def find_applicable_rule(db_session, shop_id, product_category_id, product_inclusive_price: Decimal):
        """
        Find the most applicable GST rule for a shop product
        Args:
            db_session: Database session
            shop_id: Shop ID
            product_category_id: Shop category ID of the product
            product_inclusive_price: Product price (inclusive of GST)
        Returns:
            ShopGSTRule instance or None
        """
        today = DDate.today()
        
        try:
            inclusive_price_decimal = Decimal(product_inclusive_price)
        except (TypeError, InvalidOperation):
            return None  # Cannot determine rule without a valid price

        category_lineage_ids = ShopGSTRule._get_category_lineage_ids(product_category_id, db_session)
        if not category_lineage_ids:
            return None

        all_active_rules = db_session.query(ShopGSTRule).filter(
            ShopGSTRule.is_active == True,
            ShopGSTRule.shop_id == shop_id,  # Shop-specific rules
            ShopGSTRule.category_id.in_(category_lineage_ids),
            or_(ShopGSTRule.start_date == None, ShopGSTRule.start_date <= today),
            or_(ShopGSTRule.end_date == None, ShopGSTRule.end_date >= today)
        ).order_by(
            desc(ShopGSTRule.id)
        ).all()

        if not all_active_rules:
            return None

        best_rule_for_product = None

        # Check each category level in the lineage (most specific first)
        for current_lineage_cat_id in category_lineage_ids:
            rules_for_this_category_level = [
                rule for rule in all_active_rules if rule.category_id == current_lineage_cat_id
            ]

            if not rules_for_this_category_level:
                continue

            matched_rules_at_this_level = []
            for rule in rules_for_this_category_level:
                price_condition_met = False
                if rule.price_condition_type == ProductPriceConditionType.ANY:
                    price_condition_met = True
                elif rule.price_condition_value is not None:
                    # Price condition in rule refers to INCLUSIVE price
                    rule_price_val_inclusive = Decimal(rule.price_condition_value)
                    
                    if rule.price_condition_type == ProductPriceConditionType.LESS_THAN and inclusive_price_decimal < rule_price_val_inclusive:
                        price_condition_met = True
                    elif rule.price_condition_type == ProductPriceConditionType.LESS_THAN_OR_EQUAL and inclusive_price_decimal <= rule_price_val_inclusive:
                        price_condition_met = True
                    elif rule.price_condition_type == ProductPriceConditionType.GREATER_THAN and inclusive_price_decimal > rule_price_val_inclusive:
                        price_condition_met = True
                    elif rule.price_condition_type == ProductPriceConditionType.GREATER_THAN_OR_EQUAL and inclusive_price_decimal >= rule_price_val_inclusive:
                        price_condition_met = True
                    elif rule.price_condition_type == ProductPriceConditionType.EQUAL and inclusive_price_decimal == rule_price_val_inclusive:
                        price_condition_met = True

                if price_condition_met:
                    matched_rules_at_this_level.append(rule)

            # If we found matching rules at this category level, use the most recent one
            if matched_rules_at_this_level:
                # Sort by ID descending to get the most recent rule
                matched_rules_at_this_level.sort(key=lambda r: r.id, reverse=True)
                best_rule_for_product = matched_rules_at_this_level[0]
                break  # Found a rule at this category level, stop looking at parent levels

        return best_rule_for_product
