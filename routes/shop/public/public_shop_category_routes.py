from flask import Blueprint
from controllers.shop.public.public_shop_category_controller import PublicShopCategoryController
from flask_cors import cross_origin

public_shop_category_bp = Blueprint('public_shop_category', __name__)

@public_shop_category_bp.route('/api/public/shops/<int:shop_id>/categories', methods=['GET'])
@cross_origin()
def get_categories_by_shop(shop_id):
    """
    Get all active categories for a specific shop
    ---
    tags:
      - Public Shop Categories
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
    responses:
      200:
        description: List of categories for the shop
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            categories:
              type: array
              items:
                type: object
                properties:
                  category_id:
                    type: integer
                  name:
                    type: string
                  description:
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
    return PublicShopCategoryController.get_categories_by_shop(shop_id)

@public_shop_category_bp.route('/api/public/shops/<int:shop_id>/categories/<int:category_id>', methods=['GET'])
@cross_origin()
def get_category_by_id(shop_id, category_id):
    """
    Get a specific category from a shop
    ---
    tags:
      - Public Shop Categories
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: path
        name: category_id
        type: integer
        required: true
        description: ID of the category
    responses:
      200:
        description: Category details
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            category:
              type: object
              properties:
                category_id:
                  type: integer
                name:
                  type: string
                description:
                  type: string
                product_count:
                  type: integer
      404:
        description: Shop or category not found
      500:
        description: Internal server error
    """
    return PublicShopCategoryController.get_category_by_id(shop_id, category_id)
