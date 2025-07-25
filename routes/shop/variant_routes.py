# routes/shop/variant_routes.py
from flask import Blueprint
from controllers.shop.shop_variant_controller import ShopVariantController

variant_bp = Blueprint('shop_variants', __name__)

# Variant management routes
@variant_bp.route('/products/<int:parent_id>/variants', methods=['POST'])
def create_variant(parent_id):
    """Create a new variant for a parent product"""
    return ShopVariantController.create_variant(parent_id)

@variant_bp.route('/products/<int:parent_id>/variants', methods=['GET'])
def get_variants(parent_id):
    """Get all variants for a parent product"""
    return ShopVariantController.get_variants(parent_id)

@variant_bp.route('/variants/<int:variant_id>', methods=['PUT'])
def update_variant(variant_id):
    """Update a specific variant"""
    return ShopVariantController.update_variant(variant_id)

@variant_bp.route('/variants/<int:variant_id>', methods=['DELETE'])
def delete_variant(variant_id):
    """Delete a specific variant"""
    return ShopVariantController.delete_variant(variant_id)

@variant_bp.route('/products/<int:parent_id>/variants/bulk', methods=['POST'])
def bulk_create_variants(parent_id):
    """Create multiple variants from attribute combinations"""
    return ShopVariantController.bulk_create_variants(parent_id)

# Variant utility routes
@variant_bp.route('/products/<int:product_id>/variant-options', methods=['GET'])
def get_variant_options(product_id):
    """Get available attribute options for creating variants"""
    from controllers.shop.shop_variant_controller import ShopVariantController
    return ShopVariantController.get_variant_options(product_id)

@variant_bp.route('/products/<int:parent_id>/variant-combinations', methods=['POST'])
def generate_variant_combinations(parent_id):
    """Generate all possible variant combinations from selected attributes"""
    from controllers.shop.shop_variant_controller import ShopVariantController
    return ShopVariantController.generate_variant_combinations(parent_id)

# Variant Media Management Routes
@variant_bp.route('/variants/<int:variant_id>/media', methods=['POST'])
def upload_variant_media(variant_id):
    """Upload media files for a specific variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.upload_variant_media(variant_id)

@variant_bp.route('/variants/<int:variant_id>/media', methods=['GET'])
def get_variant_media(variant_id):
    """Get all media for a specific variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.get_variant_media(variant_id)

@variant_bp.route('/variants/<int:variant_id>/media/order', methods=['PUT'])
def update_media_order(variant_id):
    """Update the sort order of media files for a variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.update_media_order(variant_id)

@variant_bp.route('/variants/<int:variant_id>/media/<int:media_id>/primary', methods=['PUT'])
def set_primary_media(variant_id, media_id):
    """Set a media file as primary for the variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.set_primary_media(variant_id, media_id)

@variant_bp.route('/variants/<int:variant_id>/media/<int:media_id>', methods=['DELETE'])
def delete_variant_media(variant_id, media_id):
    """Delete a media file from a variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.delete_variant_media(variant_id, media_id)

@variant_bp.route('/variants/<int:variant_id>/media/stats', methods=['GET'])
def get_media_stats(variant_id):
    """Get media statistics for a variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.get_media_stats(variant_id)

@variant_bp.route('/variants/<int:variant_id>/media/copy-parent', methods=['POST'])
def copy_parent_media(variant_id):
    """Copy parent product media to variant"""
    from controllers.shop.shop_variant_media_controller import ShopVariantMediaController
    return ShopVariantMediaController.copy_parent_media(variant_id)
