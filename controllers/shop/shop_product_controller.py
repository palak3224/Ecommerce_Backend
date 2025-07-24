
from flask import request, jsonify
from common.database import db
from models.shop.shop_product import ShopProduct
from models.shop.shop_category import ShopCategory
from models.shop.shop_brand import ShopBrand
from models.shop.shop import Shop
from models.shop.shop_product_media import ShopProductMedia
from models.shop.shop_product_attribute import ShopProductAttribute
from models.shop.shop_product_stock import ShopProductStock
from models.shop.shop_product_shipping import ShopProductShipping
from models.shop.shop_product_meta import ShopProductMeta
from models.shop.shop_attribute import ShopAttribute, ShopAttributeValue
from models.enums import MediaType
from sqlalchemy import desc, or_, func
from common.decorators import superadmin_required
from datetime import datetime, timezone
import random
import string

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
    def get_product_details(product_id):
        """Get complete product details for editing including all relationships"""
        try:
            # Get base product information
            product = ShopProduct.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404

            # Get product media
            product_media = ShopProductMedia.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).order_by(ShopProductMedia.sort_order).all()

            # Get product meta information
            product_meta = ShopProductMeta.query.filter_by(
                product_id=product_id
            ).first()

            # Get product attributes
            product_attributes = ShopProductAttribute.query.filter_by(
                product_id=product_id
            ).all()

            # Get shipping information
            shipping = ShopProductShipping.query.filter_by(
                product_id=product_id
            ).first()

            # Get stock information  
            stock = ShopProductStock.query.filter_by(
                product_id=product_id
            ).first()

            # Prepare response data
            response_data = product.serialize()
            
            # Add detailed information
            response_data.update({
                "media": [media.serialize() for media in product_media] if product_media else [],
                "meta": {
                    "short_desc": product_meta.short_desc if product_meta else "",
                    "full_desc": product_meta.full_desc if product_meta else "",
                    "meta_title": product_meta.meta_title if product_meta else "",
                    "meta_desc": product_meta.meta_desc if product_meta else "",
                    "meta_keywords": product_meta.meta_keywords if product_meta else ""
                },
                "attributes": [attr.serialize() for attr in product_attributes] if product_attributes else [],
                "shipping": {
                    "length_cm": float(shipping.length_cm) if shipping and shipping.length_cm else 0,
                    "width_cm": float(shipping.width_cm) if shipping and shipping.width_cm else 0,
                    "height_cm": float(shipping.height_cm) if shipping and shipping.height_cm else 0,
                    "weight_kg": float(shipping.weight_kg) if shipping and shipping.weight_kg else 0,
                    "shipping_class": "standard"  # Default shipping class
                },
                "stock": {
                    "stock_qty": stock.stock_qty if stock else 0,
                    "low_stock_threshold": stock.low_stock_threshold if stock else 5
                }
            })

            return jsonify({
                'status': 'success',
                'data': response_data
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error fetching product details: {str(e)}'
            }), 500

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

    @staticmethod
    def generate_unique_sku(shop_id, category_id, product_name):
        """Generate a unique SKU for the product"""
        # Get shop and category codes
        shop = Shop.query.get(shop_id)
        category = ShopCategory.query.get(category_id)
        
        shop_code = f"SH{shop_id:02d}" if shop else "SH00"
        category_code = category.name[:3].upper() if category else "GEN"
        
        # Create timestamp part
        timestamp = datetime.now().strftime("%Y%m%d%H")
        
        # Generate random suffix
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        
        base_sku = f"{shop_code}-{category_code}-{timestamp}-{random_suffix}"
        
        # Ensure uniqueness
        counter = 1
        sku = base_sku
        while ShopProduct.query.filter_by(sku=sku, deleted_at=None).first():
            sku = f"{base_sku}-{counter:02d}"
            counter += 1
            
        return sku

    # PRODUCTION-READY MULTI-STEP PRODUCT CREATION SYSTEM
    # ====================================================
    # This system creates products in steps but ensures data integrity,
    # scalability, and uses all existing models properly.

    @staticmethod
    @superadmin_required
    def create_product_step1():
        """Step 1: Create product with basic information and return product_id for subsequent steps"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['shop_id', 'category_id', 'product_name', 'cost_price', 'selling_price']
            for field in required_fields:
                if field not in data or data[field] in [None, '']:
                    return jsonify({
                        'status': 'error',
                        'message': f'{field} is required'
                    }), 400
            
            # Validate shop and category exist and are active
            shop = Shop.query.filter(
                Shop.shop_id == data['shop_id'],
                Shop.deleted_at.is_(None),
                Shop.is_active == True
            ).first()
            if not shop:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid or inactive shop'
                }), 400
                
            category = ShopCategory.query.filter(
                ShopCategory.category_id == data['category_id'],
                ShopCategory.shop_id == data['shop_id'],
                ShopCategory.deleted_at.is_(None),
                ShopCategory.is_active == True
            ).first()
            if not category:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid or inactive category for this shop'
                }), 400
            
            # Validate brand if provided (now optional)
            brand_id = data.get('brand_id')
            if brand_id:
                brand = ShopBrand.query.filter(
                    ShopBrand.brand_id == brand_id,
                    ShopBrand.shop_id == data['shop_id'],
                    ShopBrand.category_id == data['category_id'],
                    ShopBrand.deleted_at.is_(None),
                    ShopBrand.is_active == True
                ).first()
                if not brand:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid brand for this shop-category combination'
                    }), 400
            
            # Generate or validate SKU
            sku = data.get('sku')
            if not sku:
                sku = ShopProductController.generate_unique_sku(
                    data['shop_id'], 
                    data['category_id'], 
                    data['product_name']
                )
            else:
                # Check SKU uniqueness if provided
                existing_product = ShopProduct.query.filter(
                    ShopProduct.sku == sku,
                    ShopProduct.deleted_at.is_(None)
                ).first()
                if existing_product:
                    return jsonify({
                        'status': 'error',
                        'message': f'SKU "{sku}" already exists'
                    }), 400
            
            # Parse datetime fields for special offers
            special_start = None
            special_end = None
            if data.get('special_start'):
                try:
                    special_start = datetime.fromisoformat(data['special_start'].replace('Z', '+00:00'))
                except ValueError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid special_start date format'
                    }), 400
                    
            if data.get('special_end'):
                try:
                    special_end = datetime.fromisoformat(data['special_end'].replace('Z', '+00:00'))
                except ValueError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid special_end date format'
                    }), 400
            
            # Calculate discount percentage if cost and selling prices are provided
            discount_pct = 0.0
            if data['cost_price'] > 0 and data['selling_price'] > 0:
                discount_pct = round(((data['selling_price'] - data['cost_price']) / data['cost_price']) * 100, 2)
            
            # Create the base product record
            product = ShopProduct(
                shop_id=data['shop_id'],
                category_id=data['category_id'],
                brand_id=brand_id,
                sku=sku,
                product_name=data['product_name'],
                product_description=data.get('product_description', ''),
                cost_price=data['cost_price'],
                selling_price=data['selling_price'],
                discount_pct=discount_pct,
                special_price=data.get('special_price'),
                special_start=special_start,
                special_end=special_end,
                is_published=False,  # Will be published manually via shop management
                active_flag=True   # Will be activated manually via shop management
            )
            
            db.session.add(product)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product basic information saved successfully',
                'data': {
                    'product_id': product.product_id,
                    'sku': product.sku,
                    'product_name': product.product_name,
                    'discount_pct': discount_pct,
                    'next_step': 2
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error creating product: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required  
    def create_product_step2():
        """Step 2: Save product attributes using existing ShopProductAttribute model"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            attributes = data.get('attributes', [])
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'product_id is required'
                }), 400
            
            # Verify product exists and get it
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Clear existing attributes for this product (in case of re-editing)
            ShopProductAttribute.query.filter_by(product_id=product_id).delete()
            
            # Save new attributes
            saved_attributes = []
            for attr_data in attributes:
                attribute_id = attr_data.get('attribute_id')
                value = attr_data.get('value')
                
                if not attribute_id or value in [None, '']:
                    continue
                
                # Get the attribute to determine its type
                attribute = ShopAttribute.query.get(attribute_id)
                if not attribute:
                    continue
                
                # Create product attribute record
                product_attr = ShopProductAttribute(
                    product_id=product_id,
                    attribute_id=attribute_id
                )
                
                # Set the appropriate value field based on attribute type
                if attribute.attribute_type.value in ['SELECT', 'MULTISELECT']:
                    # For select types, find the attribute value ID
                    attr_value = ShopAttributeValue.query.filter_by(
                        attribute_id=attribute_id,
                        value=value
                    ).first()
                    if attr_value:
                        product_attr.value_id = attr_value.value_id
                        product_attr.value_code = value
                elif attribute.attribute_type.value == 'NUMBER':
                    try:
                        product_attr.value_number = float(value)
                    except (ValueError, TypeError):
                        continue
                elif attribute.attribute_type.value == 'BOOLEAN':
                    product_attr.value_text = str(bool(value))
                else:  # TEXT, TEXTAREA
                    product_attr.value_text = str(value)
                
                db.session.add(product_attr)
                saved_attributes.append({
                    'attribute_id': attribute_id,
                    'attribute_name': attribute.name,
                    'value': value
                })
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product attributes saved successfully',
                'data': {
                    'product_id': product_id,
                    'attributes_count': len(saved_attributes),
                    'attributes': saved_attributes,
                    'next_step': 3
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error saving attributes: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def create_product_step3():
        """Step 3: Save product media using existing ShopProductMedia model"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            media_items = data.get('media', [])
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'product_id is required'
                }), 400
            
            # Verify product exists
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Separate existing and new media items
            existing_media_ids = []
            new_media_items = []
            
            for i, media_item in enumerate(media_items):
                if not media_item.get('url'):
                    continue
                
                if media_item.get('isExisting') and media_item.get('media_id'):
                    existing_media_ids.append(media_item['media_id'])
                else:
                    new_media_items.append((i, media_item))
            
            # Delete media that are no longer in the list (but keep existing ones that are still present)
            if existing_media_ids:
                ShopProductMedia.query.filter(
                    ShopProductMedia.product_id == product_id,
                    ShopProductMedia.media_id.notin_(existing_media_ids)
                ).delete(synchronize_session=False)
            else:
                # If no existing media IDs provided, clear all existing media
                ShopProductMedia.query.filter_by(product_id=product_id).delete()
            
            # Update existing media (sort order, primary status)
            saved_media = []
            for i, media_item in enumerate(media_items):
                if not media_item.get('url'):
                    continue
                
                if media_item.get('isExisting') and media_item.get('media_id'):
                    # Update existing media
                    existing_media = ShopProductMedia.query.filter_by(
                        media_id=media_item['media_id'],
                        product_id=product_id
                    ).first()
                    
                    if existing_media:
                        existing_media.is_primary = media_item.get('is_primary', i == 0)
                        existing_media.sort_order = i + 1
                        
                        saved_media.append({
                            'media_id': existing_media.media_id,
                            'url': existing_media.url,
                            'type': existing_media.type.value,
                            'is_primary': existing_media.is_primary,
                            'sort_order': existing_media.sort_order
                        })
                else:
                    # Add new media
                    media_type = MediaType.IMAGE if media_item.get('type', 'image').lower() == 'image' else MediaType.VIDEO
                    
                    product_media = ShopProductMedia(
                        product_id=product_id,
                        url=media_item['url'],
                        type=media_type,
                        is_primary=media_item.get('is_primary', i == 0),
                        file_name=media_item.get('file_name', ''),
                        file_size=media_item.get('file_size', 0),
                        sort_order=i + 1
                    )
                    
                    db.session.add(product_media)
                    db.session.flush()  # Flush to get the media_id
                    
                    saved_media.append({
                        'media_id': product_media.media_id,
                        'url': media_item['url'],
                        'type': media_type.value,
                        'is_primary': product_media.is_primary,
                        'sort_order': product_media.sort_order
                    })
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product media saved successfully',
                'data': {
                    'product_id': product_id,
                    'media_count': len(saved_media),
                    'media': saved_media,
                    'next_step': 4
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error saving media: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def create_product_step4():
        """Step 4: Save product shipping information using existing ShopProductShipping model"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'product_id is required'
                }), 400
            
            # Verify product exists
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Get or create shipping record
            shipping = ShopProductShipping.query.filter_by(product_id=product_id).first()
            if not shipping:
                shipping = ShopProductShipping(product_id=product_id)
            
            # Update shipping information
            if 'weight_kg' in data and data['weight_kg'] is not None:
                shipping.weight_kg = float(data['weight_kg'])
            elif 'weight' in data and data['weight'] is not None:
                shipping.weight_kg = float(data['weight'])
                
            if 'length_cm' in data and data['length_cm'] is not None:
                shipping.length_cm = float(data['length_cm'])
            elif 'length' in data and data['length'] is not None:
                shipping.length_cm = float(data['length'])
                
            if 'width_cm' in data and data['width_cm'] is not None:
                shipping.width_cm = float(data['width_cm'])
            elif 'width' in data and data['width'] is not None:
                shipping.width_cm = float(data['width'])
                
            if 'height_cm' in data and data['height_cm'] is not None:
                shipping.height_cm = float(data['height_cm'])
            elif 'height' in data and data['height'] is not None:
                shipping.height_cm = float(data['height'])
                
            if 'shipping_class' in data and data['shipping_class'] is not None:
                shipping.shipping_class = str(data['shipping_class'])
            
            db.session.add(shipping)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product shipping information saved successfully',
                'data': {
                    'product_id': product_id,
                    'shipping': shipping.serialize(),
                    'next_step': 5
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error saving shipping information: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def create_product_step5():
        """Step 5: Save product stock information using existing ShopProductStock model"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'product_id is required'
                }), 400
            
            # Verify product exists
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Get or create stock record
            stock = ShopProductStock.query.filter_by(product_id=product_id).first()
            if not stock:
                stock = ShopProductStock(product_id=product_id)
            
            # Update stock information
            if 'stock_qty' in data and data['stock_qty'] is not None:
                stock.stock_qty = int(data['stock_qty'])
            elif 'stock_quantity' in data and data['stock_quantity'] is not None:
                stock.stock_qty = int(data['stock_quantity'])
            if 'low_stock_threshold' in data and data['low_stock_threshold'] is not None:
                stock.low_stock_threshold = int(data['low_stock_threshold'])
            
            db.session.add(stock)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product stock information saved successfully',
                'data': {
                    'product_id': product_id,
                    'stock': stock.serialize(),
                    'next_step': 6
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error saving stock information: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def create_product_step6():
        """Step 6: Save product meta information using existing ShopProductMeta model and finalize"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'product_id is required'
                }), 400
            
            # Verify product exists
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Get or create meta record
            meta = ShopProductMeta.query.filter_by(product_id=product_id).first()
            if not meta:
                meta = ShopProductMeta(product_id=product_id)
            
            # Update meta information
            if 'short_desc' in data:
                meta.short_desc = data['short_desc']
            if 'full_desc' in data:
                meta.full_desc = data['full_desc']
                # Also update the main product description for backward compatibility
                product.product_description = data['full_desc']
            if 'meta_title' in data:
                meta.meta_title = data['meta_title']
            if 'meta_desc' in data:
                meta.meta_desc = data['meta_desc']
            if 'meta_keywords' in data:
                meta.meta_keywords = data['meta_keywords']
            
            # Finalize the product - mark as published and ready
            product.is_published = True
            product.updated_at = datetime.now(timezone.utc)
            
            db.session.add(meta)
            db.session.commit()
            
            # Get complete product data with all relationships
            complete_product = ShopProduct.query.filter_by(product_id=product_id).first()
            
            return jsonify({
                'status': 'success',
                'message': 'Product created successfully and is now live!',
                'data': {
                    'product_id': product_id,
                    'product': complete_product.serialize(),
                    'meta': meta.serialize(),
                    'is_complete': True
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error finalizing product: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def update_product_status():
        """Update product status (published, active, special offer)"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            
            if not product_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Product ID is required'
                }), 400
                
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            
            if not product:
                return jsonify({
                    'status': 'error',
                    'message': 'Product not found'
                }), 404
            
            # Update fields if provided
            if 'is_published' in data:
                product.is_published = data['is_published']
            if 'active_flag' in data:
                product.active_flag = data['active_flag']
            if 'special_price' in data:
                product.special_price = data['special_price']
            if 'special_start' in data:
                product.special_start = datetime.fromisoformat(data['special_start']) if data['special_start'] else None
            if 'special_end' in data:
                product.special_end = datetime.fromisoformat(data['special_end']) if data['special_end'] else None
                
            product.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Product status updated',
                'data': product.serialize()
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error updating product status: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def update_product_step1(product_id):
        """Update basic product information for an existing product (Step 1)"""
        try:
            data = request.get_json()
            product = ShopProduct.query.filter(
                ShopProduct.product_id == product_id,
                ShopProduct.deleted_at.is_(None)
            ).first()
            if not product:
                return jsonify({'status': 'error', 'message': 'Product not found'}), 404

            # Check SKU uniqueness if changed
            if 'sku' in data and data['sku'] != product.sku:
                existing_product = ShopProduct.query.filter(
                    ShopProduct.sku == data['sku'],
                    ShopProduct.product_id != product_id,
                    ShopProduct.deleted_at.is_(None)
                ).first()
                if existing_product:
                    return jsonify({'status': 'error', 'message': f'SKU \"{data['sku']}\" already exists'}), 400

            # Update fields
            for field in ['shop_id', 'category_id', 'brand_id', 'sku', 'product_name', 'product_description', 'cost_price', 'selling_price', 'special_price', 'special_start', 'special_end']:
                if field in data:
                    setattr(product, field, data[field])

            # Recalculate discount_pct if cost_price or selling_price changed
            if 'cost_price' in data or 'selling_price' in data:
                cost = data.get('cost_price', product.cost_price)
                sell = data.get('selling_price', product.selling_price)
                if cost > 0 and sell > 0:
                    product.discount_pct = round(((sell - cost) / cost) * 100, 2)
                else:
                    product.discount_pct = 0.0

            product.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            return jsonify({
                'status': 'success',
                'message': 'Product basic information updated successfully',
                'data': {
                    'product_id': product.product_id,
                    'sku': product.sku,
                    'product_name': product.product_name,
                    'discount_pct': product.discount_pct,
                    'next_step': 2
                }
            }), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Error updating product: {str(e)}'}), 500
