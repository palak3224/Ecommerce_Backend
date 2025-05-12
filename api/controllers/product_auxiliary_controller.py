import os
import cloudinary
import cloudinary.uploader
from flask import request, jsonify
from models.catalog.product_auxiliary import ProductImage, ProductVideo
from common.database import db

# Configure Cloudinary (set your credentials in environment variables)
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

class ProductAuxiliaryController:
    @staticmethod
    def upload_image():
        file = request.files.get('image')
        product_id = request.form.get('product_id')
        if not file or not product_id:
            return jsonify({'error': 'Image file and product_id are required'}), 400
        try:
            upload_result = cloudinary.uploader.upload(file, folder='product_images')
            image_url = upload_result['secure_url']
            is_main = request.form.get('is_main', 'false').lower() == 'true'
            image = ProductImage(product_id=product_id, image_url=image_url, is_main=is_main)
            db.session.add(image)
            db.session.commit()
            return jsonify({'image_url': image_url, 'image_id': image.image_id}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def upload_video():
        file = request.files.get('video')
        product_id = request.form.get('product_id')
        if not file or not product_id:
            return jsonify({'error': 'Video file and product_id are required'}), 400
        try:
            upload_result = cloudinary.uploader.upload(file, resource_type='video', folder='product_videos')
            video_url = upload_result['secure_url']
            video = ProductVideo(product_id=product_id, video_url=video_url)
            db.session.add(video)
            db.session.commit()
            return jsonify({'video_url': video_url, 'video_id': video.video_id}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def list_images(product_id):
        images = ProductImage.get_product_images(product_id)
        return jsonify([{'image_id': img.image_id, 'image_url': img.image_url, 'is_main': img.is_main} for img in images])

    @staticmethod
    def list_videos(product_id):
        videos = ProductVideo.get_product_videos(product_id)
        return jsonify([{'video_id': vid.video_id, 'video_url': vid.video_url} for vid in videos]) 