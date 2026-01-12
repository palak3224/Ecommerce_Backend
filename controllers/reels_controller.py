from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from common.database import db
from common.cache import get_redis_client
from models.reel import Reel
from models.user_reel_like import UserReelLike
from models.user_reel_view import UserReelView
from models.user_reel_share import UserReelShare
from models.user_merchant_follow import UserMerchantFollow
from models.user_category_preference import UserCategoryPreference
from models.product import Product
from models.product_stock import ProductStock
from models.product_media import ProductMedia
from models.enums import MediaType
from models.merchant_notification import MerchantNotification
from auth.models.models import User, MerchantProfile
from services.reels_s3_service import get_reels_s3_service
from werkzeug.utils import secure_filename
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timezone, timedelta
from http import HTTPStatus
import os
import mimetypes
from controllers.reels_errors import (
    REEL_UPLOAD_FAILED, STORAGE_ERROR, VALIDATION_ERROR,
    PRODUCT_VALIDATION_ERROR, FILE_VALIDATION_ERROR,
    AUTHORIZATION_ERROR, NOT_FOUND_ERROR, TRANSACTION_ERROR,
    create_error_response
)


# Allowed video extensions (only mp4, webm, mov for reels)
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
# Allowed MIME types for videos
ALLOWED_VIDEO_MIME_TYPES = {
    'video/mp4',
    'video/webm',
    'video/quicktime',  # MOV
}
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
                return create_error_response(
                    AUTHORIZATION_ERROR,
                    'Only merchants can upload reels',
                    {'user_id': current_user_id, 'user_role': user.role.value if user else None},
                    HTTPStatus.FORBIDDEN
                )
            
            # Validate required fields
            if 'video' not in request.files:
                return create_error_response(
                    VALIDATION_ERROR,
                    'Video file is required',
                    {'field': 'video', 'required': True},
                    HTTPStatus.BAD_REQUEST
                )
            
            video_file = request.files['video']
            if video_file.filename == '':
                return create_error_response(
                    VALIDATION_ERROR,
                    'No video file selected',
                    {'field': 'video'},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate product_id
            product_id = request.form.get('product_id')
            if not product_id:
                return create_error_response(
                    VALIDATION_ERROR,
                    'product_id is required',
                    {'field': 'product_id', 'required': True},
                    HTTPStatus.BAD_REQUEST
                )
            
            try:
                product_id = int(product_id)
            except ValueError:
                return create_error_response(
                    VALIDATION_ERROR,
                    'product_id must be a valid integer',
                    {'field': 'product_id', 'provided': product_id},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate description
            description = request.form.get('description', '').strip()
            if not description:
                return create_error_response(
                    VALIDATION_ERROR,
                    'description is required',
                    {'field': 'description', 'required': True},
                    HTTPStatus.BAD_REQUEST
                )
            
            if len(description) > 5000:
                return create_error_response(
                    VALIDATION_ERROR,
                    'description must be 5000 characters or less',
                    {'field': 'description', 'length': len(description), 'max_length': 5000},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate video file extension (only mp4, webm, mov)
            if not allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
                return create_error_response(
                    FILE_VALIDATION_ERROR,
                    f'Invalid file type. Allowed types: {", ".join(ALLOWED_VIDEO_EXTENSIONS).upper()}',
                    {
                        'field': 'video',
                        'filename': video_file.filename,
                        'allowed_extensions': list(ALLOWED_VIDEO_EXTENSIONS)
                    },
                    HTTPStatus.BAD_REQUEST
                )
            
            # Get file extension for S3 upload
            file_extension = 'mp4'  # Default
            if '.' in video_file.filename:
                file_extension = video_file.filename.rsplit('.', 1)[1].lower()
                if file_extension not in ALLOWED_VIDEO_EXTENSIONS:
                    file_extension = 'mp4'  # Fallback to mp4
            
            # Check file size before processing
            video_file.seek(0, os.SEEK_END)
            file_size = video_file.tell()
            video_file.seek(0)
            
            if file_size > MAX_VIDEO_SIZE:
                return create_error_response(
                    FILE_VALIDATION_ERROR,
                    f'Video file size must be less than {MAX_VIDEO_SIZE / (1024 * 1024)}MB',
                    {
                        'field': 'video',
                        'file_size_bytes': file_size,
                        'max_size_bytes': MAX_VIDEO_SIZE,
                        'max_size_mb': MAX_VIDEO_SIZE / (1024 * 1024)
                    },
                    HTTPStatus.BAD_REQUEST
                )
            
            if file_size == 0:
                return create_error_response(
                    FILE_VALIDATION_ERROR,
                    'Video file is empty',
                    {'field': 'video'},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate MIME type (more secure than just extension)
            # Read first few bytes to detect actual file type
            file_header = video_file.read(12)
            video_file.seek(0)  # Reset for upload
            
            # Detect MIME type from file header (only for allowed formats)
            detected_mime = None
            if file_header.startswith(b'\x00\x00\x00\x20ftyp'):
                detected_mime = 'video/mp4'
            elif file_header.startswith(b'\x00\x00\x00\x18ftypqt'):
                detected_mime = 'video/quicktime'
            elif file_header.startswith(b'\x1a\x45\xdf\xa3'):
                # WebM starts with this header
                detected_mime = 'video/webm'
            else:
                # Fallback to mimetypes guess
                guessed_mime, _ = mimetypes.guess_type(video_file.filename)
                if guessed_mime and guessed_mime in ALLOWED_VIDEO_MIME_TYPES:
                    detected_mime = guessed_mime
            
            # Validate MIME type matches allowed types (only if detected)
            if detected_mime and detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
                return create_error_response(
                    FILE_VALIDATION_ERROR,
                    f'Invalid video file type. Detected MIME type: {detected_mime}. Allowed: {", ".join(sorted(ALLOWED_VIDEO_MIME_TYPES))}',
                    {
                        'field': 'video',
                        'detected_mime_type': detected_mime,
                        'allowed_mime_types': sorted(ALLOWED_VIDEO_MIME_TYPES),
                        'filename': video_file.filename
                    },
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate product
            is_valid, product, error_message = ReelsController.validate_product_for_reel(
                product_id, merchant.id
            )
            if not is_valid:
                return create_error_response(
                    PRODUCT_VALIDATION_ERROR,
                    error_message,
                    {'product_id': product_id, 'merchant_id': merchant.id},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Get reels S3 service (with proper error handling)
            try:
                reels_s3_service = get_reels_s3_service()
            except ValueError as ve:
                # Missing environment variables
                current_app.logger.error(f"S3 service initialization failed (missing config): {str(ve)}")
                return create_error_response(
                    STORAGE_ERROR,
                    'Storage service not configured properly',
                    {
                        'error_details': str(ve),
                        'suggestion': 'Please check AWS environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, CLOUDFRONT_REELS_BASE_URL)'
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                # Other initialization errors
                current_app.logger.error(f"S3 service initialization failed: {str(e)}", exc_info=True)
                return create_error_response(
                    STORAGE_ERROR,
                    'Failed to initialize storage service',
                    {
                        'error_details': str(e),
                        'suggestion': 'Please check AWS configuration and try again'
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
            # Create reel record first (without video URL) to get reel_id
            # This is needed because S3 key requires reel_id
            reel = None
            try:
                reel = Reel(
                    merchant_id=merchant.id,
                    product_id=product_id,
                    video_url='',  # Temporary, will be updated after upload
                    video_public_id='',  # Temporary, will be updated after upload
                    description=description,
                    approval_status='approved',
                    is_active=True
                )
                
                db.session.add(reel)
                db.session.flush()  # Flush to get reel_id without committing
                reel_id = reel.reel_id
                
                if not reel_id:
                    raise ValueError("Failed to generate reel_id")
                    
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to create reel record: {str(e)}", exc_info=True)
                return create_error_response(
                    TRANSACTION_ERROR,
                    'Failed to create reel record',
                    {
                        'error_details': str(e),
                        'suggestion': 'Please try again or contact support'
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
            # Upload video to S3 using the reel_id
            # Note: If this fails, we rollback the DB transaction
            upload_result = None
            try:
                upload_result = reels_s3_service.upload_reel_video(
                    video_file,
                    merchant_id=merchant.id,
                    product_id=product_id,
                    reel_id=reel_id,
                    file_extension=file_extension
                )
                
                # Validate upload result
                if not upload_result or 'url' not in upload_result or 's3_key' not in upload_result:
                    raise ValueError("Invalid upload result from S3 service")
                    
            except ValueError as ve:
                # Validation errors from S3 service
                db.session.rollback()
                current_app.logger.error(f"Video upload validation failed: {str(ve)}")
                return create_error_response(
                    STORAGE_ERROR,
                    'Video upload validation failed',
                    {
                        'error_details': str(ve),
                        'suggestion': 'Please check your file and try again'
                    },
                    HTTPStatus.BAD_REQUEST
                )
            except Exception as e:
                # Upload failed - rollback DB transaction
                db.session.rollback()
                current_app.logger.error(f"Video upload to S3 failed: {str(e)}", exc_info=True)
                return create_error_response(
                    STORAGE_ERROR,
                    'Video upload to storage failed',
                    {
                        'error_details': str(e),
                        'suggestion': 'Please try again or contact support if the problem persists'
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
            # Update reel with upload results
            try:
                reel.video_url = upload_result['url']
                reel.video_public_id = upload_result['s3_key']  # Store S3 key in video_public_id
                reel.file_size_bytes = upload_result.get('bytes', 0)
                reel.video_format = file_extension
                
                # Set thumbnail URL if generated
                current_app.logger.info("=" * 80)
                current_app.logger.info(f"[REELS_CONTROLLER] 📋 Updating reel record with thumbnail information...")
                current_app.logger.info(f"[REELS_CONTROLLER] 📋 Upload result keys: {list(upload_result.keys())}")
                current_app.logger.info(f"[REELS_CONTROLLER] 📋 thumbnail_url in result: {'thumbnail_url' in upload_result}")
                current_app.logger.info(f"[REELS_CONTROLLER] 📋 thumbnail_url value: {upload_result.get('thumbnail_url')}")
                
                if upload_result.get('thumbnail_url'):
                    reel.thumbnail_url = upload_result['thumbnail_url']
                    reel.thumbnail_public_id = upload_result.get('thumbnail_s3_key')
                    current_app.logger.info(f"[REELS_CONTROLLER] ✅ Thumbnail URL saved to database: {reel.thumbnail_url}")
                    current_app.logger.info(f"[REELS_CONTROLLER] ✅ Thumbnail S3 key saved: {reel.thumbnail_public_id}")
                else:
                    current_app.logger.warning(f"[REELS_CONTROLLER] ⚠️  No thumbnail_url in upload result. Thumbnail may not have been generated.")
                current_app.logger.info("=" * 80)
                
                # Commit the transaction
                db.session.commit()
            except Exception as e:
                # If DB commit fails, try to delete uploaded video from S3
                db.session.rollback()
                current_app.logger.error(f"Failed to update reel record: {str(e)}", exc_info=True)
                
                # Attempt cleanup of uploaded video (non-critical)
                if upload_result and upload_result.get('s3_key'):
                    try:
                        reels_s3_service.delete_reel_video(upload_result['s3_key'])
                        current_app.logger.info(f"Cleaned up uploaded video from S3: {upload_result['s3_key']}")
                    except Exception as cleanup_error:
                        current_app.logger.error(
                            f"Failed to cleanup uploaded video from S3: {str(cleanup_error)}",
                            exc_info=True
                        )
                
                return create_error_response(
                    TRANSACTION_ERROR,
                    'Failed to save reel record',
                    {
                        'error_details': str(e),
                        'suggestion': 'The video was uploaded but the record creation failed. Please contact support.'
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
            # Invalidate trending cache (new reel affects trending)
            # This is non-critical, so we don't fail if it doesn't work
            try:
                redis_client = get_redis_client(current_app)
                if redis_client:
                    # Invalidate trending feeds
                    pattern = "feed:trending:*"
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
                    # Invalidate all recommendation feeds (new reel might appear)
                    pattern = "feed:recommended:*"
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
            except Exception:
                pass  # Silently fail if cache invalidation fails
            
            return jsonify({
                'status': 'success',
                'message': 'Reel uploaded successfully.',
                'data': reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=None)
            }), HTTPStatus.CREATED
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Reel upload failed: {str(e)}")
            return create_error_response(
                REEL_UPLOAD_FAILED,
                'Reel upload failed due to an unexpected error',
                {
                    'error_details': str(e),
                    'suggestion': 'Please try again or contact support if the problem persists'
                },
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_reel(reel_id, track_view=True, view_duration=None):
        """
        Get a single reel by ID with disabling reasons.
        Automatically increments view count if track_view is True.
        If user is authenticated, includes whether the user has liked the reel.
        
        Args:
            reel_id: Reel ID
            track_view: Whether to increment view count (default: True)
            view_duration: Optional view duration in seconds (for tracking watch time)
            
        Returns:
            JSON response with reel data
        """
        try:
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            # Validate view_duration if provided
            if view_duration is not None:
                if view_duration < 0:
                    view_duration = None  # Invalid, ignore it
                elif reel.duration_seconds and view_duration > reel.duration_seconds:
                    # Cap at reel duration
                    view_duration = reel.duration_seconds
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Get reel data
            reel_data = reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=fields)
            
            # Check if user is authenticated and track view / check like status
            should_increment_view_count = False
            try:
                current_user_id = get_jwt_identity()
                if current_user_id:
                    # Track user view (for recommendations)
                    if track_view and reel.is_visible:
                        try:
                            # Check if user has already viewed this reel
                            has_viewed = UserReelView.has_user_viewed(current_user_id, reel_id)
                            
                            if not has_viewed:
                                # First view - increment count
                                should_increment_view_count = True
                            elif view_duration is not None:
                                # Re-watch: Check if view_duration is significantly different (re-watch)
                                existing_view = UserReelView.query.filter_by(
                                    user_id=current_user_id,
                                    reel_id=reel_id
                                ).first()
                                
                                if existing_view and existing_view.view_duration is not None:
                                    # Consider it a re-watch if duration increased by at least 25%
                                    duration_increase = view_duration - existing_view.view_duration
                                    if duration_increase > 0 and duration_increase >= (existing_view.view_duration * 0.25):
                                        should_increment_view_count = True
                                else:
                                    # Previous view had no duration, this one does - count as re-watch
                                    should_increment_view_count = True
                            
                            # Track/update user view
                            UserReelView.track_view(current_user_id, reel_id, view_duration=view_duration)
                            
                            # Update category preference based on view duration
                            if reel.product and reel.product.category_id:
                                try:
                                    # Calculate score based on watch percentage
                                    if view_duration is not None and reel.duration_seconds and reel.duration_seconds > 0:
                                        watch_percentage = min(1.0, view_duration / reel.duration_seconds)
                                        # Full watch (>80%) = 0.1, partial (50-80%) = 0.05, minimal (<50%) = 0.02
                                        if watch_percentage >= 0.8:
                                            score_delta = 0.1
                                        elif watch_percentage >= 0.5:
                                            score_delta = 0.05
                                        else:
                                            score_delta = 0.02
                                    else:
                                        # No duration provided, use default view score
                                        score_delta = 0.05
                                    
                                    UserCategoryPreference.update_preference(
                                        current_user_id,
                                        reel.product.category_id,
                                        score_delta,
                                        'view'
                                    )
                                except Exception as e:
                                    current_app.logger.warning(f"Failed to update category preference: {str(e)}")
                                    # Don't fail the view tracking if preference update fails
                            
                            db.session.commit()
                        except Exception as e:
                            current_app.logger.warning(f"Failed to track user view: {str(e)}")
                            db.session.rollback()
                    
                    # Check if user has liked this reel
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel_id)
                    reel_data['is_liked'] = is_liked
            except Exception:
                # User not authenticated or token invalid - always increment for unauthenticated users
                should_increment_view_count = True
                reel_data['is_liked'] = False
            
            # Increment view count if needed (for unauthenticated users or first view)
            if track_view and reel.is_visible and should_increment_view_count:
                try:
                    reel.increment_views()
                except Exception as e:
                    current_app.logger.warning(f"Failed to increment view count: {str(e)}")
            
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
            # Get current user (optional JWT for public endpoints)
            current_user_id = None
            is_own_reels = False
            
            # If merchant_id is None, we need JWT to get current user's merchant profile
            if merchant_id is None:
                # JWT is required when getting own reels
                try:
                    verify_jwt_in_request()
                    current_user_id = get_jwt_identity()
                    user = User.get_by_id(current_user_id)
                    if not user:
                        return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
                    
                    merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
                    if not merchant:
                        return jsonify({'error': 'Merchant profile not found'}), HTTPStatus.NOT_FOUND
                    merchant_id = merchant.id
                    is_own_reels = True
                except Exception as e:
                    return jsonify({'error': 'Authentication required to view own reels'}), HTTPStatus.UNAUTHORIZED
            else:
                # For public endpoint, JWT is optional - check if user is authenticated
                try:
                    verify_jwt_in_request(optional=True)
                    current_user_id = get_jwt_identity()
                except Exception:
                    # No JWT token present, which is fine for public endpoint
                    current_user_id = None
                
                # Check if requesting own reels (only if authenticated)
                merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
                if not merchant:
                    return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
                
                # Only check if own reels if user is authenticated
                if current_user_id:
                    is_own_reels = (merchant.user_id == current_user_id)
            
            # Build query with eager loading to prevent N+1 queries
            query = Reel.query.options(
                joinedload(Reel.product).joinedload(Product.category),
                joinedload(Reel.merchant)
            ).filter_by(merchant_id=merchant_id)
            
            # If not own reels or not including all, filter visible only
            if not is_own_reels or not include_all:
                query = Reel.get_visible_reels(query)
            
            # Get filter parameters
            category_id = request.args.get('category_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            sort_by = request.args.get('sort_by', 'newest')  # newest, likes, views, shares
            
            # Apply category filter
            if category_id:
                query = query.join(Product).filter(Product.category_id == category_id)
            
            # Apply date range filter
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at >= start_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid start_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'start_date', 'provided': start_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at <= end_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid end_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'end_date', 'provided': end_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            # Apply sorting
            sort_mapping = {
                'newest': desc(Reel.created_at),
                'likes': desc(Reel.likes_count),
                'views': desc(Reel.views_count),
                'shares': desc(Reel.shares_count)
            }
            
            order_by = sort_mapping.get(sort_by, desc(Reel.created_at))
            query = query.order_by(order_by)
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            reels_data = [reel.serialize(
                include_reasons=is_own_reels,  # Include reasons only for own reels
                include_product=True,
                include_merchant=True
            ) for reel in pagination.items]
            
            # Add is_liked status to each reel if user is authenticated
            for reel_data in reels_data:
                if current_user_id:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel_data['reel_id'])
                    reel_data['is_liked'] = is_liked
                else:
                    reel_data['is_liked'] = False
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                },
                'filters_applied': {
                    'category_id': category_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'sort_by': sort_by
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
        Supports filtering and sorting.
        
        Returns:
            JSON response with paginated reel list
        """
        try:
            # Get only visible reels with eager loading to prevent N+1 queries
            query = Reel.get_visible_reels()
            query = query.options(
                joinedload(Reel.product).joinedload(Product.category),
                joinedload(Reel.merchant)
            )
            
            # Get filter parameters
            category_id = request.args.get('category_id', type=int)
            merchant_id = request.args.get('merchant_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            sort_by = request.args.get('sort_by', 'newest')  # newest, likes, views, shares
            
            # Apply category filter
            if category_id:
                query = query.join(Product).filter(Product.category_id == category_id)
            
            # Apply merchant filter
            if merchant_id:
                query = query.filter(Reel.merchant_id == merchant_id)
            
            # Apply date range filter
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at >= start_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid start_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'start_date', 'provided': start_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at <= end_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid end_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'end_date', 'provided': end_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            # Apply sorting
            sort_mapping = {
                'newest': desc(Reel.created_at),
                'likes': desc(Reel.likes_count),
                'views': desc(Reel.views_count),
                'shares': desc(Reel.shares_count)
            }
            
            order_by = sort_mapping.get(sort_by, desc(Reel.created_at))
            query = query.order_by(order_by)
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            reels_data = [reel.serialize(
                include_reasons=False,  # Don't include reasons for public feed
                include_product=True,
                include_merchant=True,
                fields=fields
            ) for reel in pagination.items]
            
            # Check if user is authenticated and add is_liked status
            current_user_id = None
            try:
                verify_jwt_in_request(optional=True)
                current_user_id = get_jwt_identity()
            except Exception:
                # No JWT token present, which is fine for public endpoint
                current_user_id = None
            
            # Add is_liked status to each reel
            for reel_data in reels_data:
                if current_user_id:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel_data['reel_id'])
                    reel_data['is_liked'] = is_liked
                else:
                    reel_data['is_liked'] = False
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                },
                'filters_applied': {
                    'category_id': category_id,
                    'merchant_id': merchant_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'sort_by': sort_by
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
            
            # Update description in transaction
            try:
                reel.description = description
                reel.updated_at = datetime.now(timezone.utc)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to update reel in database: {str(e)}")
                return jsonify({'error': f'Failed to update reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
            return jsonify({
                'status': 'success',
                'message': 'Reel updated successfully',
                'data': reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=None)
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
            
            # Soft delete in transaction
            try:
                reel.deleted_at = datetime.now(timezone.utc)
                reel.updated_at = datetime.now(timezone.utc)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to delete reel in database: {str(e)}")
                return jsonify({'error': f'Failed to delete reel: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
            
            # Delete from S3 (non-critical, log but don't fail)
            # video_public_id stores the S3 key, but we can also extract from video_url
            if reel.video_url or reel.video_public_id:
                try:
                    reels_s3_service = get_reels_s3_service()
                    # Try video_public_id first (S3 key), then fallback to extracting from video_url
                    delete_key = reel.video_public_id if reel.video_public_id else reel.video_url
                    reels_s3_service.delete_reel_video(delete_key)
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete video from S3: {str(e)}")
                    # Don't fail the request if storage deletion fails
            
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
            
            # Get approved products with stock > 0, not variants, with eager loading of media
            # Using selectinload for media to avoid cartesian product issues
            products = Product.query.join(ProductStock).options(
                joinedload(Product.category),
                selectinload(Product.media)
            ).filter(
                Product.merchant_id == merchant.id,
                Product.deleted_at.is_(None),
                Product.active_flag == True,
                Product.approval_status == 'approved',
                Product.parent_product_id.is_(None),  # Only parent products
                ProductStock.stock_qty > 0
            ).all()
            
            products_data = []
            for product in products:
                # Get primary image (prefer is_main_image, fallback to first image by sort_order)
                primary_image = None
                if product.media:
                    # Filter for image type media only (exclude videos)
                    image_media = [m for m in product.media if m.type == MediaType.IMAGE and m.deleted_at is None]
                    
                    if image_media:
                        # First try to find main image
                        main_image = next((m for m in image_media if m.is_main_image), None)
                        if main_image:
                            primary_image = main_image.url
                        else:
                            # If no main image, get first image by sort_order
                            sorted_images = sorted(image_media, key=lambda m: m.sort_order)
                            if sorted_images:
                                primary_image = sorted_images[0].url
                
                products_data.append({
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'category_id': product.category_id,
                    'category_name': product.category.name if product.category else None,
                    'stock_qty': product.stock.stock_qty if product.stock else 0,
                    'selling_price': float(product.selling_price) if product.selling_price else None,
                    'primary_image': primary_image
                })
            
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
                
                # Update category preference (like = +0.3)
                try:
                    if reel.product and reel.product.category_id:
                        UserCategoryPreference.update_preference(
                            current_user_id,
                            reel.product.category_id,
                            0.3,
                            'like'
                        )
                except Exception as e:
                    current_app.logger.warning(f"Failed to update category preference: {str(e)}")
                    # Don't fail the like operation if preference update fails
                
                # Create or update notification for merchant (aggregated by reel)
                # Use savepoint to ensure notification failure doesn't affect like operation
                savepoint = db.session.begin_nested()
                try:
                    user_name = f"{user.first_name} {user.last_name}".strip()
                    MerchantNotification.get_or_create_reel_like_notification(
                        merchant_id=reel.merchant_id,
                        reel_id=reel.reel_id,
                        user_id=current_user_id,
                        user_name=user_name
                    )
                    savepoint.commit()
                except Exception as e:
                    savepoint.rollback()
                    current_app.logger.warning(f"Failed to create notification for reel like: {str(e)}")
                    # Don't fail the like operation if notification creation fails
                
                # Commit all changes together (like + notification if successful)
                db.session.commit()
                
                # Invalidate recommendation cache
                try:
                    redis_client = get_redis_client(current_app)
                    if redis_client:
                        # Invalidate user's recommendation feed
                        pattern = f"feed:recommended:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                except Exception:
                    pass  # Silently fail if cache invalidation fails
                
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
                
                # Decrease category preference (unlike = -0.15, half of like)
                try:
                    if reel.product and reel.product.category_id:
                        UserCategoryPreference.update_preference(
                            current_user_id,
                            reel.product.category_id,
                            -0.15,  # Negative delta to decrease preference
                            'unlike'
                        )
                except Exception as e:
                    current_app.logger.warning(f"Failed to update category preference: {str(e)}")
                    # Don't fail the unlike operation if preference update fails
                
                db.session.commit()
                
                # Invalidate recommendation cache
                try:
                    redis_client = get_redis_client(current_app)
                    if redis_client:
                        # Invalidate user's recommendation feed
                        pattern = f"feed:recommended:{current_user_id}:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                except Exception:
                    pass  # Silently fail if cache invalidation fails
                
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
        Share a reel (increment share count with user tracking).
        Requires authentication to track which user shares which reel.
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response with updated share count
        """
        try:
            # Get reel
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'Reel not found',
                    {'reel_id': reel_id},
                    HTTPStatus.NOT_FOUND
                )
            
            # Check if reel is visible
            if not reel.is_visible:
                return create_error_response(
                    VALIDATION_ERROR,
                    'Reel is not available',
                    {'reel_id': reel_id, 'disabling_reasons': reel.get_disabling_reasons()},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Get current user (optional - allow unauthenticated shares but track if authenticated)
            current_user_id = None
            try:
                verify_jwt_in_request(optional=True)
                current_user_id = get_jwt_identity()
            except Exception:
                # User not authenticated - still allow share but don't track user
                current_user_id = None
            
            # Track user share if authenticated
            if current_user_id:
                try:
                    UserReelShare.create_share(current_user_id, reel_id)
                except Exception as e:
                    current_app.logger.warning(f"Failed to track user share: {str(e)}")
                    # Don't fail the share operation if tracking fails
            
            # Increment share count
            try:
                reel.increment_shares()
                db.session.commit()  # Always commit, regardless of authentication
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to increment share count: {str(e)}")
                return create_error_response(
                    TRANSACTION_ERROR,
                    'Failed to track share',
                    {'error_details': str(e)},
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
            return jsonify({
                'status': 'success',
                'message': 'Reel share tracked successfully',
                'data': {
                    'reel_id': reel.reel_id,
                    'shares_count': reel.shares_count,
                    'user_tracked': current_user_id is not None
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Share reel failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to track share',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_user_reel_stats():
        """
        Get user's reel interaction statistics.
        Returns counts of likes, views, follows, and determines if user is new.
        
        Returns:
            JSON response with user stats
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), HTTPStatus.NOT_FOUND
            
            # Calculate user stats
            likes_count = UserReelLike.query.filter_by(user_id=current_user_id).count()
            views_count = UserReelView.query.filter_by(user_id=current_user_id).count()
            follows_count = UserMerchantFollow.query.filter_by(user_id=current_user_id).count()
            total_interactions = likes_count + views_count + follows_count
            
            # Determine if new user
            # User is "new" if account created in last 7 days OR less than 3 interactions
            account_age = datetime.now(timezone.utc) - user.created_at
            is_new_user = account_age < timedelta(days=7) or total_interactions < 3
            
            return jsonify({
                'status': 'success',
                'data': {
                    'is_new_user': is_new_user,
                    'reel_stats': {
                        'likes_count': likes_count,
                        'views_count': views_count,
                        'follows_count': follows_count,
                        'total_interactions': total_interactions
                    },
                    'account_info': {
                        'account_age_days': account_age.days,
                        'created_at': user.created_at.isoformat() if user.created_at else None,
                        'last_login': user.last_login.isoformat() if user.last_login else None
                    }
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get user reel stats failed: {str(e)}")
            return jsonify({'error': f'Failed to get user stats: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_recently_viewed_reels():
        """
        Get recently viewed reels for the authenticated user.
        Returns reels ordered by most recently viewed first.
        Works for both regular users and merchants.
        
        Returns:
            JSON response with paginated reel list including viewed_at timestamp
        """
        try:
            # Get authenticated user ID
            current_user_id = get_jwt_identity()
            if not current_user_id:
                return jsonify({'error': 'Authentication required'}), HTTPStatus.UNAUTHORIZED
            
            # Convert to int if it's a string
            if isinstance(current_user_id, str):
                current_user_id = int(current_user_id)
            
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Query user's viewed reels, ordered by most recent view
            # Join with Reel to get full reel data and filter for visible reels only
            query = db.session.query(UserReelView, Reel).join(
                Reel, UserReelView.reel_id == Reel.reel_id
            ).filter(
                UserReelView.user_id == current_user_id,
                Reel.deleted_at == None,
                Reel.is_active == True,
                Reel.approval_status == 'approved'
            ).order_by(
                desc(UserReelView.viewed_at)
            )
            
            # Get total count before pagination
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            paginated_results = query.offset(offset).limit(per_page).all()
            
            # Serialize reels with viewed_at timestamp
            reels_data = []
            for user_view, reel in paginated_results:
                # Check if reel is visible (no disabling reasons)
                if not reel.is_visible:
                    continue  # Skip reels that shouldn't be visible
                
                # Serialize reel
                reel_data = reel.serialize(
                    include_reasons=False,
                    include_product=True,
                    include_merchant=True,
                    fields=fields
                )
                
                # Add viewed_at timestamp
                reel_data['viewed_at'] = user_view.viewed_at.isoformat() if user_view.viewed_at else None
                
                # Add view_duration if available
                if user_view.view_duration is not None:
                    reel_data['view_duration'] = user_view.view_duration
                
                # Check if user has liked this reel
                is_liked = UserReelLike.user_has_liked(current_user_id, reel.reel_id)
                reel_data['is_liked'] = is_liked
                
                reels_data.append(reel_data)
            
            # Calculate pagination info
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            
            return jsonify({
                'status': 'success',
                'data': {
                    'reels': reels_data,
                    'pagination': {
                        'total': total,
                        'pages': pages,
                        'current_page': page,
                        'per_page': per_page,
                        'has_next': page < pages,
                        'has_prev': page > 1
                    }
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get recently viewed reels failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'Failed to get recently viewed reels: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def track_reel_view(reel_id, view_duration=None):
        """
        Track a reel view for the authenticated user.
        This is a dedicated endpoint for mobile apps to track views independently.
        
        Args:
            reel_id: Reel ID to track
            view_duration: Optional view duration in seconds
            
        Returns:
            JSON response with success status
        """
        try:
            # Get authenticated user
            current_user_id = get_jwt_identity()
            if not current_user_id:
                return jsonify({'error': 'Authentication required'}), HTTPStatus.UNAUTHORIZED
            
            # Convert to int if string
            if isinstance(current_user_id, str):
                current_user_id = int(current_user_id)
            
            # Verify reel exists and is visible
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return jsonify({'error': 'Reel not found'}), HTTPStatus.NOT_FOUND
            
            if not reel.is_visible:
                return jsonify({'error': 'Reel is not available'}), HTTPStatus.BAD_REQUEST
            
            # Validate view_duration if provided
            if view_duration is not None:
                if view_duration < 0:
                    view_duration = None
                elif reel.duration_seconds and view_duration > reel.duration_seconds:
                    view_duration = reel.duration_seconds  # Cap at reel duration
            
            # Track the view (this will also cleanup old views)
            UserReelView.track_view(current_user_id, reel_id, view_duration=view_duration)
            
            # Update category preference if applicable
            if reel.product and reel.product.category_id:
                try:
                    from models.user_category_preference import UserCategoryPreference
                    
                    if view_duration is not None and reel.duration_seconds and reel.duration_seconds > 0:
                        watch_percentage = min(1.0, view_duration / reel.duration_seconds)
                        if watch_percentage >= 0.8:
                            score_delta = 0.1
                        elif watch_percentage >= 0.5:
                            score_delta = 0.05
                        else:
                            score_delta = 0.02
                    else:
                        score_delta = 0.05
                    
                    UserCategoryPreference.update_preference(
                        current_user_id,
                        reel.product.category_id,
                        score_delta,
                        'view'
                    )
                except Exception as e:
                    current_app.logger.warning(f"Failed to update category preference: {str(e)}")
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'View tracked successfully'
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Track reel view failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'Failed to track view: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def get_user_shared_reels():
        """
        Get reels that the current user has shared.
        
        Returns:
            JSON response with paginated list of shared reels
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'User not found',
                    {},
                    HTTPStatus.NOT_FOUND
                )
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Get user's shared reels
            shared_records = UserReelShare.get_user_shared_reels(current_user_id)
            
            # Paginate
            total = len(shared_records)
            pages = (total + per_page - 1) // per_page if total > 0 else 0
            start = (page - 1) * per_page
            end = start + per_page
            paginated_records = shared_records[start:end]
            
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            # Serialize reel data
            reels_data = []
            for share_record in paginated_records:
                reel = share_record.reel
                if reel:
                    reel_data = reel.serialize(include_reasons=False, include_product=True, include_merchant=True, fields=fields)
                    if not fields or 'shared_at' in fields:
                        reel_data['shared_at'] = share_record.shared_at.isoformat() if share_record.shared_at else None
                    # Add is_liked status (user is authenticated in this endpoint)
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel.reel_id)
                    reel_data['is_liked'] = is_liked
                    reels_data.append(reel_data)
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get user shared reels failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to get shared reels',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def search_reels():
        """
        Search reels by description, product name, or merchant name.
        Uses MySQL FULLTEXT search on description field.
        
        Returns:
            JSON response with paginated search results
        """
        try:
            # Get search query
            search_query = request.args.get('q', '').strip()
            if not search_query:
                return create_error_response(
                    VALIDATION_ERROR,
                    'Search query is required',
                    {'field': 'q', 'required': True},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Get filter parameters
            category_id = request.args.get('category_id', type=int)
            merchant_id = request.args.get('merchant_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Build base query - only visible reels
            # get_visible_reels() already joins Product and ProductStock, so we only need to join MerchantProfile
            query = Reel.get_visible_reels()
            query = query.join(MerchantProfile, Reel.merchant_id == MerchantProfile.id)
            query = query.options(
                joinedload(Reel.product).joinedload(Product.category),
                joinedload(Reel.merchant)
            )
            
            # Apply search across multiple fields: description, product name, merchant name
            # We'll search in: reels.description, products.product_name, merchant_profiles.business_name
            from sqlalchemy import text, or_
            
            # Escape special characters for MySQL FULLTEXT
            search_terms = search_query.replace('"', '\\"')
            search_like = f'%{search_query}%'
            
            # Build search conditions - try FULLTEXT on description, LIKE on product/merchant names
            # Use OR to search across all fields
            search_conditions = [
                text("MATCH(reels.description) AGAINST(:search_query IN BOOLEAN MODE)"),
                Product.product_name.like(search_like),
                MerchantProfile.business_name.like(search_like)
            ]
            
            query = query.filter(or_(*search_conditions)).params(search_query=search_terms)
            
            # Apply category filter
            if category_id:
                query = query.filter(Product.category_id == category_id)
            
            # Apply merchant filter
            if merchant_id:
                query = query.filter(Reel.merchant_id == merchant_id)
            
            # Apply date range filter
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at >= start_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid start_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'start_date', 'provided': start_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at <= end_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid end_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'end_date', 'provided': end_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            # Order by created_at
            query = query.order_by(desc(Reel.created_at))
            
            # Paginate - catch FULLTEXT error here and fallback to LIKE
            try:
                pagination = query.paginate(
                    page=page,
                    per_page=per_page,
                    error_out=False
                )
            except Exception as e:
                # If FULLTEXT index doesn't exist, fallback to LIKE search
                error_str = str(e)
                if 'FULLTEXT' in error_str or '1191' in error_str:
                    current_app.logger.warning(f"FULLTEXT index not found, falling back to LIKE search: {str(e)}")
                    # Rebuild query with LIKE instead of FULLTEXT
                    # get_visible_reels() already joins Product and ProductStock
                    query = Reel.get_visible_reels()
                    query = query.join(MerchantProfile, Reel.merchant_id == MerchantProfile.id)
                    query = query.options(
                        joinedload(Reel.product).joinedload(Product.category),
                        joinedload(Reel.merchant)
                    )
                    # Use LIKE search across all fields
                    search_like = f'%{search_query}%'
                    query = query.filter(or_(
                        Reel.description.like(search_like),
                        Product.product_name.like(search_like),
                        MerchantProfile.business_name.like(search_like)
                    ))
                    
                    # Reapply filters
                    if category_id:
                        query = query.filter(Product.category_id == category_id)
                    if merchant_id:
                        query = query.filter(Reel.merchant_id == merchant_id)
                    if start_date:
                        try:
                            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                            query = query.filter(Reel.created_at >= start_dt)
                        except ValueError:
                            pass
                    if end_date:
                        try:
                            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            query = query.filter(Reel.created_at <= end_dt)
                        except ValueError:
                            pass
                    
                    query = query.order_by(desc(Reel.created_at))
                    pagination = query.paginate(
                        page=page,
                        per_page=per_page,
                        error_out=False
                    )
                else:
                    # Re-raise if it's a different error
                    raise
            
            # Serialize results
            # Get fields parameter for field selection
            fields_param = request.args.get('fields')
            fields = None
            if fields_param:
                fields = [f.strip() for f in fields_param.split(',') if f.strip()]
            
            reels_data = [reel.serialize(
                include_reasons=False,
                include_product=True,
                include_merchant=True,
                fields=fields
            ) for reel in pagination.items]
            
            # Check if user is authenticated and add is_liked status
            current_user_id = None
            try:
                verify_jwt_in_request(optional=True)
                current_user_id = get_jwt_identity()
            except Exception:
                # No JWT token present, which is fine for public search
                current_user_id = None
            
            # Add is_liked status to each reel
            for reel_data in reels_data:
                if current_user_id:
                    is_liked = UserReelLike.user_has_liked(current_user_id, reel_data['reel_id'])
                    reel_data['is_liked'] = is_liked
                else:
                    reel_data['is_liked'] = False
            
            return jsonify({
                'status': 'success',
                'data': reels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                },
                'search_info': {
                    'query': search_query,
                    'filters': {
                        'category_id': category_id,
                        'merchant_id': merchant_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Search reels failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to search reels',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_merchant_reel_analytics():
        """
        Get merchant's reel analytics including aggregated stats and per-reel statistics.
        
        Returns:
            JSON response with analytics data
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'User not found',
                    {},
                    HTTPStatus.NOT_FOUND
                )
            
            # Get merchant
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant:
                return create_error_response(
                    AUTHORIZATION_ERROR,
                    'Merchant profile not found',
                    {},
                    HTTPStatus.FORBIDDEN
                )
            
            # Get query parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            sort_by = request.args.get('sort_by', 'created_at')  # created_at, views, likes, shares, engagement
            
            # Build query for merchant's reels
            query = Reel.query.filter_by(merchant_id=merchant.id)
            
            # Apply date range filter if provided
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at >= start_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid start_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'start_date', 'provided': start_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Reel.created_at <= end_dt)
                except ValueError:
                    return create_error_response(
                        VALIDATION_ERROR,
                        'Invalid end_date format. Use ISO format (e.g., 2024-01-01T00:00:00Z)',
                        {'field': 'end_date', 'provided': end_date},
                        HTTPStatus.BAD_REQUEST
                    )
            
            # Get all reels for aggregated stats (before pagination)
            all_reels = query.all()
            
            # Calculate aggregated stats
            total_reels = len(all_reels)
            total_views = sum(reel.views_count for reel in all_reels)
            total_likes = sum(reel.likes_count for reel in all_reels)
            total_shares = sum(reel.shares_count for reel in all_reels)
            
            # Calculate engagement rate: (likes + shares) / views (avoid division by zero)
            engagement_rate = 0.0
            if total_views > 0:
                engagement_rate = ((total_likes + total_shares) / total_views) * 100
            
            # Apply sorting
            valid_sort_fields = {
                'created_at': Reel.created_at,
                'views': Reel.views_count,
                'likes': Reel.likes_count,
                'shares': Reel.shares_count,
                'engagement': None  # Will calculate separately
            }
            
            if sort_by == 'engagement':
                # Sort by engagement rate (likes + shares) / views
                all_reels.sort(
                    key=lambda r: ((r.likes_count + r.shares_count) / r.views_count) if r.views_count > 0 else 0,
                    reverse=True
                )
            elif sort_by in valid_sort_fields:
                if sort_by in ['views', 'likes', 'shares']:
                    query = query.order_by(desc(valid_sort_fields[sort_by]))
                else:
                    query = query.order_by(desc(valid_sort_fields[sort_by]))
                all_reels = query.all()
            
            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            paginated_reels = all_reels[start:end]
            
            # Build per-reel stats
            reel_stats = []
            for reel in paginated_reels:
                reel_engagement = 0.0
                if reel.views_count > 0:
                    reel_engagement = ((reel.likes_count + reel.shares_count) / reel.views_count) * 100
                
                reel_stats.append({
                    'reel_id': reel.reel_id,
                    'product_id': reel.product_id,
                    'product_name': reel.product.product_name if reel.product else None,
                    'description': reel.description[:100] + '...' if len(reel.description) > 100 else reel.description,
                    'views_count': reel.views_count,
                    'likes_count': reel.likes_count,
                    'shares_count': reel.shares_count,
                    'engagement_rate': round(reel_engagement, 2),
                    'is_visible': reel.is_visible,
                    'disabling_reasons': reel.get_disabling_reasons(),
                    'created_at': reel.created_at.isoformat() if reel.created_at else None
                })
            
            # Calculate total pages
            total_pages = (total_reels + per_page - 1) // per_page if total_reels > 0 else 0
            
            return jsonify({
                'status': 'success',
                'data': {
                    'aggregated_stats': {
                        'total_reels': total_reels,
                        'total_views': total_views,
                        'total_likes': total_likes,
                        'total_shares': total_shares,
                        'average_engagement_rate': round(engagement_rate, 2),
                        'average_views_per_reel': round(total_views / total_reels, 2) if total_reels > 0 else 0,
                        'average_likes_per_reel': round(total_likes / total_reels, 2) if total_reels > 0 else 0
                    },
                    'reel_stats': reel_stats,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': total_reels,
                        'pages': total_pages
                    },
                    'filters_applied': {
                        'start_date': start_date,
                        'end_date': end_date,
                        'sort_by': sort_by
                    }
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get merchant reel analytics failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to get reel analytics',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_merchant_reel_stats(merchant_id):
        """
        Get aggregated reel statistics for a merchant (public endpoint).
        Returns total counts of reels, likes, views, and shares.
        
        Args:
            merchant_id: Merchant ID to get stats for
            
        Returns:
            JSON response with aggregated stats
        """
        try:
            # Check if merchant exists
            merchant = MerchantProfile.query.filter_by(id=merchant_id).first()
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), HTTPStatus.NOT_FOUND
            
            # Get all visible reels for this merchant using the get_visible_reels filter
            base_query = Reel.query.filter_by(merchant_id=merchant_id)
            visible_reels_query = Reel.get_visible_reels(base_query)
            visible_reels = visible_reels_query.all()
            
            # Calculate aggregated stats
            total_reels = len(visible_reels)
            total_views = sum(reel.views_count for reel in visible_reels)
            total_likes = sum(reel.likes_count for reel in visible_reels)
            total_shares = sum(reel.shares_count for reel in visible_reels)
            
            return jsonify({
                'status': 'success',
                'data': {
                    'merchant_id': merchant_id,
                    'total_reels': total_reels,
                    'total_likes': total_likes,
                    'total_views': total_views,
                    'total_shares': total_shares
                }
            }), HTTPStatus.OK
            
        except Exception as e:
            current_app.logger.error(f"Get merchant reel stats failed: {str(e)}")
            return jsonify({'error': f'Failed to get reel stats: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    @staticmethod
    def batch_delete_reels():
        """
        Delete multiple reels in a batch operation.
        All reels must belong to the current merchant.
        
        Request body:
        {
            "reel_ids": [1, 2, 3]
        }
        
        Returns:
            JSON response with results for each reel
        """
        try:
            # Get current user
            current_user_id = get_jwt_identity()
            user = User.get_by_id(current_user_id)
            if not user:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'User not found',
                    {},
                    HTTPStatus.NOT_FOUND
                )
            
            # Get merchant
            merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
            if not merchant:
                return create_error_response(
                    AUTHORIZATION_ERROR,
                    'Merchant profile not found',
                    {},
                    HTTPStatus.FORBIDDEN
                )
            
            # Get request data
            data = request.get_json()
            if not data or 'reel_ids' not in data:
                return create_error_response(
                    VALIDATION_ERROR,
                    'reel_ids array is required',
                    {'field': 'reel_ids'},
                    HTTPStatus.BAD_REQUEST
                )
            
            reel_ids = data['reel_ids']
            if not isinstance(reel_ids, list):
                return create_error_response(
                    VALIDATION_ERROR,
                    'reel_ids must be an array',
                    {'field': 'reel_ids', 'provided': type(reel_ids).__name__},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Limit batch size
            if len(reel_ids) > 50:
                return create_error_response(
                    VALIDATION_ERROR,
                    'Maximum 50 reels can be deleted in one batch',
                    {'field': 'reel_ids', 'count': len(reel_ids), 'max': 50},
                    HTTPStatus.BAD_REQUEST
                )
            
            if len(reel_ids) == 0:
                return create_error_response(
                    VALIDATION_ERROR,
                    'reel_ids array cannot be empty',
                    {'field': 'reel_ids'},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Validate all reels exist and belong to merchant
            reels = Reel.query.filter(
                Reel.reel_id.in_(reel_ids),
                Reel.merchant_id == merchant.id
            ).all()
            
            found_reel_ids = {reel.reel_id for reel in reels}
            missing_reel_ids = set(reel_ids) - found_reel_ids
            
            if missing_reel_ids:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'Some reels not found or do not belong to you',
                    {
                        'field': 'reel_ids',
                        'missing_or_unauthorized': list(missing_reel_ids),
                        'found': list(found_reel_ids)
                    },
                    HTTPStatus.NOT_FOUND
                )
            
            # Process deletion in transaction
            results = []
            reels_s3_service = get_reels_s3_service()
            
            try:
                for reel in reels:
                    try:
                        # Soft delete
                        reel.deleted_at = datetime.now(timezone.utc)
                        reel.updated_at = datetime.now(timezone.utc)
                        
                        # Delete from S3 (non-critical)
                        # video_public_id stores the S3 key, but we can also extract from video_url
                        if reel.video_url or reel.video_public_id:
                            try:
                                delete_key = reel.video_public_id if reel.video_public_id else reel.video_url
                                reels_s3_service.delete_reel_video(delete_key)
                            except Exception as e:
                                current_app.logger.warning(f"Failed to delete video from S3 for reel {reel.reel_id}: {str(e)}")
                        
                        results.append({
                            'reel_id': reel.reel_id,
                            'status': 'success',
                            'message': 'Reel deleted successfully'
                        })
                    except Exception as e:
                        current_app.logger.error(f"Failed to delete reel {reel.reel_id}: {str(e)}")
                        results.append({
                            'reel_id': reel.reel_id,
                            'status': 'error',
                            'message': f'Failed to delete reel: {str(e)}'
                        })
                
                db.session.commit()
                
                success_count = sum(1 for r in results if r['status'] == 'success')
                
                return jsonify({
                    'status': 'success',
                    'message': f'Batch delete completed: {success_count}/{len(reel_ids)} reels deleted',
                    'data': {
                        'results': results,
                        'summary': {
                            'total': len(reel_ids),
                            'successful': success_count,
                            'failed': len(reel_ids) - success_count
                        }
                    }
                }), HTTPStatus.OK
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Batch delete failed: {str(e)}")
                return create_error_response(
                    TRANSACTION_ERROR,
                    'Batch delete operation failed',
                    {'error_details': str(e)},
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch delete reels failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to process batch delete',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def approve_reel(reel_id):
        """
        Approve a reel (admin only).
        Note: Reels are auto-approved, but this endpoint exists for potential future use.
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response
        """
        try:
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'Reel not found',
                    {'reel_id': reel_id},
                    HTTPStatus.NOT_FOUND
                )
            
            # Update approval status
            reel.approval_status = 'approved'
            reel.approved_at = datetime.now(timezone.utc)
            reel.approved_by = get_jwt_identity()
            reel.rejection_reason = None
            reel.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel approved successfully',
                'data': reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=None)
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Approve reel failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to approve reel',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def reject_reel(reel_id):
        """
        Reject a reel with reason (admin only).
        
        Args:
            reel_id: Reel ID
            
        Request body:
        {
            "rejection_reason": "Violates community guidelines"
        }
        
        Returns:
            JSON response
        """
        try:
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'Reel not found',
                    {'reel_id': reel_id},
                    HTTPStatus.NOT_FOUND
                )
            
            # Get rejection reason
            data = request.get_json()
            rejection_reason = data.get('rejection_reason', '').strip() if data else ''
            
            if not rejection_reason:
                return create_error_response(
                    VALIDATION_ERROR,
                    'rejection_reason is required',
                    {'field': 'rejection_reason'},
                    HTTPStatus.BAD_REQUEST
                )
            
            if len(rejection_reason) > 255:
                return create_error_response(
                    VALIDATION_ERROR,
                    'rejection_reason must be 255 characters or less',
                    {'field': 'rejection_reason', 'length': len(rejection_reason)},
                    HTTPStatus.BAD_REQUEST
                )
            
            # Update approval status
            reel.approval_status = 'rejected'
            reel.rejection_reason = rejection_reason
            reel.approved_by = get_jwt_identity()
            reel.updated_at = datetime.now(timezone.utc)
            # Note: approved_at remains None for rejected reels
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Reel rejected successfully',
                'data': reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=None)
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Reject reel failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to reject reel',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def hide_reel(reel_id):
        """
        Hide a reel from public view (admin only).
        
        Args:
            reel_id: Reel ID
            
        Returns:
            JSON response
        """
        try:
            reel = Reel.query.filter_by(reel_id=reel_id).first()
            if not reel:
                return create_error_response(
                    NOT_FOUND_ERROR,
                    'Reel not found',
                    {'reel_id': reel_id},
                    HTTPStatus.NOT_FOUND
                )
            
            # Hide reel
            reel.is_active = False
            reel.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            # Invalidate caches
            try:
                redis_client = get_redis_client(current_app)
                if redis_client:
                    pattern = "feed:*"
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
            except Exception:
                pass
            
            return jsonify({
                'status': 'success',
                'message': 'Reel hidden successfully',
                'data': reel.serialize(include_reasons=True, include_product=True, include_merchant=True, fields=None)
            }), HTTPStatus.OK
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Hide reel failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to hide reel',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_pending_reels():
        """
        Get pending reels for moderation (admin only).
        Note: Since reels are auto-approved, this will return empty unless approval is enabled.
        
        Returns:
            JSON response with paginated list of pending reels
        """
        try:
            # Get query parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            per_page = min(per_page, 100)  # Max 100 per page
            
            # Query pending reels (if approval is required in future)
            query = Reel.query.filter(
                Reel.approval_status == 'pending',
                Reel.deleted_at.is_(None)
            )
            
            # Pagination
            pagination = query.order_by(desc(Reel.created_at)).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            reels_data = [reel.serialize(
                include_reasons=True,
                include_product=True,
                include_merchant=True
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
            current_app.logger.error(f"Get pending reels failed: {str(e)}")
            return create_error_response(
                TRANSACTION_ERROR,
                'Failed to get pending reels',
                {'error_details': str(e)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )

