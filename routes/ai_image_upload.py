"""
Temporary image upload endpoint for AI Product Description feature
Uploads images temporarily and returns URLs for AI processing
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
from auth.utils import merchant_role_required

ai_image_upload_bp = Blueprint('ai_image_upload', __name__)

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'temp_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@ai_image_upload_bp.route('/api/merchant-dashboard/upload-temp-image', methods=['POST'])
@jwt_required()
@merchant_role_required
def upload_temp_image():
    """
    Upload temporary image for AI processing
    Returns the image URL that can be used by the AI service
    """
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        
        # Save file
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        # Generate URL
        # In production, this should be your actual domain
        base_url = request.host_url.rstrip('/')
        image_url = f"{base_url}/static/temp_uploads/{unique_filename}"
        
        return jsonify({
            'success': True,
            'url': image_url,
            'image_url': image_url,
            'filename': unique_filename,
            'message': 'Image uploaded successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to upload image',
            'details': str(e)
        }), 500

@ai_image_upload_bp.route('/api/merchant-dashboard/delete-temp-image/<filename>', methods=['DELETE'])
@jwt_required()
@merchant_role_required
def delete_temp_image(filename):
    """
    Delete temporary uploaded image
    """
    try:
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({
                'success': True,
                'message': 'Image deleted successfully'
            }), 200
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({
            'error': 'Failed to delete image',
            'details': str(e)
        }), 500

