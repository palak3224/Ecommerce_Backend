from flask import Blueprint, request, jsonify
from controllers.product_controller import ProductController
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from models.recently_viewed import RecentlyViewed
from common.database import db
from datetime import datetime
from sqlalchemy import desc

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
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify([]), 200
            
        # Get the 6 most recently viewed products
        recent_views = RecentlyViewed.query.filter_by(
            user_id=user_id
        ).order_by(
            desc(RecentlyViewed.viewed_at)
        ).limit(6).all()
        
        # Get the product details for each view
        products = []
        for view in recent_views:
            if view.product and view.product.active_flag and not view.product.deleted_at:
                product_dict = view.product.serialize()
                # Add frontend-specific fields
                product_dict.update({
                    'id': str(view.product.product_id),
                    'name': view.product.product_name,
                    'price': float(view.product.selling_price),
                    'originalPrice': float(view.product.cost_price),
                    'currency': 'USD',
                    'stock': 100,
                    'isNew': True,
                    'isBuiltIn': False,
                    'rating': 0,
                    'reviews': [],
                    'sku': view.product.sku if hasattr(view.product, 'sku') else None
                })
                
                # Get primary media
                media = ProductController.get_product_media(view.product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']
                
                products.append(product_dict)
        
        return jsonify(products), 200
        
    except Exception as e:
        print(f"Error in get_recently_viewed: {str(e)}")
        return jsonify({
            "error": "Failed to fetch recently viewed products",
            "message": str(e)
        }), 500

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

@product_bp.route('/api/products/<int:product_id>/details', methods=['GET'])
@cross_origin()
def get_product_details(product_id):
    """
    Get detailed product information including media and meta data.
    Also tracks the product view for authenticated users.
    """
    try:
        # Try to get the current user ID if authenticated
        user_id = None
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
        except Exception:
            # If JWT verification fails, continue without user tracking
            pass
        
        # If user is authenticated, track the view
        if user_id:
            # Check if there's an existing view record
            existing_view = RecentlyViewed.query.filter_by(
                user_id=user_id,
                product_id=product_id
            ).first()
            
            if existing_view:
                # Update the viewed_at timestamp
                existing_view.viewed_at = datetime.utcnow()
            else:
                # Create a new view record
                new_view = RecentlyViewed(
                    user_id=user_id,
                    product_id=product_id,
                    viewed_at=datetime.utcnow()
                )
                db.session.add(new_view)
            
            # Commit the changes
            db.session.commit()
        
        # Get and return the product details
        return ProductController.get_product_details(product_id)
        
    except Exception as e:
        print(f"Error in get_product_details route: {str(e)}")
        return jsonify({
            "error": "Failed to fetch product details",
            "message": str(e)
        }), 500 