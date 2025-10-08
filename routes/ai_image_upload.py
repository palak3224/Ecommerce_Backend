"""
Temporary image upload endpoint for AI Product Description feature
Uploads images to Cloudinary and returns URLs for AI processing
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from http import HTTPStatus
from auth.utils import merchant_role_required

ai_image_upload_bp = Blueprint('ai_image_upload', __name__)

# Configure allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@ai_image_upload_bp.route('/api/merchant-dashboard/upload-temp-image', methods=['POST'])
@jwt_required()
@merchant_role_required
def upload_temp_image():
    """
    Upload temporary image to Cloudinary for AI processing
    Returns the Cloudinary URL and public_id that can be used by the AI service
    """
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), HTTPStatus.BAD_REQUEST
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), HTTPStatus.BAD_REQUEST
        
        # Check file extension
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), HTTPStatus.BAD_REQUEST
        
        # Upload to Cloudinary in a dedicated folder for AI temp images
        upload_result = cloudinary.uploader.upload(
            file,
            folder='ai_temp_images',
            resource_type="image",
            allowed_formats=list(ALLOWED_EXTENSIONS)
        )
        
        # Return both url and image_url for compatibility
        secure_url = upload_result.get('secure_url')
        
        return jsonify({
            'success': True,
            'url': secure_url,
            'image_url': secure_url,
            'public_id': upload_result.get('public_id'),
            'format': upload_result.get('format'),
            'bytes': upload_result.get('bytes'),
            'message': 'Image uploaded successfully to Cloudinary'
        }), HTTPStatus.OK
        
    except Exception as e:
        current_app.logger.error(f"AI temp image upload failed: {str(e)}")
        return jsonify({
            'error': 'Failed to upload image',
            'details': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@ai_image_upload_bp.route('/api/merchant-dashboard/delete-temp-image/<public_id>', methods=['DELETE'])
@jwt_required()
@merchant_role_required
def delete_temp_image(public_id):
    """
    Delete temporary uploaded image from Cloudinary
    Note: public_id should be URL-encoded if it contains slashes (e.g., ai_temp_images/xyz)
    """
    try:
        # If the public_id doesn't contain the folder prefix, add it
        if not public_id.startswith('ai_temp_images/'):
            public_id = f'ai_temp_images/{public_id}'
        
        # Delete from Cloudinary
        result = cloudinary.uploader.destroy(public_id, resource_type='image')
        
        if result.get('result') == 'ok':
            return jsonify({
                'success': True,
                'message': 'Image deleted successfully from Cloudinary'
            }), HTTPStatus.OK
        else:
            return jsonify({
                'error': 'File not found or already deleted',
                'result': result.get('result')
            }), HTTPStatus.NOT_FOUND
            
    except Exception as e:
        current_app.logger.error(f"AI temp image deletion failed: {str(e)}")
        return jsonify({
            'error': 'Failed to delete image',
            'details': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR

