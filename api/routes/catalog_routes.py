from flask import Blueprint, request, jsonify
from api.controllers.catalog_controller import (
    CategoryController,
    BrandController,
    AttributeController,
    ColorController,
    SizeController
)

catalog_bp = Blueprint('catalog', __name__)

# Category Routes
@catalog_bp.route('/categories', methods=['POST'])
def create_category():
    return CategoryController.create_category(request)

@catalog_bp.route('/categories', methods=['GET'])
def get_categories():
    return CategoryController.get_categories(request)

@catalog_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    return CategoryController.get_category(category_id)

@catalog_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    return CategoryController.update_category(category_id, request)

@catalog_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    return CategoryController.delete_category(category_id)

# Brand Routes
@catalog_bp.route('/brands', methods=['POST'])
def create_brand():
    return BrandController.create_brand(request)

@catalog_bp.route('/brands', methods=['GET'])
def get_brands():
    return BrandController.get_brands(request)

@catalog_bp.route('/brands/<int:brand_id>', methods=['GET'])
def get_brand(brand_id):
    return BrandController.get_brand(brand_id)

@catalog_bp.route('/brands/<int:brand_id>', methods=['PUT'])
def update_brand(brand_id):
    return BrandController.update_brand(brand_id, request)

@catalog_bp.route('/brands/<int:brand_id>', methods=['DELETE'])
def delete_brand(brand_id):
    return BrandController.delete_brand(brand_id)

# Attribute Routes
@catalog_bp.route('/attributes', methods=['POST'])
def create_attribute():
    return AttributeController.create_attribute(request)

@catalog_bp.route('/attributes', methods=['GET'])
def get_attributes():
    return AttributeController.get_attributes(request)

@catalog_bp.route('/attributes/<int:attribute_id>', methods=['GET'])
def get_attribute(attribute_id):
    return AttributeController.get_attribute(attribute_id)

@catalog_bp.route('/attributes/<int:attribute_id>', methods=['PUT'])
def update_attribute(attribute_id):
    return AttributeController.update_attribute(attribute_id, request)

@catalog_bp.route('/attributes/<int:attribute_id>', methods=['DELETE'])
def delete_attribute(attribute_id):
    return AttributeController.delete_attribute(attribute_id)

# Color Routes
@catalog_bp.route('/colors', methods=['POST'])
def create_color():
    return ColorController.create_color(request)

@catalog_bp.route('/colors', methods=['GET'])
def get_colors():
    return ColorController.get_colors(request)

@catalog_bp.route('/colors/<int:color_id>', methods=['GET'])
def get_color(color_id):
    return ColorController.get_color(color_id)

@catalog_bp.route('/colors/<int:color_id>', methods=['PUT'])
def update_color(color_id):
    return ColorController.update_color(color_id, request)

@catalog_bp.route('/colors/<int:color_id>', methods=['DELETE'])
def delete_color(color_id):
    return ColorController.delete_color(color_id)

@catalog_bp.route('/colors/<int:color_id>/approve', methods=['POST'])
def approve_color(color_id):
    return ColorController.approve_color(color_id)

# Size Routes
@catalog_bp.route('/sizes', methods=['POST'])
def create_size():
    return SizeController.create_size(request)

@catalog_bp.route('/sizes', methods=['GET'])
def get_sizes():
    return SizeController.get_sizes(request)

@catalog_bp.route('/sizes/<int:size_id>', methods=['GET'])
def get_size(size_id):
    return SizeController.get_size(size_id)

@catalog_bp.route('/sizes/<int:size_id>', methods=['PUT'])
def update_size(size_id):
    return SizeController.update_size(size_id, request)

@catalog_bp.route('/sizes/<int:size_id>', methods=['DELETE'])
def delete_size(size_id):
    return SizeController.delete_size(size_id) 