
from flask import Blueprint
from controllers.shop.shop_product_controller import ShopProductController
from flask_cors import cross_origin

shop_product_bp = Blueprint('shop_product', __name__)

@shop_product_bp.route('/api/shop/products', methods=['GET'])
@cross_origin()
def get_products():
    return ShopProductController.get_all_products()

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['GET'])
@cross_origin()
def get_product(product_id):
    return ShopProductController.get_product(product_id)

@shop_product_bp.route('/api/shop/products', methods=['POST'])
@cross_origin()
def create_product():
    return ShopProductController.create_product()

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['PUT'])
@cross_origin()
def update_product(product_id):
    return ShopProductController.update_product(product_id)

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['DELETE'])
@cross_origin()
def delete_product(product_id):
    return ShopProductController.delete_product(product_id)
