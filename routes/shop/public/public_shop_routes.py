from flask import Blueprint
from controllers.shop.public.public_shop_controller import PublicShopController
from flask_cors import cross_origin

public_shop_bp = Blueprint('public_shop', __name__)

@public_shop_bp.route('/api/public/shops', methods=['GET'])
@cross_origin()
def get_all_shops():
    """
    Get all active shops for public display
    ---
    tags:
      - Public Shops
    responses:
      200:
        description: A list of all active shops
        schema:
          type: object
          properties:
            success:
              type: boolean
            shops:
              type: array
              items:
                type: object
            total:
              type: integer
      500:
        description: Internal server error
    """
    return PublicShopController.get_all_shops()

@public_shop_bp.route('/api/public/shops/<int:shop_id>', methods=['GET'])
@cross_origin()
def get_shop_by_id(shop_id):
    """
    Get shop details by ID for public display
    ---
    tags:
      - Public Shops
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop to retrieve
    responses:
      200:
        description: Shop details
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
      404:
        description: Shop not found or not active
      500:
        description: Internal server error
    """
    return PublicShopController.get_shop_by_id(shop_id)

@public_shop_bp.route('/api/public/shops/slug/<string:slug>', methods=['GET'])
@cross_origin()
def get_shop_by_slug(slug):
    """
    Get shop details by slug for public display
    ---
    tags:
      - Public Shops
    parameters:
      - in: path
        name: slug
        type: string
        required: true
        description: Slug of the shop to retrieve
    responses:
      200:
        description: Shop details
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
      404:
        description: Shop not found or not active
      500:
        description: Internal server error
    """
    return PublicShopController.get_shop_by_slug(slug)
