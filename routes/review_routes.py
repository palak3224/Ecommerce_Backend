from flask import Blueprint, request, jsonify, current_app
from controllers.review_controller import ReviewController
from auth.utils import role_required
from auth.models.models import UserRole
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from werkzeug.exceptions import BadRequest

logger = logging.getLogger(__name__)

review_bp = Blueprint('review', __name__, url_prefix='/api/reviews')

@review_bp.route('', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def create_review():
    """
    Create a new review for a product from a delivered order.
    
    Request Body:
    {
        "order_id": "ORD-123456",
        "product_id": 1,
        "rating": 5,
        "title": "Great product!",
        "body": "Really happy with this purchase",
        "images": ["base64_encoded_image1", "base64_encoded_image2"]  # Optional
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "review_id": 1,
            "product_id": 1,
            "user_id": 1,
            "order_id": "ORD-123456",
            "rating": 5,
            "title": "Great product!",
            "body": "Really happy with this purchase",
            "created_at": "2024-03-20T10:00:00Z",
            "updated_at": "2024-03-20T10:00:00Z",
            "images": [
                {
                    "image_id": 1,
                    "image_url": "https://cloudinary.com/...",
                    "sort_order": 0,
                    "type": "image",
                    "created_at": "2024-03-20T10:00:00Z",
                    "updated_at": "2024-03-20T10:00:00Z"
                }
            ],
            "user": {
                "id": 1,
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com"
            }
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        review_data = request.get_json()
        
        if not review_data:
            raise BadRequest('No review data provided')
            
        # Validate required fields
        required_fields = ['order_id', 'product_id', 'rating', 'title', 'body']
        missing_fields = [field for field in required_fields if field not in review_data]
        if missing_fields:
            raise BadRequest(f'Missing required fields: {", ".join(missing_fields)}')
                
        # Validate rating
        if not isinstance(review_data['rating'], int) or review_data['rating'] < 1 or review_data['rating'] > 5:
            raise BadRequest('Rating must be an integer between 1 and 5')
            
        # Validate title and body length
        if len(review_data['title'].strip()) < 3:
            raise BadRequest('Title must be at least 3 characters long')
        if len(review_data['body'].strip()) < 10:
            raise BadRequest('Review body must be at least 10 characters long')
            
        # Validate images if provided
        if 'images' in review_data:
            if not isinstance(review_data['images'], list):
                raise BadRequest('Images must be provided as a list')
            if len(review_data['images']) > 5:
                raise BadRequest('Maximum 5 images allowed per review')
            for image in review_data['images']:
                if not isinstance(image, str) or not image.startswith('data:image/'):
                    raise BadRequest('Invalid image format. Images must be base64 encoded')
            
        result = ReviewController.create_review(user_id, review_data)
        return jsonify({
            'status': 'success',
            'data': result
        }), 201
        
    except BadRequest as e:
        logger.warning(f"Bad request creating review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except ValueError as ve:
        logger.error(f"Validation error creating review: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while creating the review'
        }), 500

@review_bp.route('/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """
    Get a single review by ID.
    ---
    tags:
      - Reviews
    parameters:
      - in: path
        name: review_id
        type: integer
        required: true
        description: ID of the review to retrieve.
    responses:
      200:
        description: Review retrieved successfully.
      400:
        description: Invalid review ID.
      404:
        description: Review not found.
      500:
        description: Internal server error.
    """
    try:
        if not isinstance(review_id, int) or review_id <= 0:
            raise BadRequest('Invalid review ID')
            
        result = ReviewController.get_review(review_id)
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except BadRequest as e:
        logger.warning(f"Bad request getting review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except ValueError as ve:
        logger.error(f"Validation error getting review: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error getting review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while retrieving the review'
        }), 500

@review_bp.route('/product/<int:product_id>', methods=['GET'])
def get_product_reviews(product_id):
    """
    Get all reviews for a specific product.
    ---
    tags:
      - Reviews
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
        description: "ID of the product to retrieve reviews for."
      - name: page
        in: query
        type: integer
        required: false
        description: "Page number (default: 1)."
      - name: per_page
        in: query
        type: integer
        required: false
        description: "Items per page (default: 10)."
    responses:
      200:
        description: "List of reviews retrieved successfully."
      400:
        description: "Invalid product ID or bad request."
      500:
        description: "Internal server error."
    """
    try:
        if not isinstance(product_id, int) or product_id <= 0:
            raise BadRequest('Invalid product ID')
            
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if page < 1:
            raise BadRequest('Page number must be greater than 0')
        if per_page < 1 or per_page > 50:
            raise BadRequest('Items per page must be between 1 and 50')
        
        result = ReviewController.get_product_reviews(product_id, page, per_page)
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except BadRequest as e:
        logger.warning(f"Bad request getting product reviews: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error getting product reviews: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while retrieving product reviews'
        }), 500

@review_bp.route('/user', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_user_reviews():
    """
    Get all reviews by the current user.
    ---
    tags:
      - Reviews
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        description: "Page number (default: 1)."
      - name: per_page
        in: query
        type: integer
        required: false
        description: "Items per page (default: 10)."
    responses:
      200:
        description: "List of user reviews retrieved successfully."
      400:
        description: "Invalid request or bad parameters."
      401:
        description: "Unauthorized."
      500:
        description: "Internal server error."
    """
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if page < 1:
            raise BadRequest('Page number must be greater than 0')
        if per_page < 1 or per_page > 50:
            raise BadRequest('Items per page must be between 1 and 50')
        
        result = ReviewController.get_user_reviews(user_id, page, per_page)
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except BadRequest as e:
        logger.warning(f"Bad request getting user reviews: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error getting user reviews: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while retrieving user reviews'
        }), 500

@review_bp.route('/<int:review_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def delete_review(review_id):
    """
    Delete a review by its ID.
    ---
    tags:
      - Reviews
    security:
      - Bearer: []
    parameters:
      - in: path
        name: review_id
        type: integer
        required: true
        description: "ID of the review to delete."
    responses:
      200:
        description: "Review deleted successfully."
      400:
        description: "Invalid review ID."
      401:
        description: "Unauthorized."
      404:
        description: "Review not found."
      500:
        description: "Internal server error."
    """
    try:
        if not isinstance(review_id, int) or review_id <= 0:
            raise BadRequest('Invalid review ID')
            
        user_id = get_jwt_identity()
        
        result = ReviewController.delete_review(review_id, user_id)
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Review deleted successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to delete review'
            }), 500
            
    except BadRequest as e:
        logger.warning(f"Bad request deleting review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except ValueError as ve:
        logger.error(f"Validation error deleting review: {str(ve)}")
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error deleting review: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while deleting the review'
        }), 500