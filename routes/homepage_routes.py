from flask import Blueprint, request, jsonify, current_app
from controllers.homepage_controller import HomepageController
from flask_cors import cross_origin

homepage_bp = Blueprint('homepage', __name__)

@homepage_bp.route('/products', methods=['GET', 'OPTIONS'])
@homepage_bp.route('/products/', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_homepage_products():
    """
    Get products from categories selected for homepage display (excluding variants)
    ---
    tags:
      - Homepage
    responses:
      200:
        description: List of featured products retrieved successfully (excluding variants)
        schema:
          type: array
          items:
            type: object
            properties:
              product_id:
                type: integer
              product_name:
                type: string
              sku:
                type: string
              cost_price:
                type: number
                format: float
              selling_price:
                type: number
                format: float
              media:
                type: array
                items:
                  type: object
                  properties:
                    url:
                      type: string
                    type:
                      type: string
              brand:
                type: object
                properties:
                  brand_id:
                    type: integer
                  name:
                    type: string
              category:
                type: object
                properties:
                  category_id:
                    type: integer
                  name:
                    type: string
      500:
        description: Internal server error
    """
    return HomepageController.get_homepage_products()

@homepage_bp.route('/carousels', methods=['GET', 'OPTIONS'])
@homepage_bp.route('/carousels/', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_homepage_carousels():
    """
    Get all active carousel items for homepage (optionally filter by type)
    ---
    tags:
      - Homepage
    parameters:
      - in: query
        name: type
        type: string
        required: false
        description: Comma-separated list of carousel types ('brand', 'promo', 'new', 'featured')
    responses:
      200:
        description: List of carousel items retrieved successfully
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              type:
                type: string
              image_url:
                type: string
              link:
                type: string
              title:
                type: string
              is_active:
                type: boolean
      500:
        description: Internal server error
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        carousel_types = request.args.get('type', '').split(',')
        # Remove any empty strings from the list
        carousel_types = [t.strip() for t in carousel_types if t.strip()]
        # Get orientation filter (horizontal or vertical)
        orientation = request.args.get('orientation')
        items = HomepageController.get_homepage_carousels(carousel_types, orientation=orientation)
        return jsonify(items), 200
    except Exception as e:
        current_app.logger.error(
            f"Error fetching homepage carousels: {str(e)}",
            exc_info=True
        )
        return jsonify({
            'message': 'Failed to fetch homepage carousels.',
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
