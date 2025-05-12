from flask import Blueprint
from api.controllers.product_auxiliary_controller import ProductAuxiliaryController

product_aux_bp = Blueprint('product_auxiliary', __name__)

# Image upload
@product_aux_bp.route('/product-images', methods=['POST'])
def upload_image():
    return ProductAuxiliaryController.upload_image()

# Video upload
@product_aux_bp.route('/product-videos', methods=['POST'])
def upload_video():
    return ProductAuxiliaryController.upload_video()

# List images for a product
@product_aux_bp.route('/product-images/<int:product_id>', methods=['GET'])
def list_images(product_id):
    return ProductAuxiliaryController.list_images(product_id)

# List videos for a product
@product_aux_bp.route('/product-videos/<int:product_id>', methods=['GET'])
def list_videos(product_id):
    return ProductAuxiliaryController.list_videos(product_id) 