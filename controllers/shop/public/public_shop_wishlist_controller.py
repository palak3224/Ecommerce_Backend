from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from common.database import db
from common.response import success_response, error_response
from models.shop.shop_wishlist import ShopWishlistItem
from models.shop.shop_product import ShopProduct
from models.shop.shop import Shop


class PublicShopWishlistController:
    """Controller for managing shop wishlist items for authenticated users"""

    @staticmethod
    def add_to_wishlist(shop_id, product_id):
        """Add a product to user's wishlist for a specific shop"""
        try:
            # Get current authenticated user
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate shop_id and product_id
            if not shop_id or not product_id:
                return error_response("Shop ID and Product ID are required", 400)

            # Check if shop exists and is active
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).filter(Shop.deleted_at.is_(None)).first()
            if not shop:
                return error_response("Shop not found or not active", 404)

            # Check if product exists and belongs to the specified shop
            shop_product = ShopProduct.query.options(
                joinedload(ShopProduct.media),
                joinedload(ShopProduct.stock)
            ).filter_by(
                product_id=product_id,
                shop_id=shop_id,
                active_flag=True,
                is_published=True
            ).filter(ShopProduct.deleted_at.is_(None)).first()

            if not shop_product:
                return error_response("Product not found in this shop", 404)

            # Check if item is already in wishlist
            if ShopWishlistItem.check_item_in_wishlist(user_id, shop_id, product_id):
                return error_response("Product is already in your wishlist", 409)

            # Create new wishlist item
            wishlist_item = ShopWishlistItem.create_from_shop_product(user_id, shop_product)
            
            # Save to database
            db.session.add(wishlist_item)
            db.session.commit()

            return success_response(
                message="Product added to wishlist successfully",
                data=wishlist_item.serialize()
            )

        except IntegrityError as e:
            db.session.rollback()
            return error_response("Product is already in your wishlist", 409)
        except Exception as e:
            db.session.rollback()
            return error_response(f"Error adding product to wishlist: {str(e)}", 500)

    @staticmethod
    def remove_from_wishlist(shop_id, wishlist_item_id):
        """Hard delete a wishlist item for a specific shop"""
        try:
            # Get current authenticated user
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate parameters
            if not shop_id or not wishlist_item_id:
                return error_response("Shop ID and Wishlist Item ID are required", 400)

            # Check if shop exists and is active
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).filter(Shop.deleted_at.is_(None)).first()
            if not shop:
                return error_response("Shop not found or not active", 404)

            # Find the wishlist item
            wishlist_item = ShopWishlistItem.get_wishlist_item(user_id, shop_id, wishlist_item_id)
            
            if not wishlist_item:
                return error_response("Wishlist item not found", 404)

            # Hard delete the item
            db.session.delete(wishlist_item)
            db.session.commit()

            return success_response(
                message="Product removed from wishlist successfully",
                data={"wishlist_item_id": wishlist_item_id}
            )

        except Exception as e:
            db.session.rollback()
            return error_response(f"Error removing product from wishlist: {str(e)}", 500)

    @staticmethod
    def get_shop_wishlist(shop_id):
        """Get all wishlist items for a specific shop for the current user"""
        try:
            # Get current authenticated user
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate shop_id
            if not shop_id:
                return error_response("Shop ID is required", 400)

            # Check if shop exists and is active
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).filter(Shop.deleted_at.is_(None)).first()
            if not shop:
                return error_response("Shop not found or not active", 404)

            # Get wishlist items
            wishlist_items = ShopWishlistItem.get_user_shop_wishlist(user_id, shop_id)
            
            # Serialize the items
            serialized_items = [item.serialize() for item in wishlist_items]

            return success_response(
                message="Wishlist retrieved successfully",
                data={
                    "wishlist_items": serialized_items,
                    "total_items": len(serialized_items)
                }
            )

        except Exception as e:
            return error_response(f"Error retrieving wishlist: {str(e)}", 500)

    @staticmethod
    def check_wishlist_status(shop_id, product_id):
        """Check if a product is in user's wishlist for a specific shop"""
        try:
            # Get current authenticated user
            user_id = get_jwt_identity()
            if not user_id:
                return error_response("Authentication required", 401)

            # Validate parameters
            if not shop_id or not product_id:
                return error_response("Shop ID and Product ID are required", 400)

            # Check if shop exists and is active
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).filter(Shop.deleted_at.is_(None)).first()
            if not shop:
                return error_response("Shop not found or not active", 404)

            # Check if item is in wishlist
            is_in_wishlist = ShopWishlistItem.check_item_in_wishlist(user_id, shop_id, product_id)

            return success_response(
                message="Wishlist status checked successfully",
                data={
                    "is_in_wishlist": is_in_wishlist,
                    "shop_id": shop_id,
                    "product_id": product_id
                }
            )

        except Exception as e:
            return error_response(f"Error checking wishlist status: {str(e)}", 500)
