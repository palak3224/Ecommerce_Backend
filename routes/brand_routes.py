from flask import Blueprint
from controllers.brand_controller import BrandController
from flask_cors import cross_origin

brand_bp = Blueprint('brand', __name__)

@brand_bp.route('/', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_all_brands():
    """Get all brands with optional search"""
    return BrandController.get_all_brands()

@brand_bp.route('/<int:brand_id>', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_brand(brand_id):
    """Get a single brand by ID"""
    return BrandController.get_brand(brand_id)

@brand_bp.route('/icons', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_brand_icons():
    """Get only brand icons and basic info"""
    return BrandController.get_brand_icons()
