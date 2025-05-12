from flask import jsonify, request
from models.catalog.category import Category
from models.catalog.attributes import Attribute, Size
from models.catalog.color import Color
from models.catalog.brand import Brand, AddedBy
from common.database import db

class CategoryController:
    @staticmethod
    def create_category(request):
        data = request.get_json()
        name = data.get('name')
        parent_id = data.get('parent_id')

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        category = Category(name=name, parent_id=parent_id)
        db.session.add(category)
        db.session.commit()

        return jsonify({
            'message': 'Category created successfully',
            'category': {
                'id': category.category_id,
                'name': category.name,
                'parent_id': category.parent_id
            }
        }), 201

    @staticmethod
    def get_categories(request):
        try:
            # Get all categories
            categories = Category.query.all()
            
            # Format the response to include parent-child relationships
            formatted_categories = [{
                'id': cat.category_id,
                'name': cat.name,
                'parent_id': cat.parent_id,
                'subcategories': [{
                    'id': sub.category_id,
                    'name': sub.name,
                    'parent_id': sub.parent_id
                } for sub in cat.subcategories]
            } for cat in categories]

            return jsonify({
                'categories': formatted_categories
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_category(category_id):
        try:
            category = Category.get_by_id(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404

            # Get subcategories for this category
            subcategories = [{
                'id': sub.category_id,
                'name': sub.name,
                'parent_id': sub.parent_id
            } for sub in category.subcategories]

            return jsonify({
                'category': {
                    'id': category.category_id,
                    'name': category.name,
                    'parent_id': category.parent_id,
                    'subcategories': subcategories
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def update_category(category_id, request):
        try:
            category = Category.get_by_id(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404

            data = request.get_json()
            if 'name' in data:
                category.name = data['name']
            if 'parent_id' in data:
                category.parent_id = data['parent_id']

            db.session.commit()
            return jsonify({
                'message': 'Category updated successfully',
                'category': {
                    'id': category.category_id,
                    'name': category.name,
                    'parent_id': category.parent_id
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def delete_category(category_id):
        try:
            category = Category.get_by_id(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404

            # Check if category has subcategories
            if category.subcategories.count() > 0:
                return jsonify({'error': 'Cannot delete category with subcategories'}), 400

            db.session.delete(category)
            db.session.commit()
            return jsonify({'message': 'Category deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

class BrandController:
    @staticmethod
    def create_brand(request):
        data = request.get_json()
        name = data.get('name')
        category_id = data.get('category_id')
        added_by = data.get('added_by')  # Get the merchant ID from request
        is_approved = data.get('is_approved', False)  # Default to False for new brands

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        if not added_by:
            return jsonify({'error': 'Merchant ID is required'}), 400

        try:
            # Create brand with merchant ID
            brand = Brand(
                name=name,
                category_id=category_id,
                id=added_by,  # Set the merchant profile ID
                added_by=AddedBy.MERCHANT,  # Set as merchant-created
                is_approved=is_approved
            )
            db.session.add(brand)
            db.session.commit()

            return jsonify({
                'message': 'Brand created successfully',
                'brand': {
                    'id': brand.brand_id,
                    'name': brand.name,
                    'category_id': brand.category_id,
                    'added_by': brand.added_by.value,
                    'is_approved': brand.is_approved,
                    'merchant_id': brand.id
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_brands(request):
        try:
            category_id = request.args.get('category_id')
            parent_category_id = request.args.get('parent_category_id')
            
            # Build query based on parameters
            query = Brand.query
            
            if category_id:
                if parent_category_id:
                    # If both category_id and parent_category_id are provided
                    query = query.filter(
                        Brand.category_id == category_id,
                        Brand.category.has(parent_id=parent_category_id)
                    )
                else:
                    query = query.filter_by(category_id=category_id)

            brands = query.all()

            return jsonify({
                'brands': [{
                    'id': brand.brand_id,
                    'name': brand.name,
                    'category_id': brand.category_id,
                    'added_by': brand.added_by.value,
                    'is_approved': brand.is_approved,
                    'merchant_id': brand.id,
                    'category': {
                        'id': brand.category.category_id,
                        'name': brand.category.name
                    } if brand.category else None
                } for brand in brands]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_brand(brand_id):
        try:
            brand = Brand.get_by_id(brand_id)
            if not brand:
                return jsonify({'error': 'Brand not found'}), 404

            return jsonify({
                'brand': {
                    'id': brand.brand_id,
                    'name': brand.name,
                    'category_id': brand.category_id,
                    'added_by': brand.added_by.value,
                    'is_approved': brand.is_approved,
                    'category': {
                        'id': brand.category.category_id,
                        'name': brand.category.name
                    } if brand.category else None
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def update_brand(brand_id, request):
        try:
            brand = Brand.get_by_id(brand_id)
            if not brand:
                return jsonify({'error': 'Brand not found'}), 404

            data = request.get_json()
            if 'name' in data:
                brand.name = data['name']
            if 'category_id' in data:
                brand.category_id = data['category_id']

            db.session.commit()
            return jsonify({
                'message': 'Brand updated successfully',
                'brand': {
                    'id': brand.brand_id,
                    'name': brand.name,
                    'category_id': brand.category_id,
                    'added_by': brand.added_by.value,
                    'is_approved': brand.is_approved,
                    'category': {
                        'id': brand.category.category_id,
                        'name': brand.category.name
                    } if brand.category else None
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def delete_brand(brand_id):
        try:
            brand = Brand.get_by_id(brand_id)
            if not brand:
                return jsonify({'error': 'Brand not found'}), 404

            # Check if brand is used in any products
            if brand.products:
                return jsonify({'error': 'Cannot delete brand that is used in products'}), 400

            db.session.delete(brand)
            db.session.commit()
            return jsonify({'message': 'Brand deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

class AttributeController:
    @staticmethod
    def create_attribute(request):
        data = request.get_json()
        name = data.get('name')
        is_category_specific = data.get('is_category_specific', False)
        category_id = data.get('category_id')

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        attribute = Attribute(
            name=name,
            is_category_specific=is_category_specific,
            category_id=category_id
        )
        db.session.add(attribute)
        db.session.commit()

        return jsonify({
            'message': 'Attribute created successfully',
            'attribute': {
                'id': attribute.attribute_id,
                'name': attribute.name,
                'is_category_specific': attribute.is_category_specific,
                'category_id': attribute.category_id
            }
        }), 201

    @staticmethod
    def get_attributes(request):
        category_id = request.args.get('category_id')
        if category_id:
            attributes = Attribute.get_by_category(category_id)
        else:
            attributes = Attribute.query.all()

        return jsonify({
            'attributes': [{
                'id': attr.attribute_id,
                'name': attr.name,
                'is_category_specific': attr.is_category_specific,
                'category_id': attr.category_id
            } for attr in attributes]
        })

    @staticmethod
    def get_attribute(attribute_id):
        attribute = Attribute.get_by_id(attribute_id)
        if not attribute:
            return jsonify({'error': 'Attribute not found'}), 404

        return jsonify({
            'attribute': {
                'id': attribute.attribute_id,
                'name': attribute.name,
                'is_category_specific': attribute.is_category_specific,
                'category_id': attribute.category_id
            }
        })

    @staticmethod
    def update_attribute(attribute_id, request):
        attribute = Attribute.get_by_id(attribute_id)
        if not attribute:
            return jsonify({'error': 'Attribute not found'}), 404

        data = request.get_json()
        if 'name' in data:
            attribute.name = data['name']
        if 'is_category_specific' in data:
            attribute.is_category_specific = data['is_category_specific']
        if 'category_id' in data:
            attribute.category_id = data['category_id']

        db.session.commit()
        return jsonify({
            'message': 'Attribute updated successfully',
            'attribute': {
                'id': attribute.attribute_id,
                'name': attribute.name,
                'is_category_specific': attribute.is_category_specific,
                'category_id': attribute.category_id
            }
        })

    @staticmethod
    def delete_attribute(attribute_id):
        attribute = Attribute.get_by_id(attribute_id)
        if not attribute:
            return jsonify({'error': 'Attribute not found'}), 404

        db.session.delete(attribute)
        db.session.commit()
        return jsonify({'message': 'Attribute deleted successfully'})

class ColorController:
    @staticmethod
    def create_color(request):
        data = request.get_json()
        name = data.get('name')
        hex_code = data.get('hex_code')

        if not name or not hex_code:
            return jsonify({'error': 'Name and hex_code are required'}), 400

        color = Color(name=name, hex_code=hex_code)
        db.session.add(color)
        db.session.commit()

        return jsonify({
            'message': 'Color created successfully',
            'color': {
                'id': color.color_id,
                'name': color.name,
                'hex_code': color.hex_code,
                'is_approved': color.is_approved
            }
        }), 201

    @staticmethod
    def get_colors(request):
        colors = Color.query.all()
        return jsonify({
            'colors': [{
                'id': color.color_id,
                'name': color.name,
                'hex_code': color.hex_code,
                'is_approved': color.is_approved
            } for color in colors]
        })

    @staticmethod
    def get_color(color_id):
        color = Color.get_by_id(color_id)
        if not color:
            return jsonify({'error': 'Color not found'}), 404

        return jsonify({
            'color': {
                'id': color.color_id,
                'name': color.name,
                'hex_code': color.hex_code,
                'is_approved': color.is_approved
            }
        })

    @staticmethod
    def update_color(color_id, request):
        color = Color.get_by_id(color_id)
        if not color:
            return jsonify({'error': 'Color not found'}), 404

        data = request.get_json()
        if 'name' in data:
            color.name = data['name']
        if 'hex_code' in data:
            color.hex_code = data['hex_code']

        db.session.commit()
        return jsonify({
            'message': 'Color updated successfully',
            'color': {
                'id': color.color_id,
                'name': color.name,
                'hex_code': color.hex_code,
                'is_approved': color.is_approved
            }
        })

    @staticmethod
    def delete_color(color_id):
        color = Color.get_by_id(color_id)
        if not color:
            return jsonify({'error': 'Color not found'}), 404

        db.session.delete(color)
        db.session.commit()
        return jsonify({'message': 'Color deleted successfully'})

    @staticmethod
    def approve_color(color_id):
        color = Color.get_by_id(color_id)
        if not color:
            return jsonify({'error': 'Color not found'}), 404

        color.approve()
        return jsonify({
            'message': 'Color approved successfully',
            'color': {
                'id': color.color_id,
                'name': color.name,
                'hex_code': color.hex_code,
                'is_approved': color.is_approved
            }
        })

class SizeController:
    @staticmethod
    def create_size(request):
        data = request.get_json()
        name = data.get('name')
        category_id = data.get('category_id')

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        size = Size(name=name, category_id=category_id)
        db.session.add(size)
        db.session.commit()

        return jsonify({
            'message': 'Size created successfully',
            'size': {
                'id': size.size_id,
                'name': size.name,
                'category_id': size.category_id,
                'created_at': size.created_at.isoformat() if size.created_at else None,
                'updated_at': size.updated_at.isoformat() if size.updated_at else None
            }
        }), 201

    @staticmethod
    def get_sizes(request):
        try:
            category_id = request.args.get('category_id')
            if category_id:
                sizes = Size.get_by_category(category_id)
            else:
                sizes = Size.query.all()
                
            return jsonify({
                'sizes': [{
                    'id': size.size_id,
                    'name': size.name,
                    'category_id': size.category_id,
                    'created_at': size.created_at.isoformat() if size.created_at else None,
                    'updated_at': size.updated_at.isoformat() if size.updated_at else None
                } for size in sizes]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_size(size_id):
        try:
            size = Size.get_by_id(size_id)
            if not size:
                return jsonify({'error': 'Size not found'}), 404

            return jsonify({
                'size': {
                    'id': size.size_id,
                    'name': size.name,
                    'category_id': size.category_id,
                    'created_at': size.created_at.isoformat() if size.created_at else None,
                    'updated_at': size.updated_at.isoformat() if size.updated_at else None
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def update_size(size_id, request):
        try:
            size = Size.get_by_id(size_id)
            if not size:
                return jsonify({'error': 'Size not found'}), 404

            data = request.get_json()
            if 'name' in data:
                size.name = data['name']
            if 'category_id' in data:
                size.category_id = data['category_id']

            db.session.commit()
            return jsonify({
                'message': 'Size updated successfully',
                'size': {
                    'id': size.size_id,
                    'name': size.name,
                    'category_id': size.category_id,
                    'created_at': size.created_at.isoformat() if size.created_at else None,
                    'updated_at': size.updated_at.isoformat() if size.updated_at else None
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def delete_size(size_id):
        try:
            size = Size.get_by_id(size_id)
            if not size:
                return jsonify({'error': 'Size not found'}), 404

            # Check if size is used in any variants
            if size.variants:
                return jsonify({'error': 'Cannot delete size that is used in product variants'}), 400

            db.session.delete(size)
            db.session.commit()
            return jsonify({'message': 'Size deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500