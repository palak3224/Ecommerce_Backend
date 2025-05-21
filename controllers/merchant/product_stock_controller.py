from flask import Blueprint, request, jsonify, abort
from common.database import db
from models.product_stock import ProductStock
from models.product import Product
from auth.models.models import MerchantProfile
from flask_jwt_extended import get_jwt_identity

product_stock_bp = Blueprint('product_stock', __name__)

class MerchantProductStockController:
    @staticmethod
    def get(pid):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        product = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        stock = ProductStock.query.filter_by(product_id=pid).first()
        if not stock:
            stock = ProductStock(product_id=pid)
            db.session.add(stock)
            db.session.commit()
        return stock

    @staticmethod
    def update(pid, data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        product = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        stock = ProductStock.query.filter_by(product_id=pid).first()
        if not stock:
            stock = ProductStock(product_id=pid)
            db.session.add(stock)

        if 'stock_qty' in data:
            if not isinstance(data['stock_qty'], int) or data['stock_qty'] < 0:
                abort(400, "Invalid stock quantity")
            stock.stock_qty = data['stock_qty']

        if 'low_stock_threshold' in data:
            if not isinstance(data['low_stock_threshold'], int) or data['low_stock_threshold'] < 0:
                abort(400, "Invalid low stock threshold")
            stock.low_stock_threshold = data['low_stock_threshold']

        db.session.commit()
        return stock

    @staticmethod
    def bulk_update(pid, data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        if not isinstance(data, list):
            abort(400, "Invalid data format")

        results = []
        for item in data:
            if not isinstance(item, dict) or 'product_id' not in item or 'stock_qty' not in item:
                continue

            product = Product.query.filter_by(
                product_id=item['product_id'],
                merchant_id=merchant.id
            ).first()

            if not product:
                continue

            stock = ProductStock.query.filter_by(product_id=item['product_id']).first()
            if not stock:
                stock = ProductStock(product_id=item['product_id'])
                db.session.add(stock)

            if not isinstance(item['stock_qty'], int) or item['stock_qty'] < 0:
                continue

            stock.stock_qty = item['stock_qty']
            if 'low_stock_threshold' in item and isinstance(item['low_stock_threshold'], int):
                stock.low_stock_threshold = item['low_stock_threshold']

            results.append(stock)

        db.session.commit()
        return results

    @staticmethod
    def get_low_stock():
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        products = Product.query.filter_by(merchant_id=merchant.id).all()
        product_ids = [p.product_id for p in products]

        low_stock = ProductStock.query.filter(
            ProductStock.product_id.in_(product_ids),
            ProductStock.stock_qty <= ProductStock.low_stock_threshold
        ).all()

        return low_stock

@product_stock_bp.route('/api/merchant-dashboard/products/<int:product_id>/stock', methods=['GET'])
def get_product_stock(product_id):
    """Get stock information for a specific product."""
    try:
        stock = MerchantProductStockController.get(product_id)
        return success_response(stock.serialize())

    except Exception as e:
        return error_response(str(e), 500)

@product_stock_bp.route('/api/merchant-dashboard/products/<int:product_id>/stock', methods=['PUT'])
def update_product_stock(product_id):
    """Update stock information for a specific product."""
    try:
        data = request.get_json()
        if not data:
            return error_response('No data provided', 400)

        stock = MerchantProductStockController.update(product_id, data)
        return success_response(stock.serialize())

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@product_stock_bp.route('/api/merchant-dashboard/products/<int:product_id>/stock/bulk-update', methods=['POST'])
def bulk_update_product_stock(product_id):
    """Bulk update stock information for multiple products."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, list):
            return error_response('Invalid data format', 400)

        results = MerchantProductStockController.bulk_update(product_id, data)
        return success_response([stock.serialize() for stock in results])

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@product_stock_bp.route('/api/merchant-dashboard/products/stock/low-stock', methods=['GET'])
def get_low_stock_products():
    """Get all products with stock below their threshold."""
    try:
        low_stock = MerchantProductStockController.get_low_stock()
        return success_response([stock.serialize() for stock in low_stock])

    except Exception as e:
        return error_response(str(e), 500) 