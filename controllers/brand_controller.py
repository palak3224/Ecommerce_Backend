from flask import jsonify, request
from models.brand import Brand
from common.database import db
from sqlalchemy import or_

class BrandController:
    @staticmethod
    def get_all_brands():
        """Get all brands with optional search"""
        try:
            # Get search parameter
            search = request.args.get('search', '')
            per_page = min(request.args.get('per_page', 50, type=int), 50)

            # Base query
            query = Brand.query

            # Apply search filter if search term exists
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Brand.name.ilike(search_term),
                        Brand.slug.ilike(search_term)
                    )
                )

            # Get brands
            brands = query.limit(per_page).all()
            
            # Serialize the brands
            brands_data = [brand.serialize() for brand in brands]
            
            return jsonify(brands_data)
        except Exception as e:
            print(f"Error fetching brands: {str(e)}")
            return jsonify([]), 500

    @staticmethod
    def get_brand(brand_id):
        """Get a single brand by ID"""
        try:
            brand = Brand.query.get(brand_id)
            if not brand:
                return jsonify({'error': 'Brand not found'}), 404
            
            return jsonify(brand.serialize())
        except Exception as e:
            print(f"Error fetching brand: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
