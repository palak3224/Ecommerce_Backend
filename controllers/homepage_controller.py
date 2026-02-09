from models.homepage import HomepageCategory
from models.product import Product
from models.category import Category
from models.product_media import ProductMedia
from models.enums import MediaType
from common.database import db
from flask import jsonify
import logging
from models.carousel import Carousel
from sqlalchemy import or_

class HomepageController:
    @staticmethod
    def get_homepage_products():
        """Get products from categories that are selected for homepage display (excluding variants)"""
        try:
            # Get active homepage categories ordered by display_order
            active_homepage_categories = HomepageCategory.query.filter_by(
                is_active=True
            ).order_by(HomepageCategory.display_order).all()
            
            # Get category IDs that are active on homepage
            active_category_ids = [hc.category_id for hc in active_homepage_categories]
            
            # Get all main categories that are active on homepage and category is_active
            main_categories = Category.query.filter(
                Category.category_id.in_(active_category_ids),
                Category.parent_id.is_(None),
                Category.is_active == True
            ).all()
            
            # Initialize response data
            response_data = []
            
            # Get all product media in one query
            all_media = ProductMedia.query.filter(
                ProductMedia.type == MediaType.IMAGE,
                ProductMedia.deleted_at == None
            ).all()
            
            # Create a dictionary to map product IDs to their media
            media_dict = {}
            for media in all_media:
                if media.product_id not in media_dict:
                    media_dict[media.product_id] = []
                media_dict[media.product_id].append(media)
            
            # Function to serialize product with media
            def serialize_product_with_media(product):
                product_data = product.serialize()
                product_data['media'] = [
                    {
                        'media_id': media.media_id,
                        'type': media.type.value,
                        'url': media.url,
                        'sort_order': media.sort_order,
                        'public_id': media.public_id
                    }
                    for media in sorted(media_dict.get(product.product_id, []), key=lambda x: x.sort_order)
                ]
                return product_data
            
            def get_category_products(category_id, level=0):
                """Recursively get all products from a category and its subcategories (excluding variants)"""
                # Get direct products in this category that are approved and not variants
                direct_products = Product.query.filter(
                    Product.category_id == category_id,
                    Product.active_flag == True,
                    Product.deleted_at == None,
                    Product.approval_status == 'approved',  # Only get approved products
                    Product.parent_product_id.is_(None)  # Exclude variants
                ).all()
                
                # Get all active subcategories
                subcategories = Category.query.filter(
                    Category.parent_id == category_id,
                    Category.is_active == True
                ).all()
                
                # Get products from all subcategories recursively
                subcategory_products = []
                for subcategory in subcategories:
                    subcategory_products.extend(get_category_products(subcategory.category_id, level + 1))
                
                # Combine direct products with subcategory products
                return direct_products + subcategory_products
            
            # Process each main category
            for main_category in main_categories:
                # Get active subcategories
                subcategories = Category.query.filter(
                    Category.parent_id == main_category.category_id,
                    Category.is_active == True
                ).all()
                
                # Get products for main category (excluding products in subcategories and variants)
                main_category_products = Product.query.filter(
                    Product.category_id == main_category.category_id,
                    Product.active_flag == True,
                    Product.deleted_at == None,
                    Product.approval_status == 'approved',  # Only get approved products
                    Product.parent_product_id.is_(None),  # Exclude variants
                    ~Product.product_id.in_(
                        db.session.query(Product.product_id)
                        .join(Category, Product.category_id == Category.category_id)
                        .filter(Category.parent_id == main_category.category_id)
                    )
                ).all()
                
                # Get products for each subcategory
                subcategory_data = []
                for subcategory in subcategories:
                    # Get all products from this subcategory and its children recursively
                    all_subcategory_products = get_category_products(subcategory.category_id)
                    
                    # Only add subcategory if it has products
                    if all_subcategory_products:
                        subcategory_data.append({
                            'category': subcategory.serialize(),
                            'products': [serialize_product_with_media(p) for p in all_subcategory_products]
                        })
                
                # Only add main category if it has products or subcategories with products
                if main_category_products or subcategory_data:
                    response_data.append({
                        'category': main_category.serialize(),
                        'products': [serialize_product_with_media(p) for p in main_category_products],
                        'subcategories': subcategory_data
                    })
            
            return jsonify({
                'status': 'success',
                'message': 'Homepage products retrieved successfully',
                'data': response_data
            }), 200
            
        except Exception as e:
            logging.error(f"Error in get_homepage_products: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to retrieve homepage products',
                'error': str(e)
            }), 500

    @staticmethod
    def get_homepage_carousels(carousel_types=None, orientation=None):
        """
        Get all active carousel items for homepage (optionally filter by types and orientation).
        Args:
            carousel_types (list): List of types to filter by ('brand', 'promo', 'new', 'featured')
            orientation (str): Filter by 'horizontal' or 'vertical'
        Returns:
            list: List of carousel items (dicts)
        """
        try:
            query = Carousel.query.filter_by(is_active=True, deleted_at=None)
            
            # Filter by orientation if provided
            if orientation:
                # Safely get orientation, default to 'horizontal' if column doesn't exist
                try:
                    query = query.filter_by(orientation=orientation)
                except Exception as e:
                    logging.warning(f"Could not filter by orientation (column may not exist): {str(e)}")
                    # If orientation column doesn't exist, only return horizontal by default
                    if orientation == 'horizontal':
                        pass  # Return all (backward compatibility)
                    else:
                        return []  # Return empty for vertical if column doesn't exist
            
            if carousel_types:
                # Create a list of conditions for each type
                type_conditions = [Carousel.type == type_name for type_name in carousel_types]
                # Combine conditions with OR
                query = query.filter(or_(*type_conditions))
            
            items = query.order_by(Carousel.display_order).all()
            
            # Serialize items with error handling for each item
            result = []
            for item in items:
                try:
                    serialized = item.serialize()
                    result.append(serialized)
                except Exception as serialize_error:
                    logging.error(f"Error serializing carousel item {item.id}: {str(serialize_error)}", exc_info=True)
                    # Try to create a basic serialization without orientation
                    try:
                        basic_serialized = {
                            'id': item.id,
                            'type': item.type,
                            'image_url': item.image_url,
                            'target_id': item.target_id,
                            'display_order': item.display_order,
                            'is_active': item.is_active,
                            'shareable_link': item.shareable_link,
                            'orientation': getattr(item, 'orientation', 'horizontal'),  # Default if column doesn't exist
                            'created_at': item.created_at.isoformat() if item.created_at else None,
                            'updated_at': item.updated_at.isoformat() if item.updated_at else None
                        }
                        result.append(basic_serialized)
                    except Exception as basic_error:
                        logging.error(f"Error in basic serialization for carousel {item.id}: {str(basic_error)}", exc_info=True)
                        # Skip this item if even basic serialization fails
                        continue
            
            return result
        except Exception as e:
            logging.error(f"Error in get_homepage_carousels: {str(e)}", exc_info=True)
            return [] 