from flask import request, jsonify
from common.database import db
from models.shop.shop import Shop
from sqlalchemy import desc, or_
from datetime import datetime, timezone

class PublicShopController:
    @staticmethod
    def get_all_shops():
        """Get all active shops for public display"""
        try:
            shops = Shop.query.filter(
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).order_by(Shop.name).all()

            shop_data = []
            for shop in shops:
                shop_dict = shop.serialize()
                shop_data.append(shop_dict)

            return jsonify({
                'success': True,
                'shops': shop_data,
                'total': len(shop_data)
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching shops: {str(e)}'
            }), 500

    @staticmethod
    def get_shop_by_id(shop_id):
        """Get shop details by ID for public display"""
        try:
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

            return jsonify({
                'success': True,
                'shop': shop.serialize()
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching shop: {str(e)}'
            }), 500

    @staticmethod
    def get_shop_by_slug(slug):
        """Get shop details by slug for public display"""
        try:
            shop = Shop.query.filter(
                Shop.slug == slug,
                Shop.deleted_at.is_(None),
                Shop.is_active.is_(True)
            ).first()

            if not shop:
                return jsonify({
                    'success': False,
                    'message': 'Shop not found or not active'
                }), 404

            return jsonify({
                'success': True,
                'shop': shop.serialize()
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching shop: {str(e)}'
            }), 500
