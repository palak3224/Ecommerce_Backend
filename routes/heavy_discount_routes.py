from flask import Blueprint, request, jsonify
from controllers.feature_product_controller import FeatureProductController
from flask_cors import cross_origin
from common.cache import cached
from common.response import success_response

heavy_discount_bp = Blueprint('heavy_discount', __name__, url_prefix='/api/heavy-discount-products')

@heavy_discount_bp.route('/', methods=['GET', 'OPTIONS'])
@cross_origin()
@cached(timeout=300, key_prefix='heavy_discount_products')
def get_heavy_discount_products():
    """
    Get the top N products with the highest discount % from all AOIN products (global catalog).
    Same product source as featured-products API; returns products from the whole platform.
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        limit = request.args.get('limit', 4, type=int)
        limit = min(max(1, limit), 20)
        result = FeatureProductController.get_heavy_discount_products(limit=limit)
        return success_response(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500
