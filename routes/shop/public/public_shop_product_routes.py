from flask import Blueprint
from controllers.shop.public.public_shop_product_controller import PublicShopProductController
from flask_cors import cross_origin

public_shop_product_bp = Blueprint('public_shop_product', __name__)

@public_shop_product_bp.route('/api/public/shops/<int:shop_id>/products', methods=['GET'])
@cross_origin()
def get_products_by_shop(shop_id):
    """
    Get all published products for a specific shop with pagination and filtering
    ---
    tags:
      - Public Shop Products
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: query
        name: page
        type: integer
        description: Page number (default: 1)
      - in: query
        name: per_page
        type: integer
        description: Items per page (default: 20, max: 50)
      - in: query
        name: sort_by
        type: string
        enum: [created_at, product_name, selling_price, special_price]
        description: Field to sort by (default: created_at)
      - in: query
        name: order
        type: string
        enum: [asc, desc]
        description: Sort order (default: desc)
      - in: query
        name: category_id
        type: integer
        description: Filter by category ID
      - in: query
        name: brand_id
        type: integer
        description: Filter by brand ID
      - in: query
        name: min_price
        type: number
        description: Minimum price filter
      - in: query
        name: max_price
        type: number
        description: Maximum price filter
      - in: query
        name: search
        type: string
        description: Search term for product name, description, SKU, category, or brand
    responses:
      200:
        description: List of products for the shop
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            products:
              type: array
              items:
                type: object
            pagination:
              type: object
            filters_applied:
              type: object
      404:
        description: Shop not found or not active
      500:
        description: Internal server error
    """
    return PublicShopProductController.get_products_by_shop(shop_id)

@public_shop_product_bp.route('/api/public/shops/<int:shop_id>/products/<int:product_id>', methods=['GET'])
@cross_origin()
def get_product_by_id(shop_id, product_id):
    """
    Get a specific product from a shop with full details
    ---
    tags:
      - Public Shop Products
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the product
    responses:
      200:
        description: Product details with related products
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            product:
              type: object
            related_products:
              type: array
              items:
                type: object
      404:
        description: Shop or product not found
      500:
        description: Internal server error
    """
    return PublicShopProductController.get_product_by_id(shop_id, product_id)

@public_shop_product_bp.route('/api/public/shops/<int:shop_id>/products/featured', methods=['GET'])
@cross_origin()
def get_featured_products(shop_id):
    """
    Get featured/latest products for a shop
    ---
    tags:
      - Public Shop Products
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: query
        name: limit
        type: integer
        description: Number of featured products to return (default: 8, max: 20)
    responses:
      200:
        description: List of featured products
        schema:
          type: object
          properties:
            success:
              type: boolean
            shop:
              type: object
            featured_products:
              type: array
              items:
                type: object
            total:
              type: integer
      404:
        description: Shop not found or not active
      500:
        description: Internal server error
    """
    return PublicShopProductController.get_featured_products(shop_id)

@public_shop_product_bp.route('/api/public/shops/<int:shop_id>/products/<int:product_id>/media', methods=['GET'])
@cross_origin()
def get_product_media_gallery(shop_id, product_id):
    """
    Get optimized media gallery for a specific product (for image carousels, zoom views, etc.)
    ---
    tags:
      - Public Shop Products
    parameters:
      - in: path
        name: shop_id
        type: integer
        required: true
        description: ID of the shop
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the product
    responses:
      200:
        description: Optimized media gallery with only essential fields (90% smaller payload)
        schema:
          type: object
          properties:
            success:
              type: boolean
            product_id:
              type: integer
            product_name:
              type: string
            media:
              type: object
              properties:
                images:
                  type: array
                  items:
                    type: object
                    properties:
                      url:
                        type: string
                        description: Direct image URL
                      type:
                        type: string
                        enum: [image]
                      is_primary:
                        type: boolean
                videos:
                  type: array
                  items:
                    type: object
                    properties:
                      url:
                        type: string
                        description: Direct video URL
                      type:
                        type: string
                        enum: [video]
                      is_primary:
                        type: boolean
                primary_image:
                  type: string
                  description: URL of the primary image
                total_media:
                  type: integer
                  description: Total number of media items
        examples:
          response:
            success: true
            product_id: 123
            product_name: "Sample Product"
            media:
              images:
                - url: "https://cdn.example.com/image1.jpg"
                  type: "image"
                  is_primary: true
                - url: "https://cdn.example.com/image2.jpg"
                  type: "image"
                  is_primary: false
              videos:
                - url: "https://cdn.example.com/video1.mp4"
                  type: "video"
                  is_primary: false
              primary_image: "https://cdn.example.com/image1.jpg"
              total_media: 3
      404:
        description: Shop or product not found
      500:
        description: Internal server error
    """
    return PublicShopProductController.get_product_media_gallery(shop_id, product_id)
