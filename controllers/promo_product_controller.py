from flask import current_app, request
from models.product_placement import ProductPlacement, PlacementTypeEnum
from models.product import Product
from models.product_media import ProductMedia, MediaType
from models.category import Category
from models.brand import Brand
from common.database import db
from datetime import datetime, timezone
from sqlalchemy import desc, and_, or_, func

class PromoProductController:
    @staticmethod
    def get_promo_products():
        """
        Get all promo products with pagination and filters.
        Returns products that are currently active in promo placements and have valid special prices.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 12, type=int), 50)
            
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # Get filter parameters
            category_id = request.args.get('category_id')
            brand_id = request.args.get('brand_id', type=int)
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')
            include_children = request.args.get('include_children', 'true').lower() == 'true'
            
            # Base query to get promo products with their placements and valid special prices
            query = Product.query.join(
                ProductPlacement,
                Product.product_id == ProductPlacement.product_id
            ).filter(
                ProductPlacement.placement_type == PlacementTypeEnum.PROMOTED,
                ProductPlacement.is_active == True,
                (ProductPlacement.expires_at == None) | (ProductPlacement.expires_at > now_utc),
                Product.deleted_at == None,
                Product.active_flag == True,
                Product.approval_status == 'approved',
                Product.special_price != None,
                (Product.special_start <= now_utc.date()) | (Product.special_start == None),
                (Product.special_end >= now_utc.date()) | (Product.special_end == None),
                Product.parent_product_id.is_(None)  # Only show parent products
            )

            # Apply category filter with child categories
            if category_id:
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
                query = query.filter(Product.brand_id == brand_id)

            # Apply price range filter
            if min_price is not None:
                query = query.filter(Product.special_price >= min_price)
            if max_price is not None:
                query = query.filter(Product.special_price <= max_price)

            # Apply search filter
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

            # Serialize products with their placement details and media
            serialized_products = []
            for product in products:
                product_data = product.serialize()
                
                # Get the placement details for this product
                placement = ProductPlacement.query.filter_by(
                    product_id=product.product_id,
                    placement_type=PlacementTypeEnum.PROMOTED,
                    is_active=True
                ).first()
                
                if placement:
                    product_data['placement'] = {
                        'placement_id': placement.placement_id,
                        'sort_order': placement.sort_order,
                        'added_at': placement.added_at.isoformat() if placement.added_at else None,
                        'expires_at': placement.expires_at.isoformat() if placement.expires_at else None
                    }
                
                # Get product media
                media = ProductMedia.query.filter_by(
                    product_id=product.product_id,
                    deleted_at=None
                ).order_by(
                    ProductMedia.sort_order.asc()
                ).all()
                
                # Add media URLs to product data
                product_data['images'] = [
                    m.url for m in media 
                    if m.type == MediaType.IMAGE
                ]
                
                # Add frontend-specific fields
                product_data.update({
                    'id': str(product.product_id),
                    'name': product.product_name,
                    'description': product.product_description,
                    'price': float(product.special_price),
                    'originalPrice': float(product.selling_price),
                    'stock': 100,  # TODO: Add stock tracking
                    'isNew': True,  # TODO: Add logic for new products
                    'isBuiltIn': False,
                })
                
                serialized_products.append(product_data)

            return {
                'products': serialized_products,
                'pagination': {
                    'total': total,
                    'pages': pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }

        except Exception as e:
            current_app.logger.error(f"Error getting promo products: {str(e)}")
            raise RuntimeError("Failed to retrieve promo products") from e

    @staticmethod
    def get_promo_product_details(product_id):
        """
        Get detailed information about a specific promo product.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            
            # Query to get the product with its promo placement
            product = Product.query.join(
                ProductPlacement,
                Product.product_id == ProductPlacement.product_id
            ).filter(
                Product.product_id == product_id,
                ProductPlacement.placement_type == PlacementTypeEnum.PROMOTED,
                ProductPlacement.is_active == True,
                (ProductPlacement.expires_at == None) | (ProductPlacement.expires_at > now_utc),
                Product.deleted_at == None,
                Product.active_flag == True,
                Product.approval_status == 'approved',
                Product.special_price != None,
                (Product.special_start <= now_utc.date()) | (Product.special_start == None),
                (Product.special_end >= now_utc.date()) | (Product.special_end == None)
            ).first()

            if not product:
                raise ValueError(f"Promo product with ID {product_id} not found or not active")

            # Get the placement details
            placement = ProductPlacement.query.filter_by(
                product_id=product_id,
                placement_type=PlacementTypeEnum.PROMOTED,
                is_active=True
            ).first()

            product_data = product.serialize()
            if placement:
                product_data['placement'] = {
                    'placement_id': placement.placement_id,
                    'sort_order': placement.sort_order,
                    'added_at': placement.added_at.isoformat() if placement.added_at else None,
                    'expires_at': placement.expires_at.isoformat() if placement.expires_at else None
                }

            # Get product media
            media = ProductMedia.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).order_by(
                ProductMedia.sort_order.asc()
            ).all()
            
            # Add media URLs to product data
            product_data['images'] = [
                m.url for m in media 
                if m.type == MediaType.IMAGE
            ]

            # Add frontend-specific fields
            product_data.update({
                'id': str(product.product_id),
                'name': product.product_name,
                'description': product.product_description,
                'price': float(product.special_price),
                'originalPrice': float(product.selling_price),
                'stock': 100,  # TODO: Add stock tracking
                'isNew': True,  # TODO: Add logic for new products
                'isBuiltIn': False,
            })

            return product_data

        except ValueError as e:
            raise e
        except Exception as e:
            current_app.logger.error(f"Error getting promo product details: {str(e)}")
            raise RuntimeError("Failed to retrieve promo product details") from e 