from flask import Blueprint
from controllers.user_preference_controller import UserPreferenceController
from flask_jwt_extended import jwt_required
from flask_cors import cross_origin

user_preference_bp = Blueprint('user_preference', __name__)


@user_preference_bp.route('/api/reels/not-interested/merchant/<int:merchant_id>', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def block_merchant(merchant_id):
    """
    Mark a vendor as 'not interested' (hide their reels from your feeds)
    ---
    tags:
      - Reel Preferences
    security:
      - Bearer: []
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID to mark as not interested
    responses:
      201:
        description: Vendor marked as not interested
      401:
        description: Unauthorized (authentication required)
      404:
        description: Merchant not found
      500:
        description: Server error
    """
    return UserPreferenceController.block_merchant(merchant_id)


@user_preference_bp.route('/api/reels/not-interested/merchant/<int:merchant_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@jwt_required()
def unblock_merchant(merchant_id):
    """
    Undo 'not interested' for a vendor (restore their reels to your feeds)
    ---
    tags:
      - Reel Preferences
    security:
      - Bearer: []
    parameters:
      - in: path
        name: merchant_id
        type: integer
        required: true
        description: Merchant ID to restore
    responses:
      200:
        description: Vendor restored to your feeds
      400:
        description: Vendor was not in your not-interested list
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return UserPreferenceController.unblock_merchant(merchant_id)


@user_preference_bp.route('/api/reels/not-interested/category/<int:category_id>', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required()
def hide_category(category_id):
    """
    Mark a category as 'not interested' (hide its reels from your feeds)
    ---
    tags:
      - Reel Preferences
    security:
      - Bearer: []
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: Category ID to mark as not interested
    responses:
      201:
        description: Category marked as not interested
      401:
        description: Unauthorized (authentication required)
      404:
        description: Category not found
      500:
        description: Server error
    """
    return UserPreferenceController.hide_category(category_id)


@user_preference_bp.route('/api/reels/not-interested/category/<int:category_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@jwt_required()
def unhide_category(category_id):
    """
    Undo 'not interested' for a category (restore its reels to your feeds)
    ---
    tags:
      - Reel Preferences
    security:
      - Bearer: []
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: Category ID to restore
    responses:
      200:
        description: Category restored to your feeds
      400:
        description: Category was not in your not-interested list
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return UserPreferenceController.unhide_category(category_id)


@user_preference_bp.route('/api/reels/not-interested', methods=['GET', 'OPTIONS'])
@cross_origin()
@jwt_required()
def get_not_interested():
    """
    List your blocked vendors and hidden categories (for a settings screen)
    ---
    tags:
      - Reel Preferences
    security:
      - Bearer: []
    responses:
      200:
        description: Your not-interested vendors and categories
      401:
        description: Unauthorized (authentication required)
      500:
        description: Server error
    """
    return UserPreferenceController.get_not_interested()
