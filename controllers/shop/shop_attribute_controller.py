from flask import request, jsonify
from common.database import db
from models.shop.shop_attribute import ShopAttribute, ShopAttributeValue
from models.shop.shop import Shop
from models.shop.shop_category import ShopCategory
from models.enums import AttributeInputType
from common.decorators import superadmin_required
from datetime import datetime, timezone
from sqlalchemy import desc, or_
import re

class ShopAttributeController:
    
    @staticmethod
    def get_attributes_by_shop_category(shop_id, category_id):
        """Get all attributes for a specific shop category"""
        try:
            # Verify shop exists
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None)
            ).first()
            
            if not shop:
                return jsonify({
                    'status': 'error',
                    'message': 'Shop not found'
                }), 404
            
            # Verify category exists and belongs to the shop
            category = ShopCategory.query.filter(
                ShopCategory.category_id == category_id,
                ShopCategory.shop_id == shop_id,
                ShopCategory.deleted_at.is_(None)
            ).first()
            
            if not category:
                return jsonify({
                    'status': 'error',
                    'message': 'Category not found in this shop'
                }), 404
            
            attributes = ShopAttribute.query.filter(
                ShopAttribute.shop_id == shop_id,
                ShopAttribute.category_id == category_id,
                ShopAttribute.deleted_at.is_(None)
            ).order_by(ShopAttribute.sort_order, ShopAttribute.name).all()
            
            return jsonify({
                'status': 'success',
                'data': [attribute.serialize() for attribute in attributes]
            }), 200
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error fetching attributes: {str(e)}'
            }), 500

    @staticmethod
    def get_attribute_by_id(attribute_id):
        """Get a specific attribute by ID"""
        try:
            attribute = ShopAttribute.query.filter(
                ShopAttribute.attribute_id == attribute_id,
                ShopAttribute.deleted_at.is_(None)
            ).first()
            
            if not attribute:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute not found'
                }), 404
                
            return jsonify({
                'status': 'success',
                'data': attribute.serialize()
            }), 200
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error fetching attribute: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def create_attribute():
        """Create a new attribute for a shop category"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['shop_id', 'category_id', 'name', 'attribute_type']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({
                        'status': 'error',
                        'message': f'{field} is required'
                    }), 400
            
            # Validate attribute type
            try:
                attribute_type = AttributeInputType(data['attribute_type'])
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid attribute type'
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
            
            # Generate slug from name if not provided
            if 'slug' not in data or not data['slug']:
                data['slug'] = re.sub(r'[^a-zA-Z0-9\s]', '', data['name']).replace(' ', '-').lower()
            
            # Check if attribute with same name or slug exists in this shop-category
            existing_attribute = ShopAttribute.query.filter(
                ShopAttribute.shop_id == data['shop_id'],
                ShopAttribute.category_id == data['category_id'],
                or_(ShopAttribute.name == data['name'], ShopAttribute.slug == data['slug']),
                ShopAttribute.deleted_at.is_(None)
            ).first()
            
            if existing_attribute:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute with this name or slug already exists in this shop-category'
                }), 400
            
            # Create new attribute
            attribute = ShopAttribute(
                shop_id=data['shop_id'],
                category_id=data['category_id'],
                name=data['name'],
                slug=data['slug'],
                description=data.get('description'),
                attribute_type=attribute_type,
                is_required=data.get('is_required', False),
                is_filterable=data.get('is_filterable', False),
                sort_order=data.get('sort_order', 0),
                is_active=data.get('is_active', True)
            )
            
            db.session.add(attribute)
            db.session.flush()  # To get the attribute_id
            
            # Add attribute values if provided
            if 'values' in data and data['values']:
                for value_data in data['values']:
                    if 'value' in value_data and value_data['value']:
                        attribute_value = ShopAttributeValue(
                            attribute_id=attribute.attribute_id,
                            value=value_data['value'],
                            sort_order=value_data.get('sort_order', 0),
                            is_active=value_data.get('is_active', True)
                        )
                        db.session.add(attribute_value)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute created successfully',
                'data': attribute.serialize()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error creating attribute: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def update_attribute(attribute_id):
        """Update an existing attribute"""
        try:
            attribute = ShopAttribute.query.filter(
                ShopAttribute.attribute_id == attribute_id,
                ShopAttribute.deleted_at.is_(None)
            ).first()
            
            if not attribute:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute not found'
                }), 404
            
            data = request.get_json()
            
            # Validate attribute type if provided
            if 'attribute_type' in data:
                try:
                    attribute_type = AttributeInputType(data['attribute_type'])
                except ValueError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid attribute type'
                    }), 400
            
            # Check if another attribute with same name or slug exists in the same shop-category
            if 'name' in data and data['name'] != attribute.name:
                existing_attribute = ShopAttribute.query.filter(
                    ShopAttribute.shop_id == attribute.shop_id,
                    ShopAttribute.category_id == attribute.category_id,
                    ShopAttribute.name == data['name'],
                    ShopAttribute.attribute_id != attribute_id,
                    ShopAttribute.deleted_at.is_(None)
                ).first()
                if existing_attribute:
                    return jsonify({
                        'status': 'error',
                        'message': 'Attribute with this name already exists in this shop-category'
                    }), 400
            
            if 'slug' in data and data['slug'] != attribute.slug:
                existing_attribute = ShopAttribute.query.filter(
                    ShopAttribute.shop_id == attribute.shop_id,
                    ShopAttribute.category_id == attribute.category_id,
                    ShopAttribute.slug == data['slug'],
                    ShopAttribute.attribute_id != attribute_id,
                    ShopAttribute.deleted_at.is_(None)
                ).first()
                if existing_attribute:
                    return jsonify({
                        'status': 'error',
                        'message': 'Attribute with this slug already exists in this shop-category'
                    }), 400
            
            # Update attribute fields
            if 'name' in data:
                attribute.name = data['name']
            if 'slug' in data:
                attribute.slug = data['slug']
            if 'description' in data:
                attribute.description = data['description']
            if 'attribute_type' in data:
                attribute.attribute_type = AttributeInputType(data['attribute_type'])
            if 'is_required' in data:
                attribute.is_required = data['is_required']
            if 'is_filterable' in data:
                attribute.is_filterable = data['is_filterable']
            if 'sort_order' in data:
                attribute.sort_order = data['sort_order']
            if 'is_active' in data:
                attribute.is_active = data['is_active']
                
            attribute.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute updated successfully',
                'data': attribute.serialize()
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error updating attribute: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def delete_attribute(attribute_id):
        """Hard delete an attribute and all its values"""
        try:
            attribute = ShopAttribute.query.filter(
                ShopAttribute.attribute_id == attribute_id,
                ShopAttribute.deleted_at.is_(None)
            ).first()
            
            if not attribute:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute not found'
                }), 404
            
            # Check if attribute is being used by any products
            if attribute.product_attributes:
                return jsonify({
                    'status': 'error',
                    'message': 'Cannot delete attribute that is being used by products'
                }), 400
            
            # Hard delete all attribute values first (due to foreign key constraints)
            for value in attribute.attribute_values:
                db.session.delete(value)
            
            # Hard delete the attribute
            db.session.delete(attribute)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute deleted successfully'
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error deleting attribute: {str(e)}'
            }), 500
            return jsonify({
                'status': 'error',
                'message': f'Error deleting attribute: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def add_attribute_value():
        """Add a new value to an attribute"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['attribute_id', 'value']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({
                        'status': 'error',
                        'message': f'{field} is required'
                    }), 400
            
            # Verify attribute exists
            attribute = ShopAttribute.query.filter(
                ShopAttribute.attribute_id == data['attribute_id'],
                ShopAttribute.deleted_at.is_(None)
            ).first()
            
            if not attribute:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute not found'
                }), 404
            
            # Check if value already exists
            existing_value = ShopAttributeValue.query.filter(
                ShopAttributeValue.attribute_id == data['attribute_id'],
                ShopAttributeValue.value == data['value'],
                ShopAttributeValue.deleted_at.is_(None)
            ).first()
            
            if existing_value:
                return jsonify({
                    'status': 'error',
                    'message': 'Value already exists for this attribute'
                }), 400
            
            # Create new attribute value
            attribute_value = ShopAttributeValue(
                attribute_id=data['attribute_id'],
                value=data['value'],
                sort_order=data.get('sort_order', 0),
                is_active=data.get('is_active', True)
            )
            
            db.session.add(attribute_value)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute value added successfully',
                'data': attribute_value.serialize()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error adding attribute value: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def update_attribute_value(value_id):
        """Update an attribute value"""
        try:
            attribute_value = ShopAttributeValue.query.filter(
                ShopAttributeValue.value_id == value_id,
                ShopAttributeValue.deleted_at.is_(None)
            ).first()
            
            if not attribute_value:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute value not found'
                }), 404
            
            data = request.get_json()
            
            # Check if another value with same text exists for the same attribute
            if 'value' in data and data['value'] != attribute_value.value:
                existing_value = ShopAttributeValue.query.filter(
                    ShopAttributeValue.attribute_id == attribute_value.attribute_id,
                    ShopAttributeValue.value == data['value'],
                    ShopAttributeValue.value_id != value_id,
                    ShopAttributeValue.deleted_at.is_(None)
                ).first()
                if existing_value:
                    return jsonify({
                        'status': 'error',
                        'message': 'Value already exists for this attribute'
                    }), 400
            
            # Update attribute value fields
            if 'value' in data:
                attribute_value.value = data['value']
            if 'sort_order' in data:
                attribute_value.sort_order = data['sort_order']
            if 'is_active' in data:
                attribute_value.is_active = data['is_active']
                
            attribute_value.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute value updated successfully',
                'data': attribute_value.serialize()
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error updating attribute value: {str(e)}'
            }), 500

    @staticmethod
    @superadmin_required
    def delete_attribute_value(value_id):
        """Hard delete an attribute value"""
        try:
            attribute_value = ShopAttributeValue.query.filter(
                ShopAttributeValue.value_id == value_id,
                ShopAttributeValue.deleted_at.is_(None)
            ).first()
            
            if not attribute_value:
                return jsonify({
                    'status': 'error',
                    'message': 'Attribute value not found'
                }), 404
            
            # Hard delete the attribute value
            db.session.delete(attribute_value)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Attribute value deleted successfully'
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error deleting attribute value: {str(e)}'
            }), 500
