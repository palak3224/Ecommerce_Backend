from flask import Blueprint
from controllers.shop.shop_category_controller import ShopCategoryController

shop_category_bp = Blueprint('shop_category', __name__, url_prefix='/api/shop/categories')

# Shop category management routes
shop_category_bp.add_url_rule('/shop/<int:shop_id>', methods=['GET'], view_func=ShopCategoryController.get_categories_by_shop)
shop_category_bp.add_url_rule('/<int:category_id>', methods=['GET'], view_func=ShopCategoryController.get_category_by_id)
shop_category_bp.add_url_rule('', methods=['POST'], view_func=ShopCategoryController.create_category)
shop_category_bp.add_url_rule('/<int:category_id>', methods=['PUT'], view_func=ShopCategoryController.update_category)
shop_category_bp.add_url_rule('/<int:category_id>', methods=['DELETE'], view_func=ShopCategoryController.delete_category)
