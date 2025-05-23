from flask import request, jsonify
from common.database import db
from models.product import Product
from models.category import Category
from models.brand import Brand
from models.product_media import ProductMedia
from models.variant_media import VariantMedia
from models.enums import MediaType
from sqlalchemy import desc, or_
from flask_jwt_extended import get_jwt_identity

class ProductController:
    @staticmethod
    def get_product_media(product_id):
        """Get primary media for a product"""
        # Get primary product media
        primary_media = ProductMedia.query.filter_by(
            product_id=product_id,
            deleted_at=None,
            type=MediaType.IMAGE
        ).order_by(
            ProductMedia.sort_order
        ).first()

        # If no product media, get primary variant media
        if not primary_media:
            variant_media = VariantMedia.query.filter_by(
                variant_id=product_id,
                deleted_at=None,
                media_type='image',
                is_primary=True
            ).first()
            
            if variant_media:
                return variant_media.serialize()
            return None

        return primary_media.serialize()

    @staticmethod
    def get_all_products():
        """Get all products with pagination and filtering"""
        try:
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # Get filter parameters
            category_id = request.args.get('category_id', type=int)
            brand_id = request.args.get('brand_id', type=int)
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            
            # Base query
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True)
            )
            
            # Apply category filter with child categories
            if category_id:
                # Get all child category IDs
                child_categories = Category.query.filter_by(parent_id=category_id).all()
                child_category_ids = [cat.category_id for cat in child_categories]
                
                # Include both the selected category and its children
                category_ids = [category_id] + child_category_ids
                query = query.filter(Product.category_id.in_(category_ids))
            
            # Apply other filters
            if brand_id:
                query = query.filter(Product.brand_id == brand_id)
            if min_price is not None:
                query = query.filter(Product.selling_price >= min_price)
            if max_price is not None:
                query = query.filter(Product.selling_price <= max_price)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Product.product_name.ilike(search_term),
                        Product.product_description.ilike(search_term)
                    )
                )
                
            # Apply sorting
            if order == 'asc':
                query = query.order_by(getattr(Product, sort_by))
            else:
                query = query.order_by(desc(getattr(Product, sort_by)))
                
            # Execute paginated query
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            # Prepare response
            products = pagination.items
            total = pagination.total
            pages = pagination.pages
            
            # Get product data with media
            product_data = []
            for product in products:
                product_dict = product.serialize()
                # Add frontend-specific fields
                product_dict.update({
                    'id': str(product.product_id),  # Convert to string for frontend
                    'name': product.product_name,
                    'description': product.product_description,
                    'price': float(product.selling_price),
                    'originalPrice': float(product.cost_price),
                    'stock': 100,  # TODO: Add stock tracking
                    'isNew': True,  # TODO: Add logic for new products
                    'isBuiltIn': False,  # TODO: Add logic for built-in products
                })
                
                # Get primary media
                media = ProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']  # For backward compatibility
                
                product_data.append(product_dict)
            
            return jsonify({
                'products': product_data,
                'pagination': {
                    'total': total,
                    'pages': pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            })
        except Exception as e:
            print(f"Error in get_all_products: {str(e)}")
            return jsonify({
                'error': str(e),
                'products': [],
                'pagination': {
                    'total': 0,
                    'pages': 0,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': False,
                    'has_prev': False
                }
            }), 500

    @staticmethod
    def get_product(product_id):
        """Get a single product by ID"""
        product = Product.query.filter_by(
            product_id=product_id,
            deleted_at=None,
            active_flag=True
        ).first_or_404()
        
        # Get product data with media
        product_dict = product.serialize()
        media = ProductController.get_product_media(product_id)
        if media:
            product_dict['primary_image'] = media['url']
        
        return jsonify(product_dict)

    @staticmethod
    def get_recently_viewed():
        """Get recently viewed products for the current user"""
        try:
            from models.recently_viewed import RecentlyViewed
            user_id = get_jwt_identity()
            if not user_id:
                return jsonify([])
                
            recently_viewed = RecentlyViewed.query.filter_by(
                user_id=user_id
            ).order_by(
                desc(RecentlyViewed.viewed_at)
            ).limit(6).all()
            
            products = []
            for rv in recently_viewed:
                if rv.product and rv.product.active_flag and not rv.product.deleted_at:
                    product_dict = rv.product.serialize()
                    media = ProductController.get_product_media(rv.product.product_id)
                    if media:
                        product_dict['primary_image'] = media['url']
                    products.append(product_dict)
            
            return jsonify(products)
        except ImportError:
            # If RecentlyViewed model is not available yet, return empty list
            return jsonify([])

    @staticmethod
    def get_categories():
        """Get all product categories"""
        categories = Category.query.all()
        return jsonify([category.serialize() for category in categories])

    @staticmethod
    def get_brands():
        """Get all product brands"""
        try:
            # Get all brands that are not deleted
            brands = Brand.query.filter_by(
                deleted_at=None
            ).all()
            
            # Log the number of brands found
            print(f"Found {len(brands)} active brands")
            
            # Serialize and return the brands
            return jsonify([brand.serialize() for brand in brands])
        except Exception as e:
            print(f"Error fetching brands: {str(e)}")
            return jsonify([]), 500 