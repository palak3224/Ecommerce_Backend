from flask import jsonify, current_app, request
from models.shop.shop_cart import ShopCart, ShopCartItem
from models.shop.shop_product import ShopProduct
from models.shop.shop_product_stock import ShopProductStock
from models.shop.shop_product_media import ShopProductMedia
from common.database import db
from sqlalchemy import and_
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PublicShopCartController:
    @staticmethod
    def get_cart_items(user_id: int, shop_id: int):
        """
        Get all cart items for a user in a specific shop
        """
        try:
            # Get the user's cart for the specific shop
            cart = ShopCart.query.filter_by(user_id=user_id, shop_id=shop_id).first()
            
            if not cart:
                # Create a new cart if it doesn't exist
                cart = ShopCart(user_id=user_id, shop_id=shop_id)
                db.session.add(cart)
                db.session.commit()
                return []

            # Get all cart items with their associated shop products
            cart_items = ShopCartItem.query.filter_by(cart_id=cart.cart_id).all()
            
            return cart_items
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cart(user_id: int, shop_id: int):
        """
        Get or create a cart for a user in a specific shop
        """
        try:
            cart = ShopCart.query.filter_by(user_id=user_id, shop_id=shop_id).first()
            
            if not cart:
                cart = ShopCart(user_id=user_id, shop_id=shop_id)
                db.session.add(cart)
                db.session.commit()
            
            return cart
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def add_to_cart(user_id: int, shop_id: int, shop_product_id: int, quantity: int, selected_attributes=None):
        """
        Add a shop product to the user's cart with optional selected attributes
        """
        try:
            cart = PublicShopCartController.get_cart(user_id, shop_id)
            shop_product = ShopProduct.query.get(shop_product_id)
            
            if not shop_product:
                raise ValueError("Shop product not found")
            
            # Verify the product belongs to the specified shop
            if shop_product.shop_id != shop_id:
                raise ValueError("Product does not belong to the specified shop")
            
            # Get product stock first
            product_stock = ShopProductStock.query.filter_by(product_id=shop_product_id).first()
            
            if not product_stock or product_stock.stock_qty < quantity:
                raise ValueError("Insufficient stock")

            # Check if product already exists in cart with the same attributes
            existing_cart_item = None
            if selected_attributes:
                # For products with attributes, we need to check if the same product with same attributes exists
                cart_items = ShopCartItem.query.filter_by(
                    cart_id=cart.cart_id,
                    shop_product_id=shop_product_id
                ).all()
                
                for item in cart_items:
                    if item.get_selected_attributes() == selected_attributes:
                        existing_cart_item = item
                        break
            else:
                # For products without attributes, check normally
                existing_cart_item = ShopCartItem.query.filter_by(
                    cart_id=cart.cart_id,
                    shop_product_id=shop_product_id
                ).first()
            
            if existing_cart_item:
                # Update quantity if product exists with same attributes
                existing_cart_item.quantity += quantity
                cart_item = existing_cart_item
            else:
                # Create new cart item if product doesn't exist or has different attributes
                print(f"Creating new cart item for product: {shop_product.product_name} (ID: {shop_product.product_id})")
                cart_item = ShopCartItem.create_from_shop_product(
                    cart_id=cart.cart_id,
                    shop_product=shop_product,
                    quantity=quantity,
                    selected_attributes=selected_attributes
                )
                print(f"Cart item created with image_url: {cart_item.product_image_url}")
                db.session.add(cart_item)
            
            db.session.commit()
            return cart
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_cart_item(cart_item_id: int, quantity: int):
        """
        Update the quantity of a cart item
        """
        try:
            cart_item = ShopCartItem.query.get(cart_item_id)
            
            if not cart_item:
                raise ValueError("Cart item not found")
            
            if quantity <= 0:
                db.session.delete(cart_item)
            else:
                cart_item.quantity = quantity
            
            db.session.commit()
            return cart_item
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def remove_from_cart(cart_item_id: int):
        """
        Remove an item from the cart
        """
        try:
            cart_item = ShopCartItem.query.get(cart_item_id)
            
            if not cart_item:
                raise ValueError("Cart item not found")
            
            db.session.delete(cart_item)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def clear_cart(user_id: int, shop_id: int):
        """
        Clear all items from the user's cart in a specific shop
        """
        try:
            cart = ShopCart.query.filter_by(user_id=user_id, shop_id=shop_id).first()
            
            if not cart:
                return
            
            ShopCartItem.query.filter_by(cart_id=cart.cart_id).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cart_details(user_id: int, shop_id: int):
        """Get detailed cart information for a specific shop"""
        try:
            cart = PublicShopCartController.get_cart(user_id, shop_id)
            return True, cart.serialize()

        except Exception as e:
            logger.error(f"Error getting cart details: {str(e)}")
            raise

    @staticmethod
    def get_user_carts(user_id: int):
        """
        Get all carts for a user across different shops
        """
        try:
            carts = ShopCart.query.filter_by(user_id=user_id).all()
            return [cart.serialize() for cart in carts]
        except Exception as e:
            logger.error(f"Error getting user carts: {str(e)}")
            raise
