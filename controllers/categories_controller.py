from flask import jsonify, request
from models.category import Category
from common.database import db
from sqlalchemy import or_

class CategoriesController:
    @staticmethod
    def get_categories_with_icons():
        """Get all categories that have icons"""
        try:
            # Query categories that have an icon_url
            categories = Category.query.filter(
                Category.icon_url.isnot(None),
                Category.icon_url != ''
            ).all()
            
            # Serialize the categories
            categories_data = [category.serialize() for category in categories]
            
            return jsonify(categories_data)
        except Exception as e:
            print(f"Error fetching categories: {str(e)}")
            return jsonify([]), 500

    @staticmethod
    def get_all_categories():
        """Get all categories with their hierarchical structure"""
        try:
            # Get search parameter
            search = request.args.get('search', '')
            per_page = min(request.args.get('per_page', 50, type=int), 50)

            # Base query
            query = Category.query

            # Apply search filter if search term exists
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Category.name.ilike(search_term),
                        Category.slug.ilike(search_term)
                    )
                )

            # Get categories
            categories = query.limit(per_page).all()
            
            # Create a map of all categories
            category_map = {category.category_id: category.serialize() for category in categories}
            
            # Organize categories into hierarchy
            root_categories = []
            for category in categories:
                serialized_category = category_map[category.category_id]
                if category.parent_id is None:
                    # This is a root category
                    root_categories.append(serialized_category)
                else:
                    # This is a child category
                    parent = category_map.get(category.parent_id)
                    if parent:
                        if 'children' not in parent:
                            parent['children'] = []
                        parent['children'].append(serialized_category)
            
            return jsonify(root_categories)
        except Exception as e:
            print(f"Error fetching categories hierarchy: {str(e)}")
            return jsonify([]), 500
