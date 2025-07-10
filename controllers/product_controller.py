from flask import request, jsonify
from common.database import db
from models.product import Product
from models.category import Category
from models.brand import Brand
from models.product_media import ProductMedia
from models.enums import MediaType
from sqlalchemy import desc, or_, func
from flask_jwt_extended import get_jwt_identity
from models.product_meta import ProductMeta
from models.product_attribute import ProductAttribute
from datetime import datetime, timedelta
from models.order import OrderItem, Order
from models.review import Review
import json

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

        return primary_media.serialize() if primary_media else None

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
            category_id = request.args.get('category_id')
            brand_id = request.args.get('brand_id')
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            include_children = request.args.get('include_children', 'true').lower() == 'true'
            show_variants = request.args.get('show_variants', 'false').lower() == 'true'
            min_rating = request.args.get('min_rating', type=float)
            min_discount = request.args.get('min_discount', type=float)
            
            # Base query - only show approved products and filter by parent_product_id
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True),
                Product.approval_status == 'approved'  # Only show approved products
            )

            # Filter based on show_variants parameter
            if show_variants:
                # Show only variant products (parent_product_id is not null)
                query = query.filter(Product.parent_product_id.isnot(None))
            else:
                # Show only parent products (parent_product_id is null)
                query = query.filter(Product.parent_product_id.is_(None))
            
            # Apply category filter with child categories
            if category_id and category_id != 'all-products':
                try:
                    category_id = int(category_id)
                    if include_children:
                        # Get the category and all its child categories
                        category = Category.query.get(category_id)
                        if category:
                            # Get all child category IDs recursively
                            def get_child_category_ids(parent_id):
                                child_ids = []
                                children = Category.query.filter_by(parent_id=parent_id).all()
                                for child in children:
                                    child_ids.append(child.category_id)
                                    child_ids.extend(get_child_category_ids(child.category_id))
                                return child_ids
                            
                            child_category_ids = get_child_category_ids(category_id)
                            category_ids = [category_id] + child_category_ids
                            query = query.filter(Product.category_id.in_(category_ids))
                    else:
                        # Only include products from the selected category
                        query = query.filter(Product.category_id == category_id)
                except ValueError:
                    print(f"Invalid category_id: {category_id}")
            
            # Apply brand filter
            if brand_id:
                try:
                    # Handle multiple brand IDs
                    if ',' in brand_id:
                        brand_ids = [int(bid) for bid in brand_id.split(',')]
                        query = query.filter(Product.brand_id.in_(brand_ids))
                    else:
                        brand_id = int(brand_id)
                        query = query.filter(Product.brand_id == brand_id)
                except ValueError:
                    print(f"Invalid brand_id: {brand_id}")
                    

            # Apply price range filter
            if min_price is not None:
                query = query.filter(Product.selling_price >= min_price)
            if max_price is not None:
                query = query.filter(Product.selling_price <= max_price)

            # Apply discount filter
            if min_discount is not None:
                query = query.filter(Product.discount_pct >= min_discount)

            # Apply rating filter
            if min_rating is not None:
                # Join with reviews table and filter by average rating
                query = query.join(Review, Product.product_id == Review.product_id, isouter=True)\
                    .group_by(Product.product_id)\
                    .having(func.coalesce(func.avg(Review.rating), 0) >= min_rating)

            # Apply search filter
            if search:
                search_terms = search.lower().split()
                search_conditions = []
                
                for term in search_terms:
                    term = f"%{term}%"
                    search_conditions.extend([
                        Product.product_name.ilike(term),
                        Product.product_description.ilike(term),
                        Product.sku.ilike(term),
                        Category.name.ilike(term),
                        Brand.name.ilike(term)
                    ])
                
                # Join with category and brand tables for searching
                query = query.outerjoin(Category).outerjoin(Brand)
                
                # Apply the search conditions
                query = query.filter(or_(*search_conditions))
                
                # Add relevance scoring
                from sqlalchemy import case, literal_column
                
                relevance = case(
                    (Product.product_name.ilike(f"%{search}%"), 3),  # Exact match in name
                    (Product.product_name.ilike(f"%{search}%"), 2),  # Partial match in name
                    (Product.sku.ilike(f"%{search}%"), 2),          # Match in SKU
                    (Category.name.ilike(f"%{search}%"), 1),        # Match in category
                    (Brand.name.ilike(f"%{search}%"), 1),           # Match in brand
                    else_=0
                ).label('relevance')
                
                # Execute paginated query with relevance
                pagination = query.add_columns(relevance).paginate(page=page, per_page=per_page, error_out=False)
                
                # Prepare response
                products = pagination.items
                total = pagination.total
                pages = pagination.pages
                
                # Get product data with media and reviews
                product_data = []
                for product, relevance_score in products:  # Unpack the tuple containing product and relevance score
                    product_dict = product.serialize()
                    
                    # Calculate average rating
                    avg_rating = db.session.query(func.avg(Review.rating))\
                        .filter(Review.product_id == product.product_id)\
                        .scalar() or 0
                    
                    # Get product reviews
                    reviews = Review.query.filter_by(
                        product_id=product.product_id,
                        deleted_at=None
                    ).order_by(Review.created_at.desc()).all()
                    
                    # Add frontend-specific fields
                    product_dict.update({
                        'id': str(product.product_id),  # Convert to string for frontend
                        'name': product.product_name,
                        'description': product.product_description,
                        'stock': 100,  # TODO: Add stock tracking
                        'isNew': True,  # TODO: Add logic for new products
                        'isBuiltIn': False,  # TODO: Add logic for built-in products
                        'rating': round(float(avg_rating), 1),  # Add average rating
                        'discount_pct': float(product.discount_pct),  # Add discount percentage
                        'relevance_score': relevance_score,  # Add relevance score
                        'reviews': [{
                            "id": review.review_id,
                            "user": {
                                "id": review.user.id,
                                "first_name": review.user.first_name if hasattr(review.user, 'first_name') else 'Anonymous',
                                "last_name": review.user.last_name if hasattr(review.user, 'last_name') else '',
                                "email": review.user.email if hasattr(review.user, 'email') else None,
                                "avatar": review.user.avatar_url if hasattr(review.user, 'avatar_url') else None
                            },
                            "rating": review.rating,
                            "title": review.title,
                            "body": review.body,
                            "created_at": review.created_at.isoformat(),
                            "images": [img.serialize() for img in review.images] if review.images else []
                        } for review in reviews]
                    })
                    
                    # Get primary media
                    media = ProductController.get_product_media(product.product_id)
                    if media:
                        product_dict['primary_image'] = media['url']
                        product_dict['image'] = media['url']  # For backward compatibility
                    
                    product_data.append(product_dict)

            else:
                # Execute paginated query without relevance
                pagination = query.paginate(page=page, per_page=per_page, error_out=False)
                
                # Prepare response
                products = pagination.items
                total = pagination.total
                pages = pagination.pages
                
                # Get product data with media and reviews
                product_data = []
                for product in products:
                    product_dict = product.serialize()
                    
                    # Calculate average rating
                    avg_rating = db.session.query(func.avg(Review.rating))\
                        .filter(Review.product_id == product.product_id)\
                        .scalar() or 0
                    
                    # Get product reviews
                    reviews = Review.query.filter_by(
                        product_id=product.product_id,
                        deleted_at=None
                    ).order_by(Review.created_at.desc()).all()
                    
                    # Add frontend-specific fields
                    product_dict.update({
                        'id': str(product.product_id),  # Convert to string for frontend
                        'name': product.product_name,
                        'description': product.product_description,
                        'stock': 100,  # TODO: Add stock tracking
                        'isNew': True,  # TODO: Add logic for new products
                        'isBuiltIn': False,  # TODO: Add logic for built-in products
                        'rating': round(float(avg_rating), 1),  # Add average rating
                        'discount_pct': float(product.discount_pct),  # Add discount percentage
                        'reviews': [{
                            "id": review.review_id,
                            "user": {
                                "id": review.user.id,
                                "first_name": review.user.first_name if hasattr(review.user, 'first_name') else 'Anonymous',
                                "last_name": review.user.last_name if hasattr(review.user, 'last_name') else '',
                                "email": review.user.email if hasattr(review.user, 'email') else None,
                                "avatar": review.user.avatar_url if hasattr(review.user, 'avatar_url') else None
                            },
                            "rating": review.rating,
                            "title": review.title,
                            "body": review.body,
                            "created_at": review.created_at.isoformat(),
                            "images": [img.serialize() for img in review.images] if review.images else []
                        } for review in reviews]
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
            active_flag=True,
            approval_status='approved'  # Only show approved products
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
                if (rv.product and 
                    rv.product.active_flag and 
                    not rv.product.deleted_at and 
                    rv.product.approval_status == 'approved'):  # Only show approved products
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

    @staticmethod
    def get_product_details(product_id):
        """Get detailed product information including media, meta data, and attributes"""
        try:
            # Get base product information - only show approved products
            product = Product.query.filter_by(
                product_id=product_id,
                deleted_at=None,
                active_flag=True,
                approval_status='approved'  # Only show approved products
            ).first_or_404()

            # Get product media
            product_media = ProductMedia.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).order_by(ProductMedia.sort_order).all()

            # Get product meta information
            product_meta = ProductMeta.query.filter_by(
                product_id=product_id
            ).first()

            # Get product attributes with their values
            product_attributes = ProductAttribute.query.filter_by(
                product_id=product_id
            ).all()

            # Process attributes to handle array format from variants
            def process_attributes(attributes):
                processed_attributes = []
                
                for attr in attributes:
                    # Check if the value is in array format (from variants)
                    if attr.value_text and (
                        (attr.value_text.startswith('[') and attr.value_text.endswith(']')) or
                        (attr.value_text.startswith("['") and attr.value_text.endswith("']"))
                    ):
                        try:
                            # First try to parse as JSON
                            values = json.loads(attr.value_text)
                            if isinstance(values, list):
                                # Create individual attributes for each value
                                for index, value in enumerate(values):
                                    processed_attributes.append({
                                        "attribute_id": attr.attribute_id + index,  # Create unique IDs
                                        "attribute_name": attr.attribute.name,
                                        "value_code": attr.value_code,
                                        "value_text": str(value),
                                        "value_label": str(value),
                                        "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                        "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                    })
                            else:
                                # If not a list, treat as regular attribute
                                processed_attributes.append({
                                    "attribute_id": attr.attribute_id,
                                    "attribute_name": attr.attribute.name,
                                    "value_code": attr.value_code,
                                    "value_text": attr.value_text,
                                    "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                    "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                    "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                })
                        except (json.JSONDecodeError, ValueError):
                            # If JSON parsing fails, try to parse as Python list string
                            try:
                                # Remove outer quotes and brackets, then split by comma
                                clean_text = attr.value_text.strip()
                                if clean_text.startswith("['") and clean_text.endswith("']"):
                                    # Handle Python list with single quotes
                                    clean_text = clean_text[2:-2]  # Remove [' and ']
                                    values = [v.strip().strip("'\"") for v in clean_text.split("', '")]
                                elif clean_text.startswith('[') and clean_text.endswith(']'):
                                    # Handle JSON-like array
                                    clean_text = clean_text[1:-1]  # Remove [ and ]
                                    values = [v.strip().strip("'\"") for v in clean_text.split(',')]
                                else:
                                    # Not an array, treat as regular attribute
                                    processed_attributes.append({
                                        "attribute_id": attr.attribute_id,
                                        "attribute_name": attr.attribute.name,
                                        "value_code": attr.value_code,
                                        "value_text": attr.value_text,
                                        "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                        "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                        "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                    })
                                    continue
                                
                                # Create individual attributes for each value
                                for index, value in enumerate(values):
                                    if value:  # Only add non-empty values
                                        processed_attributes.append({
                                            "attribute_id": attr.attribute_id + index,  # Create unique IDs
                                            "attribute_name": attr.attribute.name,
                                            "value_code": attr.value_code,
                                            "value_text": str(value),
                                            "value_label": str(value),
                                            "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                            "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                        })
                            except Exception:
                                # If all parsing fails, treat as regular attribute
                                processed_attributes.append({
                                    "attribute_id": attr.attribute_id,
                                    "attribute_name": attr.attribute.name,
                                    "value_code": attr.value_code,
                                    "value_text": attr.value_text,
                                    "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                    "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                                    "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                                })
                    else:
                        # Regular attribute, no processing needed
                        processed_attributes.append({
                            "attribute_id": attr.attribute_id,
                            "attribute_name": attr.attribute.name,
                            "value_code": attr.value_code,
                            "value_text": attr.value_text,
                            "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                            "is_text_based": attr.value_code is None or attr.value_code.startswith('text_'),
                            "input_type": attr.attribute.input_type.value if attr.attribute.input_type else 'text'
                        })
                
                return processed_attributes

            # Process the attributes
            processed_attributes = process_attributes(product_attributes)

            # Track recently viewed
            try:
                from flask_jwt_extended import get_jwt_identity
                from models.recently_viewed import RecentlyViewed
                from datetime import datetime
                
                user_id = get_jwt_identity()
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
            except Exception as e:
                print(f"Error tracking recently viewed: {str(e)}")
                # Continue with the response even if tracking fails

            # Get variants and parent product information
            variants = []
            parent_product = None

            if product.parent_product_id is None:
                # If this is a parent product, get its variants
                variants = Product.query.filter_by(
                    parent_product_id=product_id,
                    deleted_at=None,
                    active_flag=True,
                    approval_status='approved'
                ).all()
            else:
                # If this is a variant product, get its parent and siblings
                parent_product = Product.query.filter_by(
                    product_id=product.parent_product_id,
                    deleted_at=None,
                    active_flag=True,
                    approval_status='approved'
                ).first()

                # Get all variants (siblings) including the parent
                all_variants = Product.query.filter_by(
                    parent_product_id=product.parent_product_id,
                    deleted_at=None,
                    active_flag=True,
                    approval_status='approved'
                ).all()
                
                # Add parent product to variants list if it exists
                if parent_product:
                    variants.append(parent_product)
                
                # Add sibling variants (excluding current product)
                variants.extend([v for v in all_variants if v.product_id != product_id])

            # Get product reviews
            reviews = Review.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).order_by(Review.created_at.desc()).all()
            
            # Calculate average rating
            avg_rating = db.session.query(func.avg(Review.rating))\
                .filter(Review.product_id == product_id)\
                .scalar() or 0

            # Prepare response data - start with serialized product data
            response_data = product.serialize()
            
            # Add additional detailed information
            response_data.update({
                "media": [media.serialize() for media in product_media] if product_media else [],
                "meta": {
                    "short_desc": product_meta.short_desc if product_meta else None,
                    "full_desc": product_meta.full_desc if product_meta else None,
                    "meta_title": product_meta.meta_title if product_meta else None,
                    "meta_desc": product_meta.meta_desc if product_meta else None,
                    "meta_keywords": product_meta.meta_keywords if product_meta else None
                },
                "attributes": processed_attributes,
                "category": product.category.serialize() if product.category else None,
                "brand": product.brand.serialize() if product.brand else None,
                # Add frontend-specific fields
                "id": str(product.product_id),
                "name": product.product_name,
                "currency": "INR",
                "stock": 100,
                "isNew": True,
                "isBuiltIn": False,
                "rating": round(float(avg_rating), 1),
                "reviews": [{
                    "id": review.review_id,
                    "user": {
                        "id": review.user.id,
                        "first_name": review.user.first_name if hasattr(review.user, 'first_name') else 'Anonymous',
                        "last_name": review.user.last_name if hasattr(review.user, 'last_name') else '',
                        "email": review.user.email if hasattr(review.user, 'email') else None,
                        "avatar": review.user.avatar_url if hasattr(review.user, 'avatar_url') else None
                    },
                    "rating": review.rating,
                    "title": review.title,
                    "body": review.body,
                    "created_at": review.created_at.isoformat(),
                    "images": [img.serialize() for img in review.images] if review.images else []
                } for review in reviews],
                "sku": product.sku if hasattr(product, 'sku') else None,
                "parent_product_id": product.parent_product_id,
                "is_variant": product.parent_product_id is not None,
                "variants": []  # Will be populated below
            })
            
            # Add variants with proper price handling
            for v in variants:
                variant_data = v.serialize()  # Use serialize() to get correct price logic
                variant_dict = {
                    "id": str(v.product_id),
                    "name": v.product_name,
                    "price": variant_data.get('price', v.selling_price),  # Use serialized price
                    "originalPrice": variant_data.get('originalPrice', v.cost_price),  # Use serialized originalPrice
                    "sku": v.sku if hasattr(v, 'sku') else None,
                    "isVariant": v.product_id != product.parent_product_id,
                    "isParent": v.product_id == product.parent_product_id,
                    "parentProductId": str(v.parent_product_id) if v.parent_product_id else None,
                    "media": [media.serialize() for media in ProductMedia.query.filter_by(
                        product_id=v.product_id,
                        deleted_at=None
                    ).order_by(ProductMedia.sort_order).all()] if ProductMedia.query.filter_by(
                        product_id=v.product_id,
                        deleted_at=None
                    ).first() else []
                }
                response_data["variants"].append(variant_dict)

            return jsonify(response_data)

        except Exception as e:
            print(f"Error in get_product_details: {str(e)}")
            return jsonify({
                "error": "Failed to fetch product details",
                "message": str(e)
            }), 500 

    @staticmethod
    def get_products_by_brand(brand_slug):
        """Get products filtered by brand slug"""
        try:
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # Get filter parameters
            category_id = request.args.get('category_id')
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            min_rating = request.args.get('min_rating', type=float)
            min_discount = request.args.get('min_discount', type=float)
            
            # Get brand by slug
            brand = Brand.query.filter_by(
                slug=brand_slug,
                deleted_at=None
            ).first_or_404()
            
            # Base query - only show approved products and parent products
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True),
                Product.approval_status == 'approved',
                Product.brand_id == brand.brand_id,
                Product.parent_product_id.is_(None)  # Only show parent products
            )
            
            # Apply category filter
            if category_id:
                try:
                    category_id = int(category_id)
                    query = query.filter(Product.category_id == category_id)
                except ValueError:
                    print(f"Invalid category_id: {category_id}")
            
            # Apply other filters
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

            # Apply rating filter
            if min_rating is not None:
                query = query.join(Review, Product.product_id == Review.product_id)\
                    .group_by(Product.product_id)\
                    .having(func.avg(Review.rating) >= min_rating)

            # Apply discount filter
            if min_discount is not None:
                query = query.filter(Product.discount_pct >= min_discount)
                
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
                
                # Calculate average rating
                avg_rating = db.session.query(func.avg(Review.rating))\
                    .filter(Review.product_id == product.product_id)\
                    .scalar() or 0
                
                # Add frontend-specific fields
                product_dict.update({
                    'id': str(product.product_id),
                    'name': product.product_name,
                    'description': product.product_description,
                    'stock': 100,
                    'isNew': True,
                    'isBuiltIn': False,
                    'rating': round(float(avg_rating), 1),
                    'discount_pct': float(product.discount_pct),
                })
                
                # Get primary media
                media = ProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']
                
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
                },
                'brand': brand.serialize()
            })
            
        except Exception as e:
            print(f"Error in get_products_by_brand: {str(e)}")
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
    def get_products_by_category(category_id):
        """Get products filtered by category ID"""
        try:
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # Get filter parameters
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            include_children = request.args.get('include_children', 'true').lower() == 'true'
            min_rating = request.args.get('min_rating', type=float)
            min_discount = request.args.get('min_discount', type=float)
            
            # Get category
            category = Category.query.get_or_404(category_id)
            
            # Base query - only show approved products and parent products
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True),
                Product.approval_status == 'approved',
                Product.parent_product_id.is_(None)  # Only show parent products
            )
            
            # Apply category filter with child categories
            if include_children:
                # Get all child category IDs recursively
                def get_child_category_ids(parent_id):
                    child_ids = []
                    children = Category.query.filter_by(parent_id=parent_id).all()
                    for child in children:
                        child_ids.append(child.category_id)
                        child_ids.extend(get_child_category_ids(child.category_id))
                    return child_ids
                
                child_category_ids = get_child_category_ids(category_id)
                category_ids = [category_id] + child_category_ids
                query = query.filter(Product.category_id.in_(category_ids))
            else:
                # Only include products from the selected category
                query = query.filter(Product.category_id == category_id)
            
            # Apply other filters
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

            # Apply rating filter
            if min_rating is not None:
                query = query.join(Review, Product.product_id == Review.product_id)\
                    .group_by(Product.product_id)\
                    .having(func.avg(Review.rating) >= min_rating)

            # Apply discount filter
            if min_discount is not None:
                query = query.filter(Product.discount_pct >= min_discount)
                
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
                
                # Calculate average rating
                avg_rating = db.session.query(func.avg(Review.rating))\
                    .filter(Review.product_id == product.product_id)\
                    .scalar() or 0
                
                # Add frontend-specific fields
                product_dict.update({
                    'id': str(product.product_id),
                    'name': product.product_name,
                    'description': product.product_description,
                    'stock': 100,
                    'isNew': True,
                    'isBuiltIn': False,
                    'rating': round(float(avg_rating), 1),
                    'discount_pct': float(product.discount_pct),
                })
                
                # Get primary media
                media = ProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']
                
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
                },
                'category': category.serialize()
            })
            
        except Exception as e:
            print(f"Error in get_products_by_category: {str(e)}")
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
    def get_product_variants(product_id):
        """Get all variants for a parent product"""
        try:
            # Get the parent product to verify it exists
            parent_product = Product.query.filter_by(
                product_id=product_id,
                deleted_at=None,
                active_flag=True,
                approval_status='approved'
            ).first_or_404()

            # Get all variants for this parent product
            variants = Product.query.filter_by(
                parent_product_id=product_id,
                deleted_at=None,
                active_flag=True,
                approval_status='approved'
            ).all()

            # Prepare response data
            variant_data = []
            for variant in variants:
                variant_dict = variant.serialize()
                # Add frontend-specific fields
                variant_dict.update({
                    'id': str(variant.product_id),
                    'name': variant.product_name,
                    'description': variant.product_description,
                    'stock': 100,  # TODO: Add stock tracking
                    'isNew': True,  # TODO: Add logic for new products
                    'isBuiltIn': False,  # TODO: Add logic for built-in products
                    'isVariant': True,
                    'parentProductId': str(product_id)
                })
                
                # Get primary media
                media = ProductController.get_product_media(variant.product_id)
                if media:
                    variant_dict['primary_image'] = media['url']
                    variant_dict['image'] = media['url']
                
                variant_data.append(variant_dict)

            return jsonify({
                'variants': variant_data,
                'total': len(variant_data)
            })

        except Exception as e:
            print(f"Error in get_product_variants: {str(e)}")
            return jsonify({
                'error': 'Failed to fetch product variants',
                'message': str(e)
            }), 500 

    @staticmethod
    def get_new_products():
        """Get products that were added within the last week (excluding variants)"""
        try:
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            
            # Calculate the date one week ago
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            
            # Base query - only show approved products added within last week and exclude variants
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True),
                Product.approval_status == 'approved',
                Product.created_at >= one_week_ago,
                Product.parent_product_id.is_(None)  # Exclude variants
            )
            
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
                    'id': str(product.product_id),
                    'name': product.product_name,
                    'description': product.product_description,
                    'stock': 100,  # TODO: Add stock tracking
                    'isNew': True,  # These are new products
                    'isBuiltIn': False,
                })
                
                # Get primary media
                media = ProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']
                
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
            print(f"Error in get_new_products: {str(e)}")
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
    def get_trendy_deals():
        """Get products that have been ordered the most (trendy deals)"""
        try:
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # Get filter parameters
            category_id = request.args.get('category_id')
            brand_id = request.args.get('brand_id')
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            include_children = request.args.get('include_children', 'true').lower() == 'true'
            min_rating = request.args.get('min_rating', type=float)
            min_discount = request.args.get('min_discount', type=float)
            
            # Calculate the date one month ago for recent orders
            one_month_ago = datetime.utcnow() - timedelta(days=30)
            
            # Query to get products ordered the most in the last month
            from sqlalchemy import func, desc
            
            # First, get all completed orders from the last month
            recent_orders = db.session.query(Order).filter(
                Order.order_status == 'completed',
                Order.order_date >= one_month_ago
            ).all()
            
            if not recent_orders:
                # If no recent orders, get all completed orders
                recent_orders = db.session.query(Order).filter(
                    Order.order_status == 'completed'
                ).all()
            
            # Get order IDs
            order_ids = [order.order_id for order in recent_orders]
            
            # Get product IDs and their order counts
            product_counts = db.session.query(
                OrderItem.product_id,
                func.sum(OrderItem.quantity).label('total_ordered')
            ).filter(
                OrderItem.order_id.in_(order_ids),
                OrderItem.product_id.isnot(None)
            ).group_by(
                OrderItem.product_id
            ).order_by(
                desc('total_ordered')
            ).all()
            
            print(f"Found {len(product_counts)} products with orders")
            
            # Get the product IDs
            product_ids = [pc[0] for pc in product_counts]
            
            # Base query for products
            query = Product.query.filter(
                Product.deleted_at.is_(None),
                Product.active_flag.is_(True),
                Product.approval_status == 'approved',
                Product.parent_product_id.is_(None)
            )

            # Apply category filter with child categories
            if category_id and category_id != 'all-products':
                try:
                    category_id = int(category_id)
                    if include_children:
                        # Get the category and all its child categories
                        category = Category.query.get(category_id)
                        if category:
                            # Get all child category IDs recursively
                            def get_child_category_ids(parent_id):
                                child_ids = []
                                children = Category.query.filter_by(parent_id=parent_id).all()
                                for child in children:
                                    child_ids.append(child.category_id)
                                    child_ids.extend(get_child_category_ids(child.category_id))
                                return child_ids
                            
                            child_category_ids = get_child_category_ids(category_id)
                            category_ids = [category_id] + child_category_ids
                            query = query.filter(Product.category_id.in_(category_ids))
                    else:
                        # Only include products from the selected category
                        query = query.filter(Product.category_id == category_id)
                except ValueError:
                    print(f"Invalid category_id: {category_id}")
            
            # Apply brand filter
            if brand_id:
                try:
                    # Handle multiple brand IDs
                    if ',' in brand_id:
                        brand_ids = [int(bid) for bid in brand_id.split(',')]
                        query = query.filter(Product.brand_id.in_(brand_ids))
                    else:
                        brand_id = int(brand_id)
                        query = query.filter(Product.brand_id == brand_id)
                except ValueError:
                    print(f"Invalid brand_id: {brand_id}")

            # Apply price range filter
            if min_price is not None:
                query = query.filter(Product.selling_price >= min_price)
            if max_price is not None:
                query = query.filter(Product.selling_price <= max_price)

            # Apply search filter
            if search:
                search_terms = search.lower().split()
                search_conditions = []
                
                for term in search_terms:
                    term = f"%{term}%"
                    search_conditions.extend([
                        Product.product_name.ilike(term),
                        Product.product_description.ilike(term),
                        Product.sku.ilike(term),
                        Category.name.ilike(term),
                        Brand.name.ilike(term)
                    ])
                
                # Join with category and brand tables for searching
                query = query.outerjoin(Category).outerjoin(Brand)
                
                # Apply the search conditions
                query = query.filter(or_(*search_conditions))

            # Apply rating filter
            if min_rating is not None:
                query = query.join(Review, Product.product_id == Review.product_id)\
                    .group_by(Product.product_id)\
                    .having(func.avg(Review.rating) >= min_rating)

            # Apply discount filter
            if min_discount is not None:
                query = query.filter(Product.discount_pct >= min_discount)

            # Filter by trendy products
            if product_ids:
                query = query.filter(Product.product_id.in_(product_ids))
            
            # Get the filtered products
            products = query.all()
            
            # Create a dictionary to store order counts
            order_counts = {pc[0]: pc[1] for pc in product_counts}
            
            # Sort products based on order counts
            products.sort(key=lambda p: order_counts.get(p.product_id, 0), reverse=True)
            
            # Apply pagination
            total = len(products)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_products = products[start_idx:end_idx]
            
            # Prepare response
            product_data = []
            for product in paginated_products:
                product_dict = product.serialize()
                
                # Calculate average rating
                avg_rating = db.session.query(func.avg(Review.rating))\
                    .filter(Review.product_id == product.product_id)\
                    .scalar() or 0
                
                # Add frontend-specific fields
                product_dict.update({
                    'id': str(product.product_id),
                    'name': product.product_name,
                    'description': product.product_description,
                    'stock': 100,
                    'isNew': True,
                    'isBuiltIn': False,
                    'rating': round(float(avg_rating), 1),
                    'discount_pct': float(product.discount_pct),
                    'orderCount': order_counts.get(product.product_id, 0),
                    'category': product.category.serialize() if product.category else None,
                    'brand': product.brand.serialize() if product.brand else None
                })
                
                # Get primary media
                media = ProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                    product_dict['image'] = media['url']
                
                product_data.append(product_dict)
            
            print(f"Returning {len(product_data)} products")
            
            return jsonify({
                'products': product_data,
                'pagination': {
                    'total': total,
                    'pages': (total + per_page - 1) // per_page,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': end_idx < total,
                    'has_prev': page > 1
                }
            })
            
        except Exception as e:
            print(f"Error in get_trendy_deals: {str(e)}")
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