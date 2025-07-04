from flask import current_app
from models.product_placement import ProductPlacement, PlacementTypeEnum
from models.product import Product
from models.product_media import ProductMedia, MediaType
from common.database import db
from datetime import datetime, timezone
from sqlalchemy import desc, and_, or_

class FeatureProductController:
    @staticmethod
    def get_featured_products(page=1, per_page=12, category_id=None, brand_id=None, min_price=None, max_price=None, search=None):
        """
        Get all featured products with pagination and filters.
        Returns products that are currently active in featured placements.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            
            # Base query to get featured products with their placements
            query = Product.query.join(
                ProductPlacement,
                Product.product_id == ProductPlacement.product_id
            ).filter(
                ProductPlacement.placement_type == PlacementTypeEnum.FEATURED,
                ProductPlacement.is_active == True,
                (ProductPlacement.expires_at == None) | (ProductPlacement.expires_at > now_utc),
                Product.deleted_at == None,
                Product.active_flag == True,
                Product.approval_status == 'approved'
            )

            # Apply category filter
            if category_id:
                query = query.filter(Product.category_id == category_id)

            # Apply brand filter
            if brand_id:
                query = query.filter(Product.brand_id == brand_id)

            # Apply price range filter (use special_price if available, otherwise selling_price)
            if min_price is not None:
                query = query.filter(
                    or_(
                        and_(Product.special_price != None, Product.special_price >= min_price),
                        and_(Product.special_price == None, Product.selling_price >= min_price)
                    )
                )
            if max_price is not None:
                query = query.filter(
                    or_(
                        and_(Product.special_price != None, Product.special_price <= max_price),
                        and_(Product.special_price == None, Product.selling_price <= max_price)
                    )
                )

            # Apply search filter
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Product.product_name.ilike(search_term),
                        Product.product_description.ilike(search_term)
                    )
                )

            # Order by placement sort order and added date
            query = query.order_by(
                ProductPlacement.sort_order.asc(),
                ProductPlacement.added_at.desc()
            )

            # Get total count for pagination
            total = query.count()

            # Apply pagination
            products = query.offset((page - 1) * per_page).limit(per_page).all()

            # Serialize products with their placement details and media
            serialized_products = []
            for product in products:
                product_data = product.serialize()
                
                # Get the placement details for this product
                placement = ProductPlacement.query.filter_by(
                    product_id=product.product_id,
                    placement_type=PlacementTypeEnum.FEATURED,
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

                # Calculate price and originalPrice for frontend compatibility
                selling_price = getattr(product, 'selling_price', 0)
                special_price = getattr(product, 'special_price', None)
                discount_pct = getattr(product, 'discount_pct', None)

                # Use special_price as current price if available, otherwise selling_price
                current_price = special_price if special_price is not None else selling_price
                
                # Calculate originalPrice for discount calculation
                if special_price is not None and selling_price > special_price:
                    # If we have a special price, the original price is the selling price
                    original_price = selling_price
                elif discount_pct and discount_pct > 0 and current_price:
                    # If we have a discount percentage, calculate original price
                    original_price = current_price / (1 - (discount_pct / 100))
                else:
                    # No discount, original price is same as current price
                    original_price = current_price

                # Update product data with calculated values
                product_data['price'] = current_price
                product_data['originalPrice'] = original_price
                product_data['selling_price'] = selling_price
                product_data['special_price'] = special_price
                product_data['discount_pct'] = discount_pct
                
                serialized_products.append(product_data)

            return {
                'products': serialized_products,
                'pagination': {
                    'total': total,
                    'pages': (total + per_page - 1) // per_page,
                    'current_page': page,
                    'per_page': per_page
                }
            }

        except Exception as e:
            current_app.logger.error(f"Error getting featured products: {str(e)}")
            raise RuntimeError("Failed to retrieve featured products") from e

    @staticmethod
    def get_featured_product_details(product_id):
        """
        Get detailed information about a specific featured product.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            
            # Query to get the product with its featured placement
            product = Product.query.join(
                ProductPlacement,
                Product.product_id == ProductPlacement.product_id
            ).filter(
                Product.product_id == product_id,
                ProductPlacement.placement_type == PlacementTypeEnum.FEATURED,
                ProductPlacement.is_active == True,
                (ProductPlacement.expires_at == None) | (ProductPlacement.expires_at > now_utc),
                Product.deleted_at == None,
                Product.active_flag == True,
                Product.approval_status == 'approved'
            ).first()

            if not product:
                raise ValueError(f"Featured product with ID {product_id} not found or not active")

            # Get the placement details
            placement = ProductPlacement.query.filter_by(
                product_id=product_id,
                placement_type=PlacementTypeEnum.FEATURED,
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

            # Calculate price and originalPrice for frontend compatibility
            selling_price = getattr(product, 'selling_price', 0)
            special_price = getattr(product, 'special_price', None)
            discount_pct = getattr(product, 'discount_pct', None)

            # Use special_price as current price if available, otherwise selling_price
            current_price = special_price if special_price is not None else selling_price
            
            # Calculate originalPrice for discount calculation
            if special_price is not None and selling_price > special_price:
                # If we have a special price, the original price is the selling price
                original_price = selling_price
            elif discount_pct and discount_pct > 0 and current_price:
                # If we have a discount percentage, calculate original price
                original_price = current_price / (1 - (discount_pct / 100))
            else:
                # No discount, original price is same as current price
                original_price = current_price

            # Update product data with calculated values
            product_data['price'] = current_price
            product_data['originalPrice'] = original_price
            product_data['selling_price'] = selling_price
            product_data['special_price'] = special_price
            product_data['discount_pct'] = discount_pct

            return product_data

        except ValueError as e:
            raise e
        except Exception as e:
            current_app.logger.error(f"Error getting featured product details: {str(e)}")
            raise RuntimeError("Failed to retrieve featured product details") from e 