from flask import Blueprint
from api.controllers.product_controller import ProductController

# Create blueprint
product_bp = Blueprint('product', __name__)

# Define routes
@product_bp.route('/products', methods=['POST'])
def create_product():
    """Create a new product."""
    return ProductController.create_product()

@product_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get product details by ID."""
    return ProductController.get_product(product_id)

@product_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update product details."""
    return ProductController.update_product(product_id)

@product_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product."""
    return ProductController.delete_product(product_id)

@product_bp.route('/products', methods=['GET'])
def list_products():
    """List all products for the authenticated merchant."""
    return ProductController.list_products()

@product_bp.route('/products/<int:product_id>/stock', methods=['PUT'])
def update_stock(product_id):
    """Update product stock quantity."""
    return ProductController.update_stock(product_id)

@product_bp.route('/products/<int:product_id>/price', methods=['PUT'])
def update_price(product_id):
    """Update product price."""
    return ProductController.update_price(product_id) 