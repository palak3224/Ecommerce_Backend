from flask import Blueprint, redirect, url_for
from controllers.categories_controller import CategoriesController
from flask_cors import cross_origin

category_bp = Blueprint('category', __name__)

@category_bp.route('/with-icons', methods=['GET', 'OPTIONS'])
@category_bp.route('/with-icons/', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_categories_with_icons():
    """Get all categories that have icons"""
    return CategoriesController.get_categories_with_icons()

@category_bp.route('/all', methods=['GET', 'OPTIONS'])
@category_bp.route('/all/', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_all_categories():
    """Get all categories with their hierarchical structure"""
    return CategoriesController.get_all_categories()

@category_bp.route('', methods=['GET', 'OPTIONS'])
@category_bp.route('/', methods=['GET', 'OPTIONS'])
@cross_origin()
def search_categories():
    """Search categories by name or slug"""
    return CategoriesController.get_all_categories() 