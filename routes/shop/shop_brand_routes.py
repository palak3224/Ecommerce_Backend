from flask import Blueprint
from controllers.shop.shop_brand_controller import ShopBrandController

shop_brand_bp = Blueprint('shop_brand', __name__, url_prefix='/api/shop/brands')

# Shop brand management routes
shop_brand_bp.add_url_rule('/shop/<int:shop_id>', methods=['GET'], view_func=ShopBrandController.get_brands_by_shop_category)
shop_brand_bp.add_url_rule('/shop/<int:shop_id>/category/<int:category_id>', methods=['GET'], view_func=ShopBrandController.get_brands_by_shop_category)
shop_brand_bp.add_url_rule('/<int:brand_id>', methods=['GET'], view_func=ShopBrandController.get_brand_by_id)
shop_brand_bp.add_url_rule('', methods=['POST'], view_func=ShopBrandController.create_brand)
shop_brand_bp.add_url_rule('/<int:brand_id>', methods=['PUT'], view_func=ShopBrandController.update_brand)
shop_brand_bp.add_url_rule('/<int:brand_id>', methods=['DELETE'], view_func=ShopBrandController.delete_brand)
