from flask import jsonify, current_app, request
from models.cart import Cart, CartItem
from models.product import Product
from models.product_stock import ProductStock
from models.product_media import ProductMedia
from common.database import db
from sqlalchemy import and_
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CartController:
    @staticmethod
    def get_cart_items(user_id: int):
        """
        Get all cart items for a user
        """
        try:
            # Get the user's cart
            cart = Cart.query.filter_by(user_id=user_id).first()
            
            if not cart:
                # Create a new cart if it doesn't exist
                cart = Cart(user_id=user_id)
                db.session.add(cart)
                db.session.commit()
                return []

            # Get all cart items with their associated products
            cart_items = CartItem.query.filter_by(cart_id=cart.cart_id).all()
            
            return cart_items
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cart(user_id: int):
        """
        Get or create a cart for a user
        """
        try:
            cart = Cart.query.filter_by(user_id=user_id).first()
            
            if not cart:
                cart = Cart(user_id=user_id)
                db.session.add(cart)
                db.session.commit()
            
            return cart
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def add_to_cart(user_id: int, product_id: int, quantity: int, selected_attributes=None):
        """
        Add a product to the user's cart with optional selected attributes
        """
        try:
            cart = CartController.get_cart(user_id)
            product = Product.query.get(product_id)
            
            if not product:
                raise ValueError("Product not found")
            
            # Get product stock first
            product_stock = ProductStock.query.filter_by(product_id=product_id).first()
            
            if not product_stock or product_stock.stock_qty < quantity:
                raise ValueError("Insufficient stock")
            
            # Get product image URL
            product_image = ProductMedia.query.filter_by(
                product_id=product_id,
                type='image'
            ).first()

            # Check if product has a valid special price
            current_date = datetime.utcnow().date()
            has_valid_special_price = (
                product.special_price is not None and
                product.special_start is not None and
                product.special_end is not None and
                product.special_start <= current_date <= product.special_end
            )
            
            # Use special price if valid, otherwise use selling price
            effective_price = product.special_price if has_valid_special_price else product.selling_price
            
            # Check if product already exists in cart with the same attributes
            existing_cart_item = None
            if selected_attributes:
                # For products with attributes, we need to check if the same product with same attributes exists
                cart_items = CartItem.query.filter_by(
                    cart_id=cart.cart_id,
                    product_id=product_id
                ).all()
                
                for item in cart_items:
                    if item.get_selected_attributes() == selected_attributes:
                        existing_cart_item = item
                        break
            else:
                # For products without attributes, check normally
                existing_cart_item = CartItem.query.filter_by(
                    cart_id=cart.cart_id,
                    product_id=product_id
                ).first()
            
            if existing_cart_item:
                # Update quantity if product exists with same attributes
                existing_cart_item.quantity += quantity
                cart_item = existing_cart_item
            else:
                # Create new cart item if product doesn't exist or has different attributes
                cart_item = CartItem.create_from_product(
                    cart_id=cart.cart_id,
                    product=product,
                    quantity=quantity,
                    selected_attributes=selected_attributes
                )
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
            cart_item = CartItem.query.get(cart_item_id)
            
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
            cart_item = CartItem.query.get(cart_item_id)
            
            if not cart_item:
                raise ValueError("Cart item not found")
            
            db.session.delete(cart_item)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def clear_cart(user_id: int):
        """
        Clear all items from the user's cart
        """
        try:
            cart = Cart.query.filter_by(user_id=user_id).first()
            
            if not cart:
                return
            
            CartItem.query.filter_by(cart_id=cart.cart_id).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cart_details(user_id):
        """Get detailed cart information"""
        try:
            cart = CartController.get_cart(user_id)
            return True, cart.serialize()

        except Exception as e:
            logger.error(f"Error getting cart details: {str(e)}")
            raise 