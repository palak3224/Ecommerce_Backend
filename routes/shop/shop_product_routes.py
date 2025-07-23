
from flask import Blueprint
from controllers.shop.shop_product_controller import ShopProductController
from flask_cors import cross_origin
from common.decorators import superadmin_required

shop_product_bp = Blueprint('shop_product', __name__)

@shop_product_bp.route('/api/shop/products', methods=['GET'])
@cross_origin()
def get_products():
    """
    Get all shop products with pagination and filtering
    ---
    tags:
      - Shop Products
    parameters:
      - in: query
        name: page
        type: integer
        description: Page number
      - in: query
        name: per_page
        type: integer
        description: Items per page
      - in: query
        name: sort_by
        type: string
        description: Field to sort by
      - in: query
        name: order
        type: string
        enum: [asc, desc]
        description: Sort order
      - in: query
        name: category_id
        type: integer
        description: Filter by category
      - in: query
        name: brand_id
        type: integer
        description: Filter by brand
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
        description: Search term
    responses:
      200:
        description: A list of shop products
      500:
        description: Internal server error
    """
    return ShopProductController.get_all_products()

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['GET'])
@cross_origin()
def get_product(product_id):
    """
    Get a single shop product by ID
    ---
    tags:
      - Shop Products
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the shop product to retrieve
    responses:
      200:
        description: Shop product details
      404:
        description: Shop product not found
      500:
        description: Internal server error
    """
    return ShopProductController.get_product(product_id)

@shop_product_bp.route('/api/shop/products/<int:product_id>/details', methods=['GET'])
@cross_origin()
@superadmin_required
def get_product_details(product_id):
    """
    Get complete shop product details for editing
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the shop product to retrieve complete details for
    responses:
      200:
        description: Complete shop product details including media, shipping, stock, meta
      404:
        description: Shop product not found
      500:
        description: Internal server error
    """
    return ShopProductController.get_product_details(product_id)

@shop_product_bp.route('/api/shop/products', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product():
    """
    Create a new shop product
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            product_name:
              type: string
            product_description:
              type: string
            sku:
              type: string
            category_id:
              type: integer
            brand_id:
              type: integer
            cost_price:
              type: number
            selling_price:
              type: number
            is_published:
              type: boolean
    responses:
      201:
        description: Shop product created successfully
      400:
        description: Bad request
      401:
        description: Unauthorized
      403:
        description: Forbidden
    """
    return ShopProductController.create_product()

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['PUT'])
@cross_origin()
@superadmin_required
def update_product(product_id):
    """
    Update an existing shop product
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the shop product to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            product_name:
              type: string
            product_description:
              type: string
            sku:
              type: string
            category_id:
              type: integer
            brand_id:
              type: integer
            cost_price:
              type: number
            selling_price:
              type: number
            is_published:
              type: boolean
            active_flag:
              type: boolean
    responses:
      200:
        description: Shop product updated successfully
      400:
        description: Bad request
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Shop product not found
    """
    return ShopProductController.update_product(product_id)

@shop_product_bp.route('/api/shop/products/<int:product_id>', methods=['DELETE'])
@cross_origin()
@superadmin_required
def delete_product(product_id):
    """
    Delete a shop product
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
        description: ID of the shop product to delete
    responses:
      200:
        description: Shop product deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Shop product not found
    """
    return ShopProductController.delete_product(product_id)

@shop_product_bp.route('/api/shop/products/status', methods=['PUT'])
@cross_origin()
@superadmin_required
def update_product_status():
    """
    Update product status (published, active, special offer)
    ---
    tags:
      - Shop Products
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - product_id
            properties:
              product_id:
                type: integer
                description: ID of the product
              is_published:
                type: boolean
                description: Published status
              active_flag:
                type: boolean
                description: Active status
              special_price:
                type: number
                format: float
                description: Special offer price
              special_start:
                type: string
                format: date-time
                description: Special offer start date
              special_end:
                type: string
                format: date-time
                description: Special offer end date
    responses:
      200:
        description: Product status updated successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.update_product_status()

# Multi-step product creation endpoints
@shop_product_bp.route('/api/shop/products/step1', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step1():
    """
    Save basic product information (Step 1)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - shop_id
            - category_id
            - product_name
            - sku
            - cost_price
            - selling_price
          properties:
            shop_id:
              type: integer
            category_id:
              type: integer
            product_name:
              type: string
            sku:
              type: string
            cost_price:
              type: number
            selling_price:
              type: number
            special_price:
              type: number
            special_start:
              type: string
              format: date-time
            special_end:
              type: string
              format: date-time
            brand_id:
              type: integer
            is_on_special_offer:
              type: boolean
            is_published:
              type: boolean
            active_flag:
              type: boolean
    responses:
      201:
        description: Basic product information saved successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
    """
    return ShopProductController.create_product_step1()

@shop_product_bp.route('/api/shop/products/step2', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step2():
    """
    Save product attributes (Step 2)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
            - attributes
          properties:
            product_id:
              type: integer
            attributes:
              type: array
              items:
                type: object
                properties:
                  attribute_id:
                    type: integer
                  value:
                    type: string
    responses:
      200:
        description: Product attributes saved successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.create_product_step2()

@shop_product_bp.route('/api/shop/products/step3', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step3():
    """
    Save product media (Step 3)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
            - media
          properties:
            product_id:
              type: integer
            media:
              type: array
              items:
                type: object
                properties:
                  url:
                    type: string
                  type:
                    type: string
                    enum: [image, video]
                  is_primary:
                    type: boolean
                  file_name:
                    type: string
                  file_size:
                    type: integer
    responses:
      200:
        description: Product media saved successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.create_product_step3()

@shop_product_bp.route('/api/shop/products/step4', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step4():
    """
    Save product shipping information (Step 4)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
          properties:
            product_id:
              type: integer
            weight:
              type: number
            length:
              type: number
            width:
              type: number
            height:
              type: number
            shipping_category:
              type: string
            is_fragile:
              type: boolean
            special_shipping_notes:
              type: string
    responses:
      200:
        description: Product shipping information saved successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.create_product_step4()

@shop_product_bp.route('/api/shop/products/step5', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step5():
    """
    Save product stock information (Step 5)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
          properties:
            product_id:
              type: integer
            stock_quantity:
              type: integer
            low_stock_threshold:
              type: integer
            manage_stock:
              type: boolean
            stock_status:
              type: string
              enum: [in_stock, limited, out_of_stock]
    responses:
      200:
        description: Product stock information saved successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.create_product_step5()

@shop_product_bp.route('/api/shop/products/step6', methods=['POST'])
@cross_origin()
@superadmin_required
def create_product_step6():
    """
    Save product meta information and finalize (Step 6)
    ---
    tags:
      - Shop Products
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
          properties:
            product_id:
              type: integer
            short_desc:
              type: string
            full_desc:
              type: string
            meta_title:
              type: string
            meta_desc:
              type: string
            meta_keywords:
              type: string
    responses:
      200:
        description: Product created successfully
      400:
        description: Invalid input data
      401:
        description: Unauthorized
      403:
        description: Forbidden
      404:
        description: Product not found
    """
    return ShopProductController.create_product_step6()
