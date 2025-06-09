from flask import jsonify, request, current_app
from models.review import Review, ReviewImage
from models.order import Order, OrderItem
from models.product import Product
from models.enums import OrderStatusEnum, MediaType
from common.database import db
import cloudinary
import cloudinary.uploader
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ReviewController:
    @staticmethod
    def _get_user_info(user):
        """Helper method to get user information safely."""
        if not user:
            return None
            
        return {
            'id': user.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or ''
        }

    @staticmethod
    def get_review(review_id):
        """Get a single review by ID with user and product details."""
        try:
            review = Review.query.filter_by(
                review_id=review_id
            ).first()
            
            if not review:
                raise ValueError("Review not found")
                
            review_data = review.serialize(include_images=True)
            
            # Add user details
            review_data['user'] = ReviewController._get_user_info(review.user)
            
            return review_data
            
        except Exception as e:
            logger.error(f"Error getting review: {str(e)}")
            raise

    @staticmethod
    def create_review(user_id, review_data):
        """Create a new review for a product."""
        try:
            # Validate order exists and belongs to user
            order = Order.query.filter_by(
                order_id=review_data['order_id'],
                user_id=user_id
            ).first()
            
            if not order:
                raise ValueError("Order not found or does not belong to user")
                
            # Check if order is delivered
            if order.order_status != OrderStatusEnum.DELIVERED:
                raise ValueError("Can only review delivered orders")
                
            # Check if product exists in order
            order_item = OrderItem.query.filter_by(
                order_id=order.order_id,
                product_id=review_data['product_id']
            ).first()
            
            if not order_item:
                raise ValueError("Product not found in order")
                
            # Check if user has already reviewed this product
            existing_review = Review.query.filter_by(
                user_id=user_id,
                product_id=review_data['product_id'],
                order_id=order.order_id
            ).first()
            
            if existing_review:
                raise ValueError("You have already reviewed this product for this order")
                
            # Create review
            review = Review(
                user_id=user_id,
                product_id=review_data['product_id'],
                order_id=order.order_id,
                rating=review_data['rating'],
                title=review_data['title'],
                body=review_data['body']
            )
            
            # Save review first to get review_id
            review.save()
            
            # Handle images if provided
            if 'images' in review_data and review_data['images']:
                for index, image_data in enumerate(review_data['images']):
                    try:
                        # Upload to Cloudinary
                        upload_result = cloudinary.uploader.upload(
                            image_data,
                            folder=f"reviews/{review.review_id}",
                            public_id=f"review_image_{index}",
                            resource_type="image"
                        )
                        
                        if upload_result:
                            # Create review image record
                            review_image = ReviewImage(
                                review_id=review.review_id,
                                image_url=upload_result['secure_url'],
                                public_id=upload_result['public_id'],
                                sort_order=index
                            )
                            review.images.append(review_image)
                            
                            # Save the image record
                            db.session.add(review_image)
                    except Exception as e:
                        current_app.logger.error(f"Failed to upload review image: {str(e)}")
                        # Continue with other images even if one fails
                        continue
            
            # Commit all changes
            db.session.commit()
            
            review_data = review.serialize(include_images=True)
            
            # Add user details
            review_data['user'] = ReviewController._get_user_info(review.user)
            
            return review_data
            
        except Exception as e:
            logger.error(f"Error creating review: {str(e)}")
            # Rollback changes if there's an error
            db.session.rollback()
            raise
            
    @staticmethod
    def get_product_reviews(product_id, page=1, per_page=10):
        """Get all reviews for a specific product."""
        try:
            # Get paginated reviews with images eagerly loaded
            reviews = Review.query.filter_by(
                product_id=product_id
            ).options(
                db.joinedload(Review.images)
            ).order_by(Review.created_at.desc())\
             .paginate(page=page, per_page=per_page)
            
            # Get total count
            total = Review.query.filter_by(
                product_id=product_id
            ).count()
            
            # Convert reviews to dict with user info
            reviews_data = []
            for review in reviews.items:
                review_dict = review.serialize(include_images=True)
                
                # Add user details
                review_dict['user'] = ReviewController._get_user_info(review.user)
                
                # Ensure images are properly included
                if not review_dict.get('images'):
                    review_dict['images'] = []
                
                reviews_data.append(review_dict)
            
            return {
                'reviews': reviews_data,
                'total': total,
                'pages': reviews.pages,
                'current_page': reviews.page
            }
            
        except Exception as e:
            logger.error(f"Error getting product reviews: {str(e)}")
            raise
            
    @staticmethod
    def get_user_reviews(user_id, page=1, per_page=10):
        """Get all reviews by a specific user."""
        try:
            # Get paginated reviews
            reviews = Review.query.filter_by(
                user_id=user_id
            ).order_by(Review.created_at.desc())\
             .paginate(page=page, per_page=per_page)
            
            # Get total count
            total = Review.query.filter_by(
                user_id=user_id
            ).count()
            
            # Convert reviews to dict with user info
            reviews_data = []
            for review in reviews.items:
                review_dict = review.serialize(include_images=True)
                
                # Add user details
                review_dict['user'] = ReviewController._get_user_info(review.user)
                
                reviews_data.append(review_dict)
            
            return {
                'reviews': reviews_data,
                'total': total,
                'pages': reviews.pages,
                'current_page': reviews.page
            }
            
        except Exception as e:
            logger.error(f"Error getting user reviews: {str(e)}")
            raise
            
    @staticmethod
    def delete_review(review_id, user_id):
        """Delete a review."""
        try:
            review = Review.query.filter_by(
                review_id=review_id,
                user_id=user_id
            ).first()
            
            if not review:
                raise ValueError("Review not found or does not belong to user")
                
            # Delete images from Cloudinary
            for image in review.images:
                if hasattr(image, 'public_id') and image.public_id:
                    try:
                        cloudinary.uploader.destroy(
                            image.public_id,
                            resource_type="image"
                        )
                        current_app.logger.info(f"Successfully deleted {image.public_id} from Cloudinary.")
                    except Exception as e:
                        current_app.logger.error(f"Failed to delete image {image.public_id} from Cloudinary: {e}")
                    
            # Delete review
            db.session.delete(review)
            db.session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting review: {str(e)}")
            raise 