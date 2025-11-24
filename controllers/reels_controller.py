from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from common.database import db
from models.reel import Reel
from models.user_reel_like import UserReelLike
from models.product import Product
from models.product_stock import ProductStock
from auth.models.models import User, MerchantProfile
from services.storage.storage_factory import get_storage_service
from werkzeug.utils import secure_filename
from sqlalchemy import desc, and_, or_
from datetime import datetime, timezone
from http import HTTPStatus
import os


# Allowed video extensions
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VIDEO_DURATION = 60  # 60 seconds


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


class ReelsController:
    """Controller for Reels operations."""
    
    @staticmethod
    def validate_product_for_reel(product_id, merchant_id):
        """
        Validate product can be used for reel upload.
        
        Args:
            product_id: Product ID to validate
            merchant_id: Merchant ID to verify ownership
            
        Returns:
            tuple: (is_valid: bool, product: Product or None, error_message: str or None)
        """
        # 1. Product exists
        product = Product.query.filter_by(
            product_id=product_id,
            deleted_at=None
        ).first()
        
        if not product:
            return False, None, "Product not found"
        
        # 2. Product belongs to merchant
        if product.merchant_id != merchant_id:
            return False, None, "Product does not belong to your account"
        
        # 3. Product is approved
        if product.approval_status != 'approved':
            return False, None, f"Product must be approved by admin. Current status: {product.approval_status}"
        
        # 4. Product is active
        if not product.active_flag:
            return False, None, "Product is not active"
        
        # 5. Product is not a variant (only parent products)
        if product.parent_product_id is not None:
            return False, None, "Reels can only be linked to parent products, not variants"
        
        # 6. Product has stock > 0
        stock_qty = product.stock.stock_qty if product.stock else 0
        if stock_qty <= 0:
            return False, None, "Product must have stock quantity greater than 0"
        
        return True, product, None
    
    @staticmethod
    def upload_reel():
        """
        Upload a new reel.
        
        Required fields:
        - video: File (MP4, MOV, AVI, MKV, max 100MB, max 60s)
        - product_id: Integer (required, must be approved product with stock > 0)
        - description: String (required, max 5000 chars)
        
        Returns:
            JSON response with reel data or error
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Check if user is a merchant
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant:
                return jsonify({'error': 'Only merchants can upload reels'}), HTTPStatus.FORBIDDEN
            
            # Validate required fields
            if 'video' not in request.files:
                return jsonify({'error': 'Video file is required'}), HTTPStatus.BAD_REQUEST
            
            video_file = request.files['video']
            if video_file.filename == '':
                return jsonify({'error': 'No video file selected'}), HTTPStatus.BAD_REQUEST
            
            # Validate product_id
            product_id = request.form.get('product_id')
            if not product_id:
                return jsonify({'error': 'product_id is required'}), HTTPStatus.BAD_REQUEST
            
            try:
                product_id = int(product_id)
            except ValueError:
                return jsonify({'error': 'product_id must be a valid integer'}), HTTPStatus.BAD_REQUEST
            
            # Validate description
            description = request.form.get('description', '').strip()
            if not description:
                return jsonify({'error': 'description is required'}), HTTPStatus.BAD_REQUEST
            
            if len(description) > 5000:
                return jsonify({'error': 'description must be 5000 characters or less'}), HTTPStatus.BAD_REQUEST
            
            # Validate video file
            if not allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
                return jsonify({
                    'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_VIDEO_EXTENSIONS).upper()}'
                }), HTTPStatus.BAD_REQUEST
            
            # Check file size
            video_file.seek(0, os.SEEK_END)
            file_size = video_file.tell()
            video_file.seek(0)
            
            if file_size > MAX_VIDEO_SIZE:
                return jsonify({
                    'error': f'Video file size must be less than {MAX_VIDEO_SIZE / (1024 * 1024)}MB'
                }), HTTPStatus.BAD_REQUEST
            
            # Validate product
            is_valid, product, error_message = ReelsController.validate_product_for_reel(
                product_id, merchant.id
            )
            if not is_valid:
                return jsonify({'error': error_message}), HTTPStatus.BAD_REQUEST
            
            # Get storage service (abstraction layer)
            storage_service = get_storage_service()
            
            # Upload video to storage (Cloudinary or AWS)
            folder = f"reels/merchant_{merchant.id}/product_{product_id}"
            upload_result = storage_service.upload_video(
                video_file,
                folder=folder,
                resource_type='video',
                allowed_formats=list(ALLOWED_VIDEO_EXTENSIONS)
            )
            
            # Generate thumbnail if not provided
            thumbnail_url = upload_result.get('thumbnail_url')
            if not thumbnail_url and upload_result.get('public_id'):
                try:
                    thumbnail_url = storage_service.generate_thumbnail(
                        upload_result['public_id']
                    )
                except Exception as e:
                    current_app.logger.warning(f"Failed to generate thumbnail: {str(e)}")
            
            # Create reel record
            reel = Reel(
                merchant_id=merchant.id,
                product_id=product_id,
                video_url=upload_result['url'],
                video_public_id=upload_result['public_id'],
                thumbnail_url=thumbnail_url,
                description=description,
                duration_seconds=upload_result.get('duration'),
                file_size_bytes=upload_result.get('bytes'),
                video_format=upload_result.get('format'),
                approval_status='approved',  # Reels don't require approval - active immediately
                is_active=True
            )
            
            db.session.add(reel)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel uploaded successfully.',
                'data': reel.serialize(include_reasons=True, include_product=True)
            }), HTTPStatus.CREATED
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Reel upload failed: {str(e)}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_reel(reel_id, track_view=True):
        """
        Get a single reel by ID with disabling reasons.
        Automatically increments view count if track_view is True.
        If user is authenticated, includes whether the user has liked the reel.
        
        Args:
            reel_id: Reel ID
            track_view: Whether to increment view count (default: True)
            
        Returns:
            JSON response with reel data
        """
        try:
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Track view if requested and reel is visible
            if track_view and reel.is_visible:
                try:
                    reel.increment_views()
                except Exception as e:
                    current_app.logger.warning(f"Failed to increment view count: {str(e)}")
            
            # Get reel data
            reel_data = reel.serialize(include_reasons=True, include_product=True)
            
            # Check if user is authenticated and has liked this reel
            try:
                current_user_id = get_jwt_identity()
                if current_user_id:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel_id)
                    reel_data['is_liked'] = is_liked
            except Exception:
                # User not authenticated or token invalid - silently ignore
                reel_data['is_liked'] = False
            
            return jsonify({
                'status': 'success',
                'data': reel_data
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get reel failed: {str(e)}")
            return jsonify({'error': f'Failed to get reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_merchant_reels(merchant_id=None, include_all=False):
        """
        Get reels for a merchant.
        
        Args:
            merchant_id: Merchant ID (if None, uses current user's merchant profile)
            include_all: If True, includes all reels (including non-visible). If False, only visible.
            
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Determine merchant_id
            if merchant_id is None:
                merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
                if not merchant:
                    return jsonify({'error': 'Merchant profile not found'}), HTTPStatus.NOT_FOUND
                merchant_id = merchant.id
                is_own_reels = True
            else:
                # Check if requesting own reels
                merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
                if not merchant:
                    return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
                is_own_reels = (merchant.user_id == current_user_id)
            
            # Build query
            query = Reel.query.filter_by(merchant_id=merchant_id)
            
            # If not own reels or not including all, filter visible only
            if not is_own_reels or not include_all:
                query = Reel.get_visible_reels(query)
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            pagination = query.order_by(desc(Reel.created_at)).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            reels_data = [reel.serialize(
                include_reasons=is_own_reels,  # Include reasons only for own reels
                include_product=True
            ) for reel in pagination.items]
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get merchant reels failed: {str(e)}")
            return jsonify({'error': f'Failed to get reels: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_public_reels():
        """
        Get public visible reels (for feed).
        Only returns reels that are visible (no disabling reasons).
        
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get only visible reels
            query = Reel.get_visible_reels()
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            pagination = query.order_by(desc(Reel.created_at)).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            reels_data = [reel.serialize(
                include_reasons=False,  # Don't include reasons for public feed
                include_product=True
            ) for reel in pagination.items]
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get public reels failed: {str(e)}")
            return jsonify({'error': f'Failed to get reels: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def update_reel(reel_id):
        """
        Update reel description.
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response with updated reel data
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Check ownership
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant or reel.merchant_id != merchant.id:
                return jsonify({'error': 'You do not have permission to update this reel'}), HTTPStatus.FORBIDDEN
            
            # Get description from request
            data = request.get_json()
            if not data or 'description' not in data:
                return jsonify({'error': 'description is required'}), HTTPStatus.BAD_REQUEST
            
            description = data['description'].strip()
            if not description:
                return jsonify({'error': 'description cannot be empty'}), HTTPStatus.BAD_REQUEST
            
            if len(description) > 5000:
                return jsonify({'error': 'description must be 5000 characters or less'}), HTTPStatus.BAD_REQUEST
            
            # Update description
            reel.description = description
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel updated successfully',
                'data': reel.serialize(include_reasons=True, include_product=True)
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update reel failed: {str(e)}")
            return jsonify({'error': f'Failed to update reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def delete_reel(reel_id):
        """
        Delete a reel (soft delete + delete from storage).
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Check ownership
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant or reel.merchant_id != merchant.id:
                return jsonify({'error': 'You do not have permission to delete this reel'}), HTTPStatus.FORBIDDEN
            
            # Soft delete
            reel.deleted_at = datetime.now(timezone.utc)
            
            # Delete from storage
            if reel.video_public_id:
                try:
                    storage_service = get_storage_service()
                    storage_service.delete_video(reel.video_public_id)
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete video from storage: {str(e)}")
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel deleted successfully'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Delete reel failed: {str(e)}")
            return jsonify({'error': f'Failed to delete reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_available_products():
        """
        Get merchant's approved products with stock > 0 that can be used for reel upload.
        
        Returns:
            JSON response with product list
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get merchant
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant profile not found'}), HTTPStatus.NOT_FOUND
            
            # Get approved products with stock > 0, not variants
            products = Product.query.join(ProductStock).filter(
                Product.merchant_id == merchant.id,
                Product.deleted_at.is_(None),
                Product.active_flag == True,
                Product.approval_status == 'approved',
                Product.parent_product_id.is_(None),  # Only parent products
                ProductStock.stock_qty > 0
            ).all()
            
            products_data = [{
                'product_id': product.product_id,
                'product_name': product.product_name,
                'category_id': product.category_id,
                'category_name': product.category.name if product.category else None,
                'stock_qty': product.stock.stock_qty if product.stock else 0,
                'selling_price': float(product.selling_price) if product.selling_price else None,
            } for product in products]
            
            return jsonify({
                'status': 'success',
                'data': products_data
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get available products failed: {str(e)}")
            return jsonify({'error': f'Failed to get products: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def like_reel(reel_id):
        """
        Like a reel (increment like count with user tracking).
        Requires authentication to track which user likes which reel for recommendations.
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response with updated like status
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Check if reel is visible
            if not reel.is_visible:
                return jsonify({'error': 'Reel is not available'}), HTTPStatus.BAD_REQUEST
            
            # Check if user already liked this reel
            if UserReelLike.user_has_liked(current_user_id, reel_id):
                return jsonify({
                    'error': 'You have already liked this reel',
                    'data': {
                        'reel_id': reel.reel_id,
                        'likes_count': reel.likes_count,
                        'is_liked': True
                    }
                }), HTTPStatus.BAD_REQUEST
            
            # Create like record
            like = UserReelLike.create_like(current_user_id, reel_id)
            if like:
                # Increment like count
                reel.increment_likes()
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Reel liked successfully',
                    'data': {
                        'reel_id': reel.reel_id,
                        'likes_count': reel.likes_count,
                        'is_liked': True
                    }
                }), HTTPStatus.OK
            else:
                # Should not happen due to check above, but handle gracefully
                return jsonify({'error': 'Failed to like reel'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Like reel failed: {str(e)}")
            return jsonify({'error': f'Failed to like reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def unlike_reel(reel_id):
        """
        Unlike a reel (decrement like count with user tracking).
        Requires authentication to track which user unlikes which reel.
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response with updated like status
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Check if user has liked this reel
            if not UserReelLike.user_has_liked(current_user_id, reel_id):
                return jsonify({
                    'error': 'You have not liked this reel',
                    'data': {
                        'reel_id': reel.reel_id,
                        'likes_count': reel.likes_count,
                        'is_liked': False
                    }
                }), HTTPStatus.BAD_REQUEST
            
            # Remove like record
            removed = UserReelLike.remove_like(current_user_id, reel_id)
            if removed:
                # Decrement likes (won't go below 0)
                reel.decrement_likes()
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Reel unliked successfully',
                    'data': {
                        'reel_id': reel.reel_id,
                        'likes_count': reel.likes_count,
                        'is_liked': False
                    }
                }), HTTPStatus.OK
            else:
                # Should not happen due to check above, but handle gracefully
                return jsonify({'error': 'Failed to unlike reel'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unlike reel failed: {str(e)}")
            return jsonify({'error': f'Failed to unlike reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def share_reel(reel_id):
        """
        Share a reel (increment share count).
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response with updated share count
        """
        try:
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Check if reel is visible
            if not reel.is_visible:
                return jsonify({'error': 'Reel is not available'}), HTTPStatus.BAD_REQUEST
            
            # Increment share count
            reel.increment_shares()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel share tracked successfully',
                'data': {
                    'reel_id': reel.reel_id,
                    'shares_count': reel.shares_count
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Share reel failed: {str(e)}")
            return jsonify({'error': f'Failed to track share: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

