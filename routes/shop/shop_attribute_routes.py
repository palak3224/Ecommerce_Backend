from flask import Blueprint
from controllers.shop.shop_attribute_controller import ShopAttributeController

shop_attribute_bp = Blueprint('shop_attribute', __name__, url_prefix='/api/shop/attributes')

# Shop attribute management routes
shop_attribute_bp.add_url_rule('/shop/<int:shop_id>/category/<int:category_id>', methods=['GET'], view_func=ShopAttributeController.get_attributes_by_shop_category)
shop_attribute_bp.add_url_rule('/<int:attribute_id>', methods=['GET'], view_func=ShopAttributeController.get_attribute_by_id)
shop_attribute_bp.add_url_rule('', methods=['POST'], view_func=ShopAttributeController.create_attribute)
shop_attribute_bp.add_url_rule('/<int:attribute_id>', methods=['PUT'], view_func=ShopAttributeController.update_attribute)
shop_attribute_bp.add_url_rule('/<int:attribute_id>', methods=['DELETE'], view_func=ShopAttributeController.delete_attribute)

# Shop attribute value management routes  
shop_attribute_bp.add_url_rule('/values', methods=['POST'], view_func=ShopAttributeController.add_attribute_value)
shop_attribute_bp.add_url_rule('/values/<int:value_id>', methods=['PUT'], view_func=ShopAttributeController.update_attribute_value)
shop_attribute_bp.add_url_rule('/values/<int:value_id>', methods=['DELETE'], view_func=ShopAttributeController.delete_attribute_value)
