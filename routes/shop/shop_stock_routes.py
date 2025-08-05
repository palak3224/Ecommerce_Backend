from flask import Blueprint, request, jsonify, current_app
from controllers.shop.shop_stock_controller import ShopStockController
from flask_cors import cross_origin
from common.decorators import superadmin_required
from http import HTTPStatus
import logging

logger = logging.getLogger(__name__)

shop_stock_bp = Blueprint('shop_stock', __name__)

# Individual Product Stock Management
@shop_stock_bp.route('/api/shop/products/<int:product_id>/stock', methods=['GET'])
@cross_origin()
def get_product_stock(product_id):
    """
    Get stock information for a shop product
    ---
    tags:
      - Shop Stock Management
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
        description: Shop Product ID
    responses:
      200:
        description: Product stock information
        schema:
          type: object
          properties:
            product:
              type: object
              properties:
                product_id:
                  type: integer
                product_name:
                  type: string
                sku:
                  type: string
                shop_id:
                  type: integer
            stock:
              type: object
              properties:
                product_id:
                  type: integer
                stock_qty:
                  type: integer
                low_stock_threshold:
                  type: integer
            available:
              type: boolean
            low_stock:
              type: boolean
      404:
        description: Product not found
      500:
        description: Internal server error
    """
    try:
        stock_info = ShopStockController.get(product_id)
        return jsonify(stock_info), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting shop product stock for product {product_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get product stock."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/products/<int:product_id>/stock', methods=['PUT'])
@cross_origin()
@superadmin_required
def update_product_stock(product_id):
    """
    Update stock information for a shop product
    ---
    tags:
      - Shop Stock Management
    security:
      - Bearer: []
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
        description: Shop Product ID
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              stock_qty:
                type: integer
                description: New stock quantity
              low_stock_threshold:
                type: integer
                description: Threshold for low stock warning
    responses:
      200:
        description: Stock information updated successfully
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            sku:
              type: string
            shop_id:
              type: integer
            stock_qty:
              type: integer
            low_stock_threshold:
              type: integer
            available:
              type: boolean
            low_stock:
              type: boolean
      400:
        description: Bad request
      404:
        description: Product not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), HTTPStatus.BAD_REQUEST
        
        updated_stock = ShopStockController.update(product_id, data)
        return jsonify(updated_stock), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error updating shop product stock for product {product_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to update product stock."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/products/<int:product_id>/stock/bulk-update', methods=['POST'])
@cross_origin()
@superadmin_required
def bulk_update_product_stock(product_id):
    """
    Bulk update stock information for a shop product and its variants
    ---
    tags:
      - Shop Stock Management
    security:
      - Bearer: []
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
        description: Shop Product ID
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: array
            items:
              type: object
              properties:
                variant_id:
                  type: integer
                  description: Variant product ID
                stock_qty:
                  type: integer
                  description: New stock quantity
                low_stock_threshold:
                  type: integer
                  description: Threshold for low stock warning
    responses:
      200:
        description: Stock information updated successfully
        schema:
          type: array
          items:
            type: object
            properties:
              variant_id:
                type: integer
              stock:
                type: object
              available:
                type: boolean
              low_stock:
                type: boolean
      400:
        description: Bad request
      404:
        description: Product not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({'message': 'Data must be a list of stock updates'}), HTTPStatus.BAD_REQUEST
        
        results = ShopStockController.bulk_update(product_id, data)
        return jsonify(results), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error bulk updating shop product stock for product {product_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to bulk update product stock."}), HTTPStatus.INTERNAL_SERVER_ERROR

# Shop Inventory Management
@shop_stock_bp.route('/api/shop/<int:shop_id>/inventory/stats', methods=['GET'])
@cross_origin()
@superadmin_required
def get_shop_inventory_stats(shop_id):
    """
    Get inventory statistics for a specific shop
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
    responses:
      200:
        description: Shop inventory statistics
        schema:
          type: object
          properties:
            total_products:
              type: integer
            total_stock:
              type: integer
            low_stock_count:
              type: integer
            out_of_stock_count:
              type: integer
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        stats = ShopStockController.get_inventory_stats(shop_id)
        return jsonify(stats), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting inventory stats for shop {shop_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get inventory stats."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/<int:shop_id>/inventory/products', methods=['GET'])
@cross_origin()
@superadmin_required
def get_shop_inventory_products(shop_id):
    """
    Get products with stock information for a specific shop
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
      - name: page
        in: query
        type: integer
        description: Page number
      - name: per_page
        in: query
        type: integer
        description: Items per page
      - name: search
        in: query
        type: string
        description: Search term for product name or SKU
      - name: category
        in: query
        type: string
        description: Category ID or slug
      - name: brand
        in: query
        type: string
        description: Brand ID or slug
      - name: stock_status
        in: query
        type: string
        enum: [in_stock, low_stock, out_of_stock]
        description: Filter by stock status
    responses:
      200:
        description: Shop products with stock information
        schema:
          type: object
          properties:
            products:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  sku:
                    type: string
                  shop_id:
                    type: integer
                  stock_qty:
                    type: integer
                  low_stock_threshold:
                    type: integer
                  available:
                    type: integer
                  is_published:
                    type: boolean
                  active_flag:
                    type: boolean
            pagination:
              type: object
              properties:
                total:
                  type: integer
                current_page:
                  type: integer
                per_page:
                  type: integer
                pages:
                  type: integer
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search')
        category = request.args.get('category')
        brand = request.args.get('brand')
        stock_status = request.args.get('stock_status')
        
        products = ShopStockController.get_products(
            shop_id=shop_id,
            page=page,
            per_page=per_page,
            search=search,
            category=category,
            brand=brand,
            stock_status=stock_status
        )
        return jsonify(products), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting inventory products for shop {shop_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get inventory products."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/<int:shop_id>/inventory/low-stock', methods=['GET'])
@cross_origin()
@superadmin_required
def get_shop_low_stock_products(shop_id):
    """
    Get low stock products for a specific shop
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
    responses:
      200:
        description: Low stock products
        schema:
          type: array
          items:
            type: object
            properties:
              product:
                type: object
              stock:
                type: object
              available:
                type: boolean
              low_stock:
                type: boolean
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        low_stock_products = ShopStockController.get_low_stock(shop_id)
        return jsonify(low_stock_products), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting low stock products for shop {shop_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get low stock products."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/<int:shop_id>/inventory/summary', methods=['GET'])
@cross_origin()
@superadmin_required
def get_shop_stock_summary(shop_id):
    """
    Get a comprehensive summary of stock information for a shop
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
    responses:
      200:
        description: Shop stock summary
        schema:
          type: object
          properties:
            shop:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                description:
                  type: string
            inventory_stats:
              type: object
              properties:
                total_products:
                  type: integer
                total_stock:
                  type: integer
                low_stock_count:
                  type: integer
                out_of_stock_count:
                  type: integer
            low_stock_products:
              type: array
            low_stock_count:
              type: integer
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        summary = ShopStockController.get_shop_stock_summary(shop_id)
        return jsonify(summary), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting stock summary for shop {shop_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get stock summary."}), HTTPStatus.INTERNAL_SERVER_ERROR

@shop_stock_bp.route('/api/shop/<int:shop_id>/inventory/batch-update', methods=['POST'])
@cross_origin()
@superadmin_required
def batch_update_shop_stock(shop_id):
    """
    Update stock for multiple products in a shop
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    parameters:
      - name: shop_id
        in: path
        type: integer
        required: true
        description: Shop ID
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: array
            items:
              type: object
              properties:
                product_id:
                  type: integer
                  description: Product ID
                stock_qty:
                  type: integer
                  description: New stock quantity
                low_stock_threshold:
                  type: integer
                  description: Threshold for low stock warning
    responses:
      200:
        description: Batch stock update results
        schema:
          type: array
          items:
            type: object
            properties:
              product_id:
                type: integer
              status:
                type: string
                enum: [success, error]
              stock_qty:
                type: integer
              low_stock_threshold:
                type: integer
              available:
                type: boolean
              low_stock:
                type: boolean
              message:
                type: string
      400:
        description: Bad request
      404:
        description: Shop not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({'message': 'Data must be a list of stock updates'}), HTTPStatus.BAD_REQUEST
        
        results = ShopStockController.update_stock_batch(shop_id, data)
        return jsonify(results), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error batch updating stock for shop {shop_id}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to batch update stock."}), HTTPStatus.INTERNAL_SERVER_ERROR

# Global Stock Management (for superadmin)
@shop_stock_bp.route('/api/shop/inventory/low-stock', methods=['GET'])
@cross_origin()
@superadmin_required
def get_all_low_stock_products():
    """
    Get low stock products across all shops
    ---
    tags:
      - Shop Inventory Management
    security:
      - Bearer: []
    responses:
      200:
        description: Low stock products across all shops
        schema:
          type: array
          items:
            type: object
            properties:
              product:
                type: object
              stock:
                type: object
              available:
                type: boolean
              low_stock:
                type: boolean
      500:
        description: Internal server error
    """
    try:
        low_stock_products = ShopStockController.get_low_stock()
        return jsonify(low_stock_products), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error getting all low stock products: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to get low stock products."}), HTTPStatus.INTERNAL_SERVER_ERROR
