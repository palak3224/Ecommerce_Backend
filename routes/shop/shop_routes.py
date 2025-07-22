from flask import Blueprint
from controllers.shop.shop_controller import ShopController

shop_bp = Blueprint('shop', __name__, url_prefix='/api/shop/shops')

# Shop management routes
shop_bp.add_url_rule('', methods=['GET'], view_func=ShopController.get_all_shops)
shop_bp.add_url_rule('/<int:shop_id>', methods=['GET'], view_func=ShopController.get_shop_by_id)
shop_bp.add_url_rule('', methods=['POST'], view_func=ShopController.create_shop)
shop_bp.add_url_rule('/<int:shop_id>', methods=['PUT'], view_func=ShopController.update_shop)
shop_bp.add_url_rule('/<int:shop_id>', methods=['DELETE'], view_func=ShopController.delete_shop)
