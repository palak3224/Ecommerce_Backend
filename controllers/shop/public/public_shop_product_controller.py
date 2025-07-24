from flask import request, jsonify
from common.database import db
from models.shop.shop_product import ShopProduct
from models.shop.shop_category import ShopCategory
from models.shop.shop_brand import ShopBrand
from models.shop.shop import Shop
from models.shop.shop_product_media import ShopProductMedia
from models.shop.shop_product_attribute import ShopProductAttribute
from models.shop.shop_product_stock import ShopProductStock
from models.enums import MediaType
from sqlalchemy import desc, or_, func, and_
from datetime import datetime, timezone

class PublicShopProductController:
    @staticmethod
    def get_product_media(product_id):
        """Get primary media for a shop product"""
        primary_media = ShopProductMedia.query.filter_by(
            product_id=product_id,
            deleted_at=None,
            type=MediaType.IMAGE
        ).order_by(
            ShopProductMedia.sort_order
        ).first()

        return primary_media.serialize() if primary_media else None

    @staticmethod
    def get_products_by_shop(shop_id):
        """Get all published products for a specific shop with pagination and filtering"""
        try:
            # Verify shop exists and is active
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            # Get query parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 20, type=int), 50)
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            category_id = request.args.get('category_id', type=int)
            brand_id = request.args.get('brand_id', type=int)
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '').strip()

            # Build base query for shop products
            query = ShopProduct.query.filter(
                ShopProduct.shop_id == shop_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)  # Only show published products
            )

            # Apply filters
            if category_id:
                query = query.filter(ShopProduct.category_id == category_id)
            
            if brand_id:
                query = query.filter(ShopProduct.brand_id == brand_id)

            # Price filtering based on current selling price or special price
            if min_price is not None:
                query = query.filter(
                    or_(
                        and_(
                            ShopProduct.special_price.is_(None),
                            ShopProduct.selling_price >= min_price
                        ),
                        and_(
                            ShopProduct.special_price.isnot(None),
                            ShopProduct.special_start <= datetime.now(timezone.utc).date(),
                            ShopProduct.special_end >= datetime.now(timezone.utc).date(),
                            ShopProduct.special_price >= min_price
                        ),
                        and_(
                            ShopProduct.special_price.isnot(None),
                            or_(
                                ShopProduct.special_start > datetime.now(timezone.utc).date(),
                                ShopProduct.special_end < datetime.now(timezone.utc).date()
                            ),
                            ShopProduct.selling_price >= min_price
                        )
                    )
                )

            if max_price is not None:
                query = query.filter(
                    or_(
                        and_(
                            ShopProduct.special_price.is_(None),
                            ShopProduct.selling_price <= max_price
                        ),
                        and_(
                            ShopProduct.special_price.isnot(None),
                            ShopProduct.special_start <= datetime.now(timezone.utc).date(),
                            ShopProduct.special_end >= datetime.now(timezone.utc).date(),
                            ShopProduct.special_price <= max_price
                        ),
                        and_(
                            ShopProduct.special_price.isnot(None),
                            or_(
                                ShopProduct.special_start > datetime.now(timezone.utc).date(),
                                ShopProduct.special_end < datetime.now(timezone.utc).date()
                            ),
                            ShopProduct.selling_price <= max_price
                        )
                    )
                )

            # Search functionality
            if search:
                search_term = f"%{search}%"
                query = query.join(ShopCategory, ShopProduct.category_id == ShopCategory.category_id)\
                            .join(ShopBrand, ShopProduct.brand_id == ShopBrand.brand_id, isouter=True)\
                            .filter(
                                or_(
                                    ShopProduct.product_name.ilike(search_term),
                                    ShopProduct.product_description.ilike(search_term),
                                    ShopProduct.sku.ilike(search_term),
                                    ShopCategory.name.ilike(search_term),
                                    ShopBrand.name.ilike(search_term)
                                )
                            )

            # Sorting
            valid_sort_fields = ['created_at', 'product_name', 'selling_price', 'special_price']
            if sort_by in valid_sort_fields and hasattr(ShopProduct, sort_by):
                if order == 'asc':
                    query = query.order_by(getattr(ShopProduct, sort_by))
                else:
                    query = query.order_by(desc(getattr(ShopProduct, sort_by)))
            else:
                query = query.order_by(desc(ShopProduct.created_at))

            # Execute pagination
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            products = pagination.items
            product_data = []

            for product in products:
                product_dict = product.serialize()
                
                # Get primary image
                media = PublicShopProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                
                # Get stock information
                stock = ShopProductStock.query.filter_by(
                    product_id=product.product_id
                ).first()
                
                if stock:
                    product_dict['stock'] = stock.serialize()
                    product_dict['is_in_stock'] = stock.stock_qty > 0
                else:
                    product_dict['is_in_stock'] = False
                
                product_data.append(product_dict)

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'products': product_data,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total_pages': pagination.pages,
                    'total_items': pagination.total,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                },
                'filters_applied': {
                    'category_id': category_id,
                    'brand_id': brand_id,
                    'min_price': min_price,
                    'max_price': max_price,
                    'search': search,
                    'sort_by': sort_by,
                    'order': order
                }
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching products: {str(e)}'
            }), 500

    @staticmethod
    def get_product_by_id(shop_id, product_id):
        """Get a specific product from a shop"""
        try:
            # Verify shop exists and is active
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            # Get the product
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.shop_id == shop_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)
            ).first()

            if not product:
                return jsonify({
                    'success': False,
                    'message': 'Product not found in this shop'
                }), 404

            # Get product details
            product_dict = product.serialize()
            
            # Get all media
            media_list = ShopProductMedia.query.filter_by(
                product_id=product.product_id,
                deleted_at=None
            ).order_by(ShopProductMedia.sort_order).all()
            
            product_dict['media'] = [media.serialize() for media in media_list]
            
            # Get stock information
            stock = ShopProductStock.query.filter_by(
                product_id=product.product_id
            ).first()
            
            if stock:
                product_dict['stock'] = stock.serialize()
                product_dict['is_in_stock'] = stock.stock_qty > 0
            else:
                product_dict['is_in_stock'] = False

            # Get related products (same category, different product)
            related_products = ShopProduct.query.filter(
                ShopProduct.shop_id == shop_id,
                ShopProduct.category_id == product.category_id,
                ShopProduct.product_id != product_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)
            ).limit(4).all()

            related_data = []
            for related in related_products:
                related_dict = related.serialize()
                media = PublicShopProductController.get_product_media(related.product_id)
                if media:
                    related_dict['primary_image'] = media['url']
                related_data.append(related_dict)

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'product': product_dict,
                'related_products': related_data
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching product: {str(e)}'
            }), 500

    @staticmethod
    def get_featured_products(shop_id, limit=8):
        """Get featured/new products for a shop"""
        try:
            # Verify shop exists and is active
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            limit = min(limit, 20)  # Max 20 featured products

            # Get latest published products
            products = ShopProduct.query.filter(
                ShopProduct.shop_id == shop_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)
            ).order_by(desc(ShopProduct.created_at)).limit(limit).all()

            product_data = []
            for product in products:
                product_dict = product.serialize()
                
                # Get primary image
                media = PublicShopProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                
                product_data.append(product_dict)

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'featured_products': product_data,
                'total': len(product_data)
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching featured products: {str(e)}'
            }), 500
