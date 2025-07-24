from flask import request, jsonify
from common.database import db
from models.shop.shop_category import ShopCategory
from models.shop.shop import Shop
from sqlalchemy import desc, or_

class PublicShopCategoryController:
    @staticmethod
    def get_categories_by_shop(shop_id):
        """Get all active categories for a specific shop"""
        try:
            # Verify shop exists and is active
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            # Get active categories for this shop
            categories = ShopCategory.query.filter(
                ShopCategory.shop_id == shop_id,
                ShopCategory.deleted_at.is_(None),
                ShopCategory.is_active.is_(True)
            ).order_by(ShopCategory.name).all()

            category_data = []
            for category in categories:
                category_dict = category.serialize()
                
                # Count products in this category
                from models.shop.shop_product import ShopProduct
                product_count = ShopProduct.query.filter(
                    ShopProduct.shop_id == shop_id,
                    ShopProduct.category_id == category.category_id,
                    ShopProduct.deleted_at.is_(None),
                    ShopProduct.active_flag.is_(True),
                    ShopProduct.is_published.is_(True)
                ).count()
                
                category_dict['product_count'] = product_count
                category_data.append(category_dict)

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'categories': category_data,
                'total': len(category_data)
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching categories: {str(e)}'
            }), 500

    @staticmethod
    def get_category_by_id(shop_id, category_id):
        """Get a specific category from a shop"""
        try:
            # Verify shop exists and is active
            shop = Shop.query.filter(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            # Get the category
            category = ShopCategory.query.filter(
                ShopCategory.category_id == category_id,
                ShopCategory.shop_id == shop_id,
                ShopCategory.deleted_at.is_(None),
                ShopCategory.is_active.is_(True)
            ).first()

            if not category:
                return jsonify({
                    'success': False,
                    'message': 'Category not found in this shop'
                }), 404

            category_dict = category.serialize()
            
            # Count products in this category
            from models.shop.shop_product import ShopProduct
            product_count = ShopProduct.query.filter(
                ShopProduct.shop_id == shop_id,
                ShopProduct.category_id == category.category_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)
            ).count()
            
            category_dict['product_count'] = product_count

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'category': category_dict
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching category: {str(e)}'
            }), 500
