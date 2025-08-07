from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from controllers.shop.public.public_shop_wishlist_controller import PublicShopWishlistController

# Create Blueprint for public shop wishlist routes
public_shop_wishlist_bp = Blueprint('public_shop_wishlist', __name__)


@public_shop_wishlist_bp.route('/api/public/shops/<int:shop_id>/wishlist', methods=['POST'])
@jwt_required()
def add_to_wishlist(shop_id):
    """
    Add a product to user's wishlist for a specific shop
    
    Request Body:
    {
        "product_id": 123
    }
    """
    data = request.get_json()
    product_id = data.get('product_id') if data else None
    
    return PublicShopWishlistController.add_to_wishlist(shop_id, product_id)


@public_shop_wishlist_bp.route('/api/public/shops/<int:shop_id>/wishlist/<int:wishlist_item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_wishlist(shop_id, wishlist_item_id):
    """
    Remove a product from user's wishlist for a specific shop (Hard Delete)
    """
    return PublicShopWishlistController.remove_from_wishlist(shop_id, wishlist_item_id)


@public_shop_wishlist_bp.route('/api/public/shops/<int:shop_id>/wishlist', methods=['GET'])
@jwt_required()
def get_shop_wishlist(shop_id):
    """
    Get all wishlist items for a specific shop for the current user
    """
    return PublicShopWishlistController.get_shop_wishlist(shop_id)


@public_shop_wishlist_bp.route('/api/public/shops/<int:shop_id>/wishlist/check/<int:product_id>', methods=['GET'])
@jwt_required()
def check_wishlist_status(shop_id, product_id):
    """
    Check if a product is in user's wishlist for a specific shop
    """
    return PublicShopWishlistController.check_wishlist_status(shop_id, product_id)


# Alternative route for checking wishlist status via POST (if needed)
@public_shop_wishlist_bp.route('/api/public/shops/<int:shop_id>/wishlist/check', methods=['POST'])
@jwt_required()
def check_wishlist_status_post(shop_id):
    """
    Check if a product is in user's wishlist for a specific shop
    
    Request Body:
    {
        "product_id": 123
    }
    """
    data = request.get_json()
    product_id = data.get('product_id') if data else None
    
    return PublicShopWishlistController.check_wishlist_status(shop_id, product_id)
