from flask import Blueprint, request, jsonify
from controllers.product_controller import ProductController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin

product_bp = Blueprint('product', __name__)

@product_bp.route('/api/products', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_products():
    """
    Get all products with pagination and filtering
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10, max: 50)
    - sort_by: Field to sort by (default: created_at)
    - order: Sort order (asc/desc, default: desc)
    - category_id: Filter by category
    - brand_id: Filter by brand
    - min_price: Minimum price filter
    - max_price: Maximum price filter
    - search: Search term for product name/description
    """
    if request.method == 'OPTIONS':
        return '', 200
    return ProductController.get_all_products()

@product_bp.route('/api/products/<int:product_id>', methods=['GET'])
@cross_origin()
def get_product(product_id):
    """Get a single product by ID"""
    return ProductController.get_product(product_id)

@product_bp.route('/api/products/recently-viewed', methods=['GET'])
@jwt_required()
@cross_origin()
def get_recently_viewed():
    """Get recently viewed products for the current user"""
    return ProductController.get_recently_viewed()

@product_bp.route('/api/products/categories', methods=['GET'])
@cross_origin()
def get_categories():
    """Get all product categories"""
    return ProductController.get_categories()

@product_bp.route('/api/products/brands', methods=['GET'])
@cross_origin()
def get_brands():
    """Get all product brands"""
    return ProductController.get_brands() 