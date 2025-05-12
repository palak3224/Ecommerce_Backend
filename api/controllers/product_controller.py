from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.catalog.product import Product
from models.catalog.attributes import Attribute, Size
from models.catalog.product_auxiliary import ProductAttribute, ProductImage, ProductVideo
from models.catalog.product_variant import ProductVariant
from auth.models.models import User, UserRole, MerchantProfile
from common.database import db
from datetime import datetime
import uuid

class ProductController:
    @staticmethod
    @jwt_required()
    def create_product():
        """Create a new product for the authenticated merchant."""
        try:
            merchant_id = get_jwt_identity()
            merchant = MerchantProfile.query.get(merchant_id)
            
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), 404

            # Verify user is a merchant
            user = User.query.get(merchant.user_id)
            if not user or user.role != UserRole.MERCHANT:
                return jsonify({'error': 'Unauthorized. Only merchants can create products'}), 403

            data = request.get_json()
            
            # Generate unique SKU and URL key
            sku = f"{merchant.business_name[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"
            url_key = f"{data['product_name'].lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
            
            # Create new product
            product = Product(
                id=merchant_id,
                category_id=data['category_id'],
                sub_category_id=data.get('sub_category_id'),
                product_name=data['product_name'],
                sku=sku,
                url_key=url_key,
                tax_category=data.get('tax_category'),
                brand_id=data.get('brand_id'),
                short_description=data.get('short_description'),
                full_description=data.get('full_description'),
                meta_title=data.get('meta_title'),
                meta_description=data.get('meta_description'),
                meta_keywords=data.get('meta_keywords'),
                price=data['price'],
                cost_price=data.get('cost_price'),
                special_price=data.get('special_price'),
                special_price_from=datetime.strptime(data['special_price_from'], '%Y-%m-%d').date() if data.get('special_price_from') else None,
                special_price_to=datetime.strptime(data['special_price_to'], '%Y-%m-%d').date() if data.get('special_price_to') else None,
                manage_stock=data.get('manage_stock', True),
                stock_quantity=data.get('stock_quantity'),
                low_stock_threshold=data.get('low_stock_threshold'),
                dimensions_length=data.get('dimensions_length'),
                dimensions_width=data.get('dimensions_width'),
                dimensions_height=data.get('dimensions_height'),
                weight=data.get('weight')
            )
            
            db.session.add(product)
            db.session.flush()  # Get the product_id without committing
            
            # Handle attributes
            if 'attributes' in data:
                for attr_data in data['attributes']:
                    # Verify attribute exists and belongs to the correct category
                    attribute = Attribute.get_by_id(attr_data['attribute_id'])
                    if not attribute:
                        continue
                        
                    if attribute.is_category_specific and attribute.category_id != product.category_id:
                        continue
                        
                    product_attr = ProductAttribute(
                        product_id=product.product_id,
                        attribute_id=attr_data['attribute_id'],
                        value=attr_data['value']
                    )
                    db.session.add(product_attr)
            
            # Handle variants
            if 'variants' in data:
                for variant_data in data['variants']:
                    # Verify size exists if provided
                    size_id = variant_data.get('size_id')
                    if size_id:
                        size = Size.get_by_id(size_id)
                        if not size or (size.category_id and size.category_id != product.category_id):
                            continue
                    
                    variant = ProductVariant(
                        product_id=product.product_id,
                        size_id=size_id,
                        sku=variant_data.get('sku'),
                        price=variant_data.get('price'),
                        stock_quantity=variant_data.get('stock_quantity'),
                        attributes=variant_data.get('attributes', {})
                    )
                    db.session.add(variant)
            
            # Handle images
            if 'images' in data:
                for image_data in data['images']:
                    image = ProductImage(
                        product_id=product.product_id,
                        image_url=image_data['url'],
                        is_main=image_data.get('is_main', False)
                    )
                    db.session.add(image)
            
            # Handle videos
            if 'videos' in data:
                for video_data in data['videos']:
                    video = ProductVideo(
                        product_id=product.product_id,
                        video_url=video_data['url']
                    )
                    db.session.add(video)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Product created successfully',
                'product_id': product.product_id,
                'sku': sku,
                'url_key': url_key
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def get_product(product_id):
        """Get product details by ID."""
        try:
            merchant_id = get_jwt_identity()
            product = Product.query.filter_by(product_id=product_id, id=merchant_id).first()
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            # Get related data
            attributes = ProductAttribute.get_product_attributes(product_id)
            images = ProductImage.get_product_images(product_id)
            videos = ProductVideo.get_product_videos(product_id)
            variants = ProductVariant.query.filter_by(product_id=product_id).all()
            
            product_data = product.to_dict()
            product_data.update({
                'attributes': [attr.to_dict() for attr in attributes],
                'images': [img.to_dict() for img in images],
                'videos': [video.to_dict() for video in videos],
                'variants': [variant.to_dict() for variant in variants]
            })
            
            return jsonify(product_data), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def update_product(product_id):
        """Update product details."""
        try:
            merchant_id = get_jwt_identity()
            product = Product.query.filter_by(product_id=product_id, id=merchant_id).first()
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            data = request.get_json()
            
            # Update basic product information
            for key, value in data.items():
                if hasattr(product, key) and key not in ['product_id', 'id', 'sku', 'url_key']:
                    if key in ['special_price_from', 'special_price_to'] and value:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    setattr(product, key, value)
            
            # Update attributes
            if 'attributes' in data:
                # Remove existing attributes
                ProductAttribute.query.filter_by(product_id=product_id).delete()
                
                # Add new attributes
                for attr_data in data['attributes']:
                    attribute = Attribute.get_by_id(attr_data['attribute_id'])
                    if not attribute:
                        continue
                        
                    if attribute.is_category_specific and attribute.category_id != product.category_id:
                        continue
                        
                    product_attr = ProductAttribute(
                        product_id=product_id,
                        attribute_id=attr_data['attribute_id'],
                        value=attr_data['value']
                    )
                    db.session.add(product_attr)
            
            # Update variants
            if 'variants' in data:
                # Remove existing variants
                ProductVariant.query.filter_by(product_id=product_id).delete()
                
                # Add new variants
                for variant_data in data['variants']:
                    size_id = variant_data.get('size_id')
                    if size_id:
                        size = Size.get_by_id(size_id)
                        if not size or (size.category_id and size.category_id != product.category_id):
                            continue
                    
                    variant = ProductVariant(
                        product_id=product_id,
                        size_id=size_id,
                        sku=variant_data.get('sku'),
                        price=variant_data.get('price'),
                        stock_quantity=variant_data.get('stock_quantity'),
                        attributes=variant_data.get('attributes', {})
                    )
                    db.session.add(variant)
            
            # Update images
            if 'images' in data:
                # Remove existing images
                ProductImage.query.filter_by(product_id=product_id).delete()
                
                # Add new images
                for image_data in data['images']:
                    image = ProductImage(
                        product_id=product_id,
                        image_url=image_data['url'],
                        is_main=image_data.get('is_main', False)
                    )
                    db.session.add(image)
            
            # Update videos
            if 'videos' in data:
                # Remove existing videos
                ProductVideo.query.filter_by(product_id=product_id).delete()
                
                # Add new videos
                for video_data in data['videos']:
                    video = ProductVideo(
                        product_id=product_id,
                        video_url=video_data['url']
                    )
                    db.session.add(video)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Product updated successfully',
                'product_id': product_id
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def delete_product(product_id):
        """Delete a product."""
        try:
            merchant_id = get_jwt_identity()
            product = Product.query.filter_by(product_id=product_id, id=merchant_id).first()
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            # Delete related records first
            ProductAttribute.query.filter_by(product_id=product_id).delete()
            ProductImage.query.filter_by(product_id=product_id).delete()
            ProductVideo.query.filter_by(product_id=product_id).delete()
            ProductVariant.query.filter_by(product_id=product_id).delete()
            
            # Delete the product
            db.session.delete(product)
            db.session.commit()
            
            return jsonify({
                'message': 'Product deleted successfully'
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def list_products():
        """List all products for the authenticated merchant."""
        try:
            merchant_id = get_jwt_identity()
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            # Build query
            query = Product.query.filter_by(id=merchant_id)
            
            # Apply filters
            category_id = request.args.get('category_id')
            if category_id:
                query = query.filter_by(category_id=category_id)
            
            sub_category_id = request.args.get('sub_category_id')
            if sub_category_id:
                query = query.filter_by(sub_category_id=sub_category_id)
            
            brand_id = request.args.get('brand_id')
            if brand_id:
                query = query.filter_by(brand_id=brand_id)
            
            # Apply sorting
            sort_by = request.args.get('sort_by', 'created_at')
            sort_order = request.args.get('sort_order', 'desc')
            
            if sort_order == 'desc':
                query = query.order_by(getattr(Product, sort_by).desc())
            else:
                query = query.order_by(getattr(Product, sort_by).asc())
            
            # Execute query with pagination
            pagination = query.paginate(page=page, per_page=per_page)
            
            # Get related data for each product
            products_data = []
            for product in pagination.items:
                product_dict = product.to_dict()
                product_dict.update({
                    'main_image': ProductImage.get_main_image(product.product_id).to_dict() if ProductImage.get_main_image(product.product_id) else None,
                    'attribute_count': ProductAttribute.query.filter_by(product_id=product.product_id).count(),
                    'variant_count': ProductVariant.query.filter_by(product_id=product.product_id).count()
                })
                products_data.append(product_dict)
            
            return jsonify({
                'products': products_data,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page
            }), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def update_stock(product_id):
        """Update product stock quantity."""
        try:
            merchant_id = get_jwt_identity()
            product = Product.query.filter_by(product_id=product_id, id=merchant_id).first()
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            data = request.get_json()
            
            if 'stock_quantity' in data:
                product.stock_quantity = data['stock_quantity']
            
            if 'low_stock_threshold' in data:
                product.low_stock_threshold = data['low_stock_threshold']
            
            db.session.commit()
            
            return jsonify({
                'message': 'Stock updated successfully',
                'product_id': product_id
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @staticmethod
    @jwt_required()
    def update_price(product_id):
        """Update product price."""
        try:
            merchant_id = get_jwt_identity()
            product = Product.query.filter_by(product_id=product_id, id=merchant_id).first()
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            data = request.get_json()
            
            if 'price' in data:
                product.price = data['price']
            
            if 'special_price' in data:
                product.special_price = data['special_price']
            
            if 'special_price_from' in data:
                product.special_price_from = datetime.strptime(data['special_price_from'], '%Y-%m-%d').date()
            
            if 'special_price_to' in data:
                product.special_price_to = datetime.strptime(data['special_price_to'], '%Y-%m-%d').date()
            
            db.session.commit()
            
            return jsonify({
                'message': 'Price updated successfully',
                'product_id': product_id
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400 