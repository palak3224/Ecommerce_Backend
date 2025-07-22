
from flask import request, jsonify
from common.database import db
from models.shop.shop_product import ShopProduct
from models.shop.shop_category import ShopCategory
from models.shop.shop_brand import ShopBrand
from models.shop.shop import Shop
from models.shop.shop_product_media import ShopProductMedia
from models.enums import MediaType
from sqlalchemy import desc, or_, func
from common.decorators import superadmin_required
from datetime import datetime, timezone

class ShopProductController:
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
    def get_all_products():
        """Get all shop products with pagination and filtering"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 10, type=int), 50)
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            shop_id = request.args.get('shop_id')
            category_id = request.args.get('category_id')
            brand_id = request.args.get('brand_id')
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            search = request.args.get('search', '')

            query = ShopProduct.query.filter(
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True)
            )

            if shop_id:
                query = query.filter(ShopProduct.shop_id == shop_id)

            if category_id:
                query = query.filter(ShopProduct.category_id == category_id)
            
            if brand_id:
                query = query.filter(ShopProduct.brand_id == brand_id)

            if min_price is not None:
                query = query.filter(ShopProduct.selling_price >= min_price)
            if max_price is not None:
                query = query.filter(ShopProduct.selling_price <= max_price)

            if search:
                search_term = f"%{search}%"
                query = query.join(ShopCategory).join(ShopBrand, isouter=True).filter(
                    or_(
                        ShopProduct.product_name.ilike(search_term),
                        ShopProduct.product_description.ilike(search_term),
                        ShopProduct.sku.ilike(search_term),
                        ShopCategory.name.ilike(search_term),
                        ShopBrand.name.ilike(search_term)
                    )
                )

            if sort_by and hasattr(ShopProduct, sort_by):
                if order == 'asc':
                    query = query.order_by(getattr(ShopProduct, sort_by))
                else:
                    query = query.order_by(desc(getattr(ShopProduct, sort_by)))

            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            products = pagination.items
            product_data = []
            for product in products:
                product_dict = product.serialize()
                media = ShopProductController.get_product_media(product.product_id)
                if media:
                    product_dict['primary_image'] = media['url']
                product_data.append(product_dict)

            return jsonify({
                'products': product_data,
                'pagination': {
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_product(product_id):
        """Get a single shop product by ID"""
        product = ShopProduct.query.filter_by(
            product_id=product_id,
            deleted_at=None,
            active_flag=True
        ).first_or_404()
        
        product_dict = product.serialize()
        media = ShopProductController.get_product_media(product_id)
        if media:
            product_dict['primary_image'] = media['url']
        
        return jsonify(product_dict)

    @staticmethod
    @superadmin_required
    def create_product():
        """Create a new shop product"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['shop_id', 'category_id', 'product_name', 'sku', 'cost_price', 'selling_price']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({
                        'status': 'error',
                        'message': f'{field} is required'
                    }), 400
            
            # Verify shop exists
            shop = Shop.query.filter(
                Shop.shop_id == data['shop_id'],
                Shop.deleted_at.is_(None)
            ).first()
            
            if not shop:
                return jsonify({
                    'status': 'error',
                    'message': 'Shop not found'
                }), 404
            
            # Verify category exists and belongs to the shop
            category = ShopCategory.query.filter(
                ShopCategory.category_id == data['category_id'],
                ShopCategory.shop_id == data['shop_id'],
                ShopCategory.deleted_at.is_(None)
            ).first()
            
            if not category:
                return jsonify({
                    'status': 'error',
                    'message': 'Category not found in this shop'
                }), 404
            
            # Verify brand if provided
            if data.get('brand_id'):
                brand = ShopBrand.query.filter(
                    ShopBrand.brand_id == data['brand_id'],
                    ShopBrand.shop_id == data['shop_id'],
                    ShopBrand.category_id == data['category_id'],
                    ShopBrand.deleted_at.is_(None)
                ).first()
                
                if not brand:
                    return jsonify({
                        'status': 'error',
                        'message': 'Brand not found in this shop-category'
                    }), 404
            
            # Check if SKU already exists
            existing_product = ShopProduct.query.filter(
                ShopProduct.sku == data['sku'],
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if existing_product:
                return jsonify({
                    'status': 'error',
                    'message': 'SKU already exists'
                }), 400
            
            new_product = ShopProduct(
                shop_id=data['shop_id'],
                product_name=data['product_name'],
                product_description=data.get('product_description', ''),
                sku=data['sku'],
                category_id=data['category_id'],
                brand_id=data.get('brand_id'),
                cost_price=data['cost_price'],
                selling_price=data['selling_price'],
                special_price=data.get('special_price'),
                special_start=data.get('special_start'),
                special_end=data.get('special_end'),
                is_published=data.get('is_published', False),
                active_flag=data.get('active_flag', True)
            )
            
            db.session.add(new_product)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product created successfully',
                'data': new_product.serialize()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error creating product: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def update_product(product_id):
        """Update an existing shop product"""
        try:
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            data = request.get_json()
            
            # Validate category change if provided
            if 'category_id' in data and data['category_id'] != product.category_id:
                category = ShopCategory.query.filter(
                    ShopCategory.category_id == data['category_id'],
                    ShopCategory.shop_id == product.shop_id,
                    ShopCategory.deleted_at.is_(None)
                ).first()
                
                if not category:
                    return jsonify({
                        'status': 'error',
                        'message': 'Category not found in this shop'
                    }), 404
            
            # Validate brand change if provided
            if 'brand_id' in data and data['brand_id'] != product.brand_id:
                if data['brand_id']:  # Allow setting to None
                    category_id = data.get('category_id', product.category_id)
                    brand = ShopBrand.query.filter(
                        ShopBrand.brand_id == data['brand_id'],
                        ShopBrand.shop_id == product.shop_id,
                        ShopBrand.category_id == category_id,
                        ShopBrand.deleted_at.is_(None)
                    ).first()
                    
                    if not brand:
                        return jsonify({
                            'status': 'error',
                            'message': 'Brand not found in this shop-category'
                        }), 404
            
            # Check SKU uniqueness if changing
            if 'sku' in data and data['sku'] != product.sku:
                existing_product = ShopProduct.query.filter(
                    ShopProduct.sku == data['sku'],
                    ShopProduct.product_id != product_id,
                    ShopProduct.deleted_at.is_(None)
                ).first()
                
                if existing_product:
                    return jsonify({
                        'status': 'error',
                        'message': 'SKU already exists'
                    }), 400
            
            # Update product fields
            if 'product_name' in data:
                product.product_name = data['product_name']
            if 'product_description' in data:
                product.product_description = data['product_description']
            if 'sku' in data:
                product.sku = data['sku']
            if 'category_id' in data:
                product.category_id = data['category_id']
            if 'brand_id' in data:
                product.brand_id = data['brand_id']
            if 'cost_price' in data:
                product.cost_price = data['cost_price']
            if 'selling_price' in data:
                product.selling_price = data['selling_price']
            if 'special_price' in data:
                product.special_price = data['special_price']
            if 'special_start' in data:
                product.special_start = data['special_start']
            if 'special_end' in data:
                product.special_end = data['special_end']
            if 'is_published' in data:
                product.is_published = data['is_published']
            if 'active_flag' in data:
                product.active_flag = data['active_flag']
                
            product.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product updated successfully',
                'data': product.serialize()
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error updating product: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def delete_product(product_id):
        """Soft delete a shop product"""
        try:
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            product.deleted_at = datetime.now(timezone.utc)
            product.active_flag = False
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product deleted successfully'
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error deleting product: {str(e)}'
            }), 500
