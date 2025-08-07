from marshmallow import Schema, fields, validate, validates, ValidationError, post_load
from models.enums import ProductPriceConditionType
from datetime import date

class CreateShopGSTRuleSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    shop_id = fields.Int(required=True, validate=validate.Range(min=1))
    category_id = fields.Int(required=True, validate=validate.Range(min=1))
    
    price_condition_type = fields.Str(
        required=True,
        validate=validate.OneOf([e.value for e in ProductPriceConditionType])
    )
    price_condition_value = fields.Decimal(places=2, allow_none=True)
    gst_rate_percentage = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0, max=100)
    )
    
    is_active = fields.Bool(load_default=True)
    start_date = fields.Date(allow_none=True)
    end_date = fields.Date(allow_none=True)

    @post_load
    def convert_enum(self, data, **kwargs):
        """Convert price_condition_type string to enum"""
        if 'price_condition_type' in data:
            data['price_condition_type'] = ProductPriceConditionType(data['price_condition_type'])
        return data

    @validates('price_condition_value')
    def validate_price_condition_value(self, value):
        """Validate price condition value based on condition type"""
        # Note: This validation is performed after post_load, so we can't access the enum directly
        # We'll handle this validation in the controller
        if value is not None and value < 0:
            raise ValidationError("Price condition value must be non-negative.")

    @validates('start_date')
    def validate_start_date(self, value):
        """Validate start date - allow past dates for flexibility"""
        # Allow any date including past dates for flexibility in GST rule management
        pass

    @validates('end_date')
    def validate_end_date(self, value):
        """Validate end date is after start date"""
        # Note: We'll validate the relationship between dates in the controller
        # since we need access to both fields
        pass


class UpdateShopGSTRuleSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=100))
    shop_id = fields.Int(validate=validate.Range(min=1))
    category_id = fields.Int(validate=validate.Range(min=1))
    
    price_condition_type = fields.Str(
        validate=validate.OneOf([e.value for e in ProductPriceConditionType])
    )
    price_condition_value = fields.Decimal(places=2, allow_none=True)
    gst_rate_percentage = fields.Decimal(
        places=2,
        validate=validate.Range(min=0, max=100)
    )
    
    is_active = fields.Bool()
    start_date = fields.Date(allow_none=True)
    end_date = fields.Date(allow_none=True)

    @post_load
    def convert_enum(self, data, **kwargs):
        """Convert price_condition_type string to enum"""
        if 'price_condition_type' in data:
            data['price_condition_type'] = ProductPriceConditionType(data['price_condition_type'])
        return data

    @validates('price_condition_value')
    def validate_price_condition_value(self, value):
        """Validate price condition value"""
        if value is not None and value < 0:
            raise ValidationError("Price condition value must be non-negative.")


class ShopGSTRuleFilterSchema(Schema):
    """Schema for filtering shop GST rules"""
    shop_id = fields.Int(validate=validate.Range(min=1))
    category_id = fields.Int(validate=validate.Range(min=1))
    is_active = fields.Bool()
    page = fields.Int(validate=validate.Range(min=1), load_default=1)
    per_page = fields.Int(validate=validate.Range(min=1, max=100), load_default=20)
