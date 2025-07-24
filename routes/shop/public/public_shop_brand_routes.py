from flask import Blueprint
from controllers.shop.public.public_shop_brand_controller import PublicShopBrandController
from flask_cors import cross_origin

public_shop_brand_bp = Blueprint('public_shop_brand', __name__)

@public_shop_brand_bp.route('/api/public/shops/<int:shop_id>/brands', methods=['GET'])
@cross_origin()
def get_brands_by_shop(shop_id):
    """
    Get all active brands for a specific shop
    ---
    tags:
      - Public Shop Brands
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
    responses:
      200:
        description: List of brands for the shop
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            brands:
              type: array
              items:
                type: object
                properties:
                  brand_id:
                    type: integer
                  name:
                    type: string
                  description:
                    type: string
                  logo_url:
                    type: string
                  product_count:
                    type: integer
            total:
              type: integer
      404:
        description: Shop not found or not active
      500:
        description: Internal server error
    """
    return PublicShopBrandController.get_brands_by_shop(shop_id)

@public_shop_brand_bp.route('/api/public/shops/<int:shop_id>/brands/<int:brand_id>', methods=['GET'])
@cross_origin()
def get_brand_by_id(shop_id, brand_id):
    """
    Get a specific brand from a shop
    ---
    tags:
      - Public Shop Brands
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: path
        name: brand_id
        type: integer
        required: true
        description: ID of the brand
    responses:
      200:
        description: Brand details
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            brand:
              type: object
              properties:
                brand_id:
                  type: integer
                name:
                  type: string
                description:
                  type: string
                logo_url:
                  type: string
                product_count:
                  type: integer
      404:
        description: Shop or brand not found
      500:
        description: Internal server error
    """
    return PublicShopBrandController.get_brand_by_id(shop_id, brand_id)
