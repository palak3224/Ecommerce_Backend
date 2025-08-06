from flask import current_app
from common.database import db
from models.shop.shop_product import ShopProduct
from models.shop.shop_product_stock import ShopProductStock
from models.shop.shop_category import ShopCategory
from models.shop.shop_brand import ShopBrand
from models.shop.shop import Shop
from sqlalchemy import or_, desc
import logging

logger = logging.getLogger(__name__)

class ShopStockController:
    @staticmethod
    def get(product_id):
        """Get stock information for a shop product"""
        try:
            # Get product with all its details - only active, non-deleted products
            product = ShopProduct.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).first()
            
            if not product:
                raise Exception("Product not found or has been deleted")
            
            # Get stock information
            stock = ShopProductStock.query.filter_by(product_id=product_id).first()
            
            if not stock:
                stock = ShopProductStock(product_id=product_id)
                db.session.add(stock)
                db.session.commit()
            
            return {
                'product': product.serialize(),
                'stock': stock.serialize(),
                'available': stock.stock_qty > 0,
                'low_stock': stock.stock_qty <= stock.low_stock_threshold
            }
        except Exception as e:
            logger.error(f"Error getting shop product stock: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def update(product_id, data):
        """Update stock information for a shop product"""
        try:
            # Only allow updates for active, non-deleted products
            product = ShopProduct.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).first()
            
            if not product:
                raise Exception("Product not found or has been deleted")
            
            stock = ShopProductStock.query.filter_by(product_id=product_id).first()
            
            if not stock:
                stock = ShopProductStock(product_id=product_id)
                db.session.add(stock)
            
            if 'stock_qty' in data:
                stock.stock_qty = data['stock_qty']
            if 'low_stock_threshold' in data:
                stock.low_stock_threshold = data['low_stock_threshold']
            
            db.session.commit()
            
            return {
                'id': product.product_id,
                'name': product.product_name,
                'sku': product.sku,
                'shop_id': product.shop_id,
                'category': product.category.name if product.category else None,
                'brand': product.brand.name if product.brand else None,
                'stock_qty': stock.stock_qty,
                'low_stock_threshold': stock.low_stock_threshold,
                'available': stock.stock_qty > 0,
                'low_stock': stock.stock_qty <= stock.low_stock_threshold
            }
        except Exception as e:
            logger.error(f"Error updating shop product stock: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def bulk_update(product_id, data):
        """Bulk update stock information for a shop product and its variants"""
        try:
            if not isinstance(data, list):
                raise ValueError("Data must be a list of stock updates")
            
            # Verify parent product exists and is not deleted
            product = ShopProduct.query.filter_by(
                product_id=product_id,
                deleted_at=None
            ).first()
            
            if not product:
                raise Exception("Parent product not found or has been deleted")
            
            results = []
            
            for item in data:
                if not isinstance(item, dict) or 'variant_id' not in item:
                    raise ValueError("Each item must be a dictionary with 'variant_id'")
                
                variant_id = item['variant_id']
                
                # Verify variant product exists and is not deleted
                variant_product = ShopProduct.query.filter_by(
                    product_id=variant_id,
                    deleted_at=None
                ).first()
                
                if not variant_product:
                    results.append({
                        'variant_id': variant_id,
                        'status': 'error',
                        'message': 'Variant product not found or has been deleted'
                    })
                    continue
                
                stock_qty = item.get('stock_qty', 0)
                low_stock_threshold = item.get('low_stock_threshold', 0)
                
                # Update variant stock
                variant_stock = ShopProductStock.query.filter_by(product_id=variant_id).first()
                if not variant_stock:
                    variant_stock = ShopProductStock(product_id=variant_id)
                    db.session.add(variant_stock)
                
                variant_stock.stock_qty = stock_qty
                variant_stock.low_stock_threshold = low_stock_threshold
                
                results.append({
                    'variant_id': variant_id,
                    'stock': variant_stock.serialize(),
                    'available': stock_qty > 0,
                    'low_stock': stock_qty <= low_stock_threshold
                })
            
            db.session.commit()
            return results
        except Exception as e:
            logger.error(f"Error bulk updating shop product stock: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def get_low_stock(shop_id=None):
        """Get low stock products for a specific shop or all shops"""
        try:
            query = db.session.query(ShopProduct, ShopProductStock).\
                join(ShopProductStock).\
                filter(ShopProductStock.stock_qty <= ShopProductStock.low_stock_threshold).\
                filter(ShopProductStock.stock_qty > 0).\
                filter(ShopProduct.deleted_at.is_(None))  # Only non-deleted products
            
            if shop_id:
                query = query.filter(ShopProduct.shop_id == shop_id)
            
            low_stock_products = query.all()
            
            return [{
                'product': product.serialize(),
                'stock': stock.serialize(),
                'available': stock.stock_qty > 0,
                'low_stock': True
            } for product, stock in low_stock_products]
        except Exception as e:
            logger.error(f"Error getting low stock products: {e}")
            raise

    @staticmethod
    def get_inventory_stats(shop_id):
        """Get inventory statistics for a specific shop"""
        try:
            logger.info(f"Fetching inventory stats for shop ID: {shop_id}")

            # Only count active, non-deleted products
            total_products = ShopProduct.query.filter_by(
                shop_id=shop_id,
                deleted_at=None
            ).count()
            
            total_stock = db.session.query(db.func.sum(ShopProductStock.stock_qty)).\
                join(ShopProduct).\
                filter(ShopProduct.shop_id == shop_id).\
                filter(ShopProduct.deleted_at.is_(None)).\
                scalar() or 0
            
            low_stock_count = db.session.query(ShopProduct).\
                join(ShopProductStock).\
                filter(ShopProduct.shop_id == shop_id).\
                filter(ShopProduct.deleted_at.is_(None)).\
                filter(ShopProductStock.stock_qty <= ShopProductStock.low_stock_threshold).\
                filter(ShopProductStock.stock_qty > 0).\
                count()
            
            out_of_stock_count = db.session.query(ShopProduct).\
                join(ShopProductStock).\
                filter(ShopProduct.shop_id == shop_id).\
                filter(ShopProduct.deleted_at.is_(None)).\
                filter(ShopProductStock.stock_qty == 0).\
                count()
            
            return {
                'total_products': total_products,
                'total_stock': total_stock,
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count
            }
        except Exception as e:
            logger.error(f"Error getting inventory stats: {e}")
            raise

    @staticmethod
    def get_products(shop_id, page=1, per_page=10, search=None, category=None, brand=None, stock_status=None):
        """Get products with stock information for a specific shop"""
        try:
            logger.info(f"Fetching products for shop ID: {shop_id}")

            # Base query - only active, non-deleted products
            query = ShopProduct.query.filter_by(
                shop_id=shop_id,
                deleted_at=None
            )
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(or_(
                    ShopProduct.product_name.ilike(search_term),
                    ShopProduct.sku.ilike(search_term)
                ))
            
            if category:
                # Handle both category ID and slug
                try:
                    category_id = int(category)
                    query = query.filter(ShopProduct.category_id == category_id)
                except ValueError:
                    # If category is not a number, treat it as a slug
                    category_obj = ShopCategory.query.filter_by(slug=category, shop_id=shop_id).first()
                    if category_obj:
                        query = query.filter(ShopProduct.category_id == category_obj.category_id)
            
            if brand:
                # Handle both brand ID and slug
                try:
                    brand_id = int(brand)
                    query = query.filter(ShopProduct.brand_id == brand_id)
                except ValueError:
                    # If brand is not a number, treat it as a slug
                    brand_obj = ShopBrand.query.filter_by(slug=brand, shop_id=shop_id).first()
                    if brand_obj:
                        query = query.filter(ShopProduct.brand_id == brand_obj.brand_id)
            
            if stock_status:
                query = query.join(ShopProductStock)
                if stock_status == 'in_stock':
                    query = query.filter(ShopProductStock.stock_qty > 0)
                elif stock_status == 'low_stock':
                    query = query.filter(ShopProductStock.stock_qty <= ShopProductStock.low_stock_threshold)
                    query = query.filter(ShopProductStock.stock_qty > 0)
                elif stock_status == 'out_of_stock':
                    query = query.filter(ShopProductStock.stock_qty == 0)
            
            # Get total count before pagination
            total = query.count()
            
            # Apply pagination
            products = query.order_by(desc(ShopProduct.created_at)).\
                offset((page - 1) * per_page).\
                limit(per_page).\
                all()
            
            # Format products for frontend
            formatted_products = []
            for product in products:
                stock = ShopProductStock.query.filter_by(product_id=product.product_id).first()
                if not stock:
                    stock = ShopProductStock(product_id=product.product_id)
                    db.session.add(stock)
                    db.session.commit()
                
                formatted_products.append({
                    'id': product.product_id,
                    'name': product.product_name,
                    'sku': product.sku,
                    'shop_id': product.shop_id,
                    'category': {
                        'id': product.category.category_id if product.category else None,
                        'name': product.category.name if product.category else None,
                        'slug': product.category.slug if product.category else None
                    },
                    'brand': {
                        'id': product.brand.brand_id if product.brand else None,
                        'name': product.brand.name if product.brand else None,
                        'slug': product.brand.slug if product.brand else None
                    },
                    'stock_qty': stock.stock_qty if stock else 0,
                    'low_stock_threshold': stock.low_stock_threshold if stock else 0,
                    'available': stock.stock_qty if stock else 0,
                    'is_published': product.is_published,
                    'active_flag': product.active_flag
                })
            
            return {
                'products': formatted_products,
                'pagination': {
                    'total': total,
                    'current_page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        except Exception as e:
            logger.error(f"Error listing shop inventory products: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def get_shop_stock_summary(shop_id):
        """Get a summary of stock information for a shop"""
        try:
            # Get shop information
            shop = Shop.query.get_or_404(shop_id)
            
            # Get inventory stats
            stats = ShopStockController.get_inventory_stats(shop_id)
            
            # Get low stock products
            low_stock_products = ShopStockController.get_low_stock(shop_id)
            
            return {
                'shop': {
                    'id': shop.shop_id,
                    'name': shop.shop_name,
                    'description': shop.description
                },
                'inventory_stats': stats,
                'low_stock_products': low_stock_products,
                'low_stock_count': len(low_stock_products)
            }
        except Exception as e:
            logger.error(f"Error getting shop stock summary: {e}")
            raise

    @staticmethod
    def update_stock_batch(shop_id, stock_updates):
        """Update stock for multiple products in a shop"""
        try:
            if not isinstance(stock_updates, list):
                raise ValueError("stock_updates must be a list")
            
            results = []
            for update in stock_updates:
                if not isinstance(update, dict) or 'product_id' not in update:
                    raise ValueError("Each update must be a dictionary with 'product_id'")
                
                product_id = update['product_id']
                stock_qty = update.get('stock_qty', 0)
                low_stock_threshold = update.get('low_stock_threshold', 5)
                
                # Verify product belongs to shop and is not deleted
                product = ShopProduct.query.filter_by(
                    product_id=product_id, 
                    shop_id=shop_id,
                    deleted_at=None
                ).first()
                
                if not product:
                    results.append({
                        'product_id': product_id,
                        'status': 'error',
                        'message': 'Product not found in this shop or has been deleted'
                    })
                    continue
                
                # Update stock
                stock = ShopProductStock.query.filter_by(product_id=product_id).first()
                if not stock:
                    stock = ShopProductStock(product_id=product_id)
                    db.session.add(stock)
                
                stock.stock_qty = stock_qty
                stock.low_stock_threshold = low_stock_threshold
                
                results.append({
                    'product_id': product_id,
                    'status': 'success',
                    'stock_qty': stock_qty,
                    'low_stock_threshold': low_stock_threshold,
                    'available': stock_qty > 0,
                    'low_stock': stock_qty <= low_stock_threshold
                })
            
            db.session.commit()
            return results
        except Exception as e:
            logger.error(f"Error updating stock batch: {e}")
            db.session.rollback()
            raise
