from flask import request, jsonify
from common.database import db
from models.shop.shop_brand import ShopBrand
from models.shop.shop import Shop
from sqlalchemy import desc, or_

class PublicShopBrandController:
    @staticmethod
    def get_brands_by_shop(shop_id):
        """Get all active brands for a specific shop"""
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

            # Get active brands for this shop
            brands = ShopBrand.query.filter(
                ShopBrand.shop_id == shop_id,
                ShopBrand.deleted_at.is_(None),
                ShopBrand.is_active.is_(True)
            ).order_by(ShopBrand.name).all()

            brand_data = []
            for brand in brands:
                brand_dict = brand.serialize()
                
                # Count products for this brand
                from models.shop.shop_product import ShopProduct
                product_count = ShopProduct.query.filter(
                    ShopProduct.shop_id == shop_id,
                    ShopProduct.brand_id == brand.brand_id,
                    ShopProduct.deleted_at.is_(None),
                    ShopProduct.active_flag.is_(True),
                    ShopProduct.is_published.is_(True)
                ).count()
                
                brand_dict['product_count'] = product_count
                brand_data.append(brand_dict)

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'brands': brand_data,
                'total': len(brand_data)
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching brands: {str(e)}'
            }), 500

    @staticmethod
    def get_brand_by_id(shop_id, brand_id):
        """Get a specific brand from a shop"""
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

            # Get the brand
            brand = ShopBrand.query.filter(
                ShopBrand.brand_id == brand_id,
                ShopBrand.shop_id == shop_id,
                ShopBrand.deleted_at.is_(None),
                ShopBrand.is_active.is_(True)
            ).first()

            if not brand:
                return jsonify({
                    'success': False,
                    'message': 'Brand not found in this shop'
                }), 404

            brand_dict = brand.serialize()
            
            # Count products for this brand
            from models.shop.shop_product import ShopProduct
            product_count = ShopProduct.query.filter(
                ShopProduct.shop_id == shop_id,
                ShopProduct.brand_id == brand.brand_id,
                ShopProduct.deleted_at.is_(None),
                ShopProduct.active_flag.is_(True),
                ShopProduct.is_published.is_(True)
            ).count()
            
            brand_dict['product_count'] = product_count

            return jsonify({
                'success': True,
                'shop': shop.serialize(),
                'brand': brand_dict
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching brand: {str(e)}'
            }), 500
