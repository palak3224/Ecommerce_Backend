from flask import Flask, jsonify, request,make_response, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from common.cache import cached
import cloudinary
import cloudinary.uploader
import cloudinary.api
from config import get_config
from common.database import db
from common.cache import cache
from auth.routes import auth_bp
from auth.document_route import document_bp
from auth.country_route import country_bp
from api.users.routes import users_bp
from api.merchants.routes import merchants_bp
from auth import email_init
from models import *  # Import all models
from models.system_monitoring import SystemMonitoring

from routes.superadmin_routes import superadmin_bp
from routes.merchant_routes import merchant_dashboard_bp
from routes.product_routes import product_bp
from routes.category_routes import category_bp
from routes.brand_routes import brand_bp
from routes.homepage_routes import homepage_bp
from routes.cart_routes import cart_bp
from routes.wishlist_routes import wishlist_bp
from routes.order_routes import order_bp
from routes.user_address_routes import user_address_bp
from routes.currency_routes import currency_bp
from routes.feature_product_routes import feature_product_bp

from routes.promo_product_routes import promo_product_bp
from auth.admin_routes import admin_bp
from routes.payment_card_routes import payment_card_bp
from routes.review_routes import review_bp
from routes.analytics_routes import analytics_bp

from routes.merchant_support_routes import merchant_support_bp
from routes.admin_support_routes import admin_support_bp
from routes.user_support_routes import user_support_bp
from routes.promotion_routes import superadmin_promotion_bp
from routes.promo_code_routes import promo_code_bp
from routes.merchant_transaction_routes import merchant_transaction_bp

from routes.games_routes import games_bp
from routes.shiprocket_routes import shiprocket_bp
from routes.live_stream_public_routes import live_stream_public_bp
from routes.shop.shop_product_routes import shop_product_bp
from routes.shop.shop_routes import shop_bp
from routes.shop.shop_category_routes import shop_category_bp
from routes.shop.shop_brand_routes import shop_brand_bp
from routes.shop.shop_attribute_routes import shop_attribute_bp
from routes.shop.shop_stock_routes import shop_stock_bp
from routes.shop.variant_routes import variant_bp
from routes.shop.shop_review_routes import shop_review_bp

# Public shop routes
from routes.shop.public.public_shop_routes import public_shop_bp
from routes.shop.public.public_shop_product_routes import public_shop_product_bp
from routes.shop.public.public_shop_category_routes import public_shop_category_bp
from routes.shop.public.public_shop_brand_routes import public_shop_brand_bp
from routes.shop.public.public_shop_cart_routes import public_shop_cart_bp
from routes.shop.public.public_shop_wishlsit_routes import public_shop_wishlist_bp
from routes.shop.public.public_shop_order_routes import public_shop_order_bp

from routes.upload_routes import upload_bp
from routes.translate_routes import translate_bp
from routes.razorpay_routes import razorpay_bp
from routes.ai_image_upload import ai_image_upload_bp
from routes.reels_routes import reels_bp
from routes.follow_routes import follow_bp
from routes.recommendation_routes import recommendation_bp
from routes.notification_routes import notification_bp


from flasgger import Swagger
from cryptography.fernet import Fernet
import time
import psutil
import traceback
import platform
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from services.notification_cleanup_service import NotificationCleanupService
from controllers.newsletter_public_controller import newsletter_public_bp
from routes.holi_giveaway_routes import holi_giveaway_bp
from flask import send_from_directory as flask_send_from_directory

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://kea.mywire.org:5300",
    "https://aoinstore.com",
    "https://www.aoinstore.com",
]

def add_headers(response):
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = 'null'  # or omit completely if strict
   
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRF-Token'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '3600'  # Cache preflight requests for 1 hour
    return response

def create_app(config_name='default'):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(get_config())
    # Set max content length for file uploads (100MB for videos)
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
    # Increase request timeout for large file uploads (10 minutes)
    # Note: This is for the development server. Production servers (gunicorn, uwsgi) have their own timeout settings
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Don't cache uploaded files
    
    # Configure werkzeug to handle large file uploads better
    # Increase the max form data size (default is usually 16MB)
    from werkzeug.formparser import default_stream_factory
    import tempfile
    import os
    
    # Use a larger buffer for multipart parsing
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
    
    # Configure werkzeug to use a larger buffer for multipart parsing
    # This helps prevent ClientDisconnected errors
    try:
        # Set environment variable for werkzeug
        os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    except:
        pass
    
    # app.config['CARD_ENCRYPTION_KEY'] = Fernet.generate_key()  

    # Configure Cloudinary
    cloudinary.config(
        cloud_name=app.config.get('CLOUDINARY_CLOUD_NAME'),
        api_key=app.config.get('CLOUDINARY_API_KEY'),
        api_secret=app.config.get('CLOUDINARY_API_SECRET'),
        secure=True
    )

    # Configure Swagger
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs"
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Ecommerce Backend API",
            "description": "API documentation for Ecommerce Backend",
            "version": "1.0.0",
            "contact": {
                "email": "Scalixity@gmail.com"
            }
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
            }
        },
        "security": [
            {
                "Bearer": []
            }
        ]
    }

    Swagger(app, config=swagger_config, template=swagger_template)

    # Configure CORS with more specific settings
    # IMPORTANT: For file uploads, we need to allow all headers and methods
    CORS(app, 
         resources={
             r"/api/*": {
                 "origins": ALLOWED_ORIGINS,
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                 "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token", "Accept"],
                 "expose_headers": ["Content-Type", "Authorization"]
             }
         },
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "Accept"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         max_age=3600)  # Cache preflight requests for 1 hour

    # Initialize extensions
    db.init_app(app)
    
    # Add teardown handler to ensure database sessions are properly closed after each request
    # This is CRITICAL to prevent connection leaks that cause ALL APIs to hang
    @app.teardown_appcontext
    def close_db(error):
        """
        Close database session after each request to prevent connection leaks.
        This runs after EVERY request (success or failure) and ensures sessions are cleaned up.
        Without this, database connections accumulate and eventually ALL APIs stop responding.
        """
        try:
            # Always rollback any pending transactions first
            if db.session.is_active:
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    app.logger.warning(f"Error during rollback in teardown: {str(rollback_error)}")
            
            # Always remove the session to return connection to pool
            # This is the most important step - it releases the connection back to the pool
            db.session.remove()
        except Exception as e:
            app.logger.error(f"Critical error closing database session: {str(e)}", exc_info=True)
            # Force remove even if there's an error - we MUST release the connection
            try:
                db.session.remove()
            except:
                pass
    
    # Initialize cache - use null cache (no Redis required)
    # Set CACHE_TYPE to null BEFORE init_app to prevent any Redis connection attempts
    app.config['CACHE_TYPE'] = 'null'
    app.config.pop('REDIS_URL', None)  # Remove REDIS_URL to prevent Flask-Caching from trying to connect
    app.config.pop('CACHE_REDIS_URL', None)  # Remove CACHE_REDIS_URL as well
    try:
        cache.init_app(app)
    except Exception as e:
        # If cache initialization fails, just continue - caching is optional
        app.logger.warning(f"Cache initialization failed (non-critical): {str(e)}")
    
    jwt = JWTManager(app)
    email_init.init_app(app)
    migrate = Migrate(app, db)

    # Check ffmpeg availability for reel thumbnail generation
    def check_ffmpeg_availability():
        """Check if ffmpeg is available for thumbnail generation."""
        import shutil
        import subprocess
        
        app.logger.info("=" * 80)
        app.logger.info("🔍 CHECKING FFMPEG AVAILABILITY FOR REEL THUMBNAIL GENERATION")
        app.logger.info("=" * 80)
        
        # Get current PATH
        current_path = os.environ.get('PATH', 'Not set')
        app.logger.info(f"📍 Current PATH: {current_path}")
        
        # Try to find ffmpeg using multiple methods
        ffmpeg_path = None
        possible_paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/bin/ffmpeg',
            'ffmpeg'  # Try PATH as fallback
        ]
        
        # Method 1: Use shutil.which (most reliable)
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                app.logger.info(f"✅ Found ffmpeg using shutil.which: {ffmpeg_path}")
        except Exception as e:
            app.logger.warning(f"⚠️  shutil.which failed: {str(e)}")
        
        # Method 2: Check common paths
        if not ffmpeg_path:
            app.logger.info("📍 shutil.which didn't find ffmpeg, checking common paths...")
            for path in possible_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    ffmpeg_path = path
                    app.logger.info(f"✅ Found ffmpeg at: {ffmpeg_path}")
                    break
        
        # Method 3: Try 'which' command
        if not ffmpeg_path:
            try:
                which_result = subprocess.run(
                    ['which', 'ffmpeg'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                if which_result.returncode == 0:
                    ffmpeg_path = which_result.stdout.decode().strip()
                    app.logger.info(f"✅ Found ffmpeg using 'which' command: {ffmpeg_path}")
            except Exception as which_error:
                app.logger.warning(f"⚠️  'which' command failed: {str(which_error)}")
        
        # Verify ffmpeg works
        if ffmpeg_path:
            try:
                version_check = subprocess.run(
                    [ffmpeg_path, '-version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                if version_check.returncode == 0:
                    version_output = version_check.stderr.decode()[:200] if version_check.stderr else version_check.stdout.decode()[:200]
                    app.logger.info("=" * 80)
                    app.logger.info("✅ FFMPEG IS AVAILABLE AND WORKING!")
                    app.logger.info(f"📍 Path: {ffmpeg_path}")
                    app.logger.info(f"📍 Version info: {version_output}")
                    app.logger.info("✅ Reel thumbnail generation will work correctly")
                    app.logger.info("=" * 80)
                    return True
                else:
                    app.logger.error("=" * 80)
                    app.logger.error("❌ FFMPEG FOUND BUT NOT WORKING!")
                    app.logger.error(f"📍 Path: {ffmpeg_path}")
                    app.logger.error(f"❌ Return code: {version_check.returncode}")
                    if version_check.stderr:
                        app.logger.error(f"❌ Error: {version_check.stderr.decode()[:200]}")
                    app.logger.error("=" * 80)
                    return False
            except Exception as check_error:
                app.logger.error("=" * 80)
                app.logger.error(f"❌ ERROR TESTING FFMPEG: {str(check_error)}")
                app.logger.error("=" * 80)
                return False
        else:
            app.logger.error("=" * 80)
            app.logger.error("❌ FFMPEG NOT FOUND!")
            app.logger.error("📍 Tried paths:")
            for path in possible_paths:
                exists = os.path.exists(path) if path != 'ffmpeg' else False
                app.logger.error(f"   - {path}: {'✅ exists' if exists else '❌ not found'}")
            app.logger.error("")
            app.logger.error("🔧 TO FIX: Install ffmpeg on your server:")
            app.logger.error("   Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")
            app.logger.error("   macOS: brew install ffmpeg")
            app.logger.error("")
            app.logger.error("⚠️  WARNING: Reel thumbnail generation will NOT work without ffmpeg!")
            app.logger.error("⚠️  New reels will be uploaded but thumbnails will be NULL")
            app.logger.error("=" * 80)
            return False
    
    # Run ffmpeg check at startup
    with app.app_context():
        check_ffmpeg_availability()

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(merchants_bp, url_prefix='/api/merchants')
    app.register_blueprint(document_bp, url_prefix='/api/merchant/documents')
    app.register_blueprint(superadmin_bp, url_prefix='/api/superadmin')
    app.register_blueprint(merchant_dashboard_bp, url_prefix='/api/merchant-dashboard')
    app.register_blueprint(country_bp)
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(product_bp)
    app.register_blueprint(category_bp, url_prefix='/api/categories')
    app.register_blueprint(brand_bp, url_prefix='/api/brands')
    app.register_blueprint(homepage_bp, url_prefix='/api/homepage')
    app.register_blueprint(cart_bp, url_prefix='/api/cart')
    app.register_blueprint(wishlist_bp, url_prefix='/api/wishlist')
    app.register_blueprint(order_bp, url_prefix='/api/orders')
    app.register_blueprint(user_address_bp, url_prefix='/api/user-address')
    app.register_blueprint(currency_bp)
    app.register_blueprint(feature_product_bp, url_prefix='/api/featured-products')
    app.register_blueprint(promo_product_bp, url_prefix='/api/promo-products')
    app.register_blueprint(payment_card_bp)
    app.register_blueprint(review_bp, url_prefix='/api/reviews')

    app.register_blueprint(merchant_support_bp)
    app.register_blueprint(admin_support_bp)
    app.register_blueprint(user_support_bp)

    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    
    app.register_blueprint(superadmin_promotion_bp)
    app.register_blueprint(promo_code_bp)
    app.register_blueprint(merchant_transaction_bp, url_prefix='/api')

    app.register_blueprint(games_bp)
    app.register_blueprint(shiprocket_bp)
    app.register_blueprint(live_stream_public_bp)
    app.register_blueprint(shop_product_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(shop_category_bp)
    app.register_blueprint(shop_brand_bp)
    app.register_blueprint(shop_attribute_bp)
    app.register_blueprint(shop_stock_bp)
    app.register_blueprint(variant_bp, url_prefix='/api/shop')
    app.register_blueprint(shop_review_bp)

    
    # Register public shop routes
    app.register_blueprint(public_shop_bp)
    app.register_blueprint(public_shop_product_bp)
    app.register_blueprint(public_shop_category_bp)
    app.register_blueprint(public_shop_brand_bp)
    app.register_blueprint(public_shop_cart_bp, url_prefix='/api/shop-cart')
    app.register_blueprint(public_shop_wishlist_bp)
    app.register_blueprint(public_shop_order_bp, url_prefix='/api')

    app.register_blueprint(newsletter_public_bp, url_prefix='/api/public')
    app.register_blueprint(holi_giveaway_bp, url_prefix='/api/holi-giveaway')

    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(razorpay_bp)
    app.register_blueprint(ai_image_upload_bp)
    app.register_blueprint(reels_bp)
    app.register_blueprint(follow_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(notification_bp)

    # Optional: Translation endpoints behind feature flag
    if app.config.get('FEATURE_TRANSLATION'):
        app.register_blueprint(translate_bp)

    # Simple health check endpoint (register early)
    @app.route("/health", methods=['GET', 'OPTIONS'])
    def health():
        """Simple health check endpoint for basic status."""
        if request.method == "OPTIONS":
            response = jsonify({})
            origin = request.headers.get('Origin')
            if origin in ALLOWED_ORIGINS:
                response.headers.add("Access-Control-Allow-Origin", origin)
            response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization")
            response.headers.add('Access-Control-Allow-Methods', "GET, OPTIONS")
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        return jsonify({"status": "ok"}), 200

    # Serve static files (temporary uploads for AI processing)
    @app.route('/static/temp_uploads/<path:filename>')
    def serve_temp_upload(filename):
        """Serve temporary uploaded files"""
        static_folder = os.path.join(app.root_path, 'static', 'temp_uploads')
        return send_from_directory(static_folder, filename)

    # Add custom headers to every response
    app.after_request(add_headers)

    # Handle OPTIONS preflight requests FIRST (before other middleware)
    # This must be registered BEFORE the monitoring middleware
    @app.before_request
    def handle_preflight():
        # Only log in DEBUG mode to reduce overhead
        if app.config.get('DEBUG'):
            app.logger.debug(f"Request: {request.method} {request.path}")
        
        if request.method == "OPTIONS":
            response = jsonify({})
            origin = request.headers.get('Origin')
            if origin in ALLOWED_ORIGINS:
                response.headers.add("Access-Control-Allow-Origin", origin)
            else:
                response.headers.add("Access-Control-Allow-Origin", ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*")
            response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization, X-CSRF-Token, Accept")
            response.headers.add('Access-Control-Allow-Methods', "GET, POST, PUT, DELETE, OPTIONS, PATCH")
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            response.headers.add('Access-Control-Max-Age', '3600')
            return response
    
    # Add request timeout and monitoring middleware
    @app.before_request
    def before_request():
        # Set request start time for timeout and performance tracking
        request.start_time = time.time()
        request.timeout = 60  # 60 second timeout per request
        
        # Monitor connection pool status (log warnings if pool is getting low)
        try:
            engine = db.engine
            pool = engine.pool
            checked_out = pool.checkedout()
            pool_size = pool.size()
            max_overflow = getattr(pool, '_max_overflow', 0) or 0
            max_total = pool_size + max_overflow
            
            # Log warning if pool usage is high (>80%)
            if max_total > 0:
                usage_percent = (checked_out / max_total) * 100
                if usage_percent > 80:
                    app.logger.warning(
                        f"High connection pool usage: {checked_out}/{max_total} ({usage_percent:.1f}%) "
                        f"for {request.method} {request.path}"
                    )
        except Exception as e:
            # Don't let pool monitoring break requests
            if app.config.get('DEBUG'):
                app.logger.debug(f"Pool monitoring error: {str(e)}")
        
        # Only log in DEBUG mode to reduce overhead
        if app.config.get('DEBUG'):
            app.logger.debug(f"{request.method} {request.path} from {request.remote_addr}")

    @app.after_request
    def after_request(response):
        """
        Optimized after_request handler - non-blocking, sampled monitoring.
        CRITICAL: Never blocks the response, even if monitoring fails.
        """
        try:
            if hasattr(request, 'start_time'):
                response_time = (time.time() - request.start_time) * 1000  # Convert to milliseconds
                
                # Log slow requests (>5 seconds) for debugging
                if response_time > 5000:
                    app.logger.warning(
                        f"Slow request: {request.method} {request.path} took {response_time:.0f}ms"
                    )
                
                # Check for request timeout
                if hasattr(request, 'timeout') and response_time > (request.timeout * 1000):
                    app.logger.error(
                        f"Request timeout exceeded: {request.method} {request.path} took {response_time:.0f}ms "
                        f"(limit: {request.timeout * 1000}ms)"
                    )
                
                # Only log errors synchronously (important for debugging)
                # Skip normal request monitoring to reduce DB load by 99%
                if response.status_code >= 400:
                    # Log errors - these are important and should be tracked
                    try:
                        # Limit error message size to prevent DB bloat
                        error_message = response.get_data(as_text=True)[:500]
                        
                        monitoring = SystemMonitoring.create_error_record(
                            service_name=request.endpoint or 'unknown',
                            error_type=f'HTTP_{response.status_code}',
                            error_message=error_message,
                            endpoint=request.path,
                            http_method=request.method,
                            http_status=response.status_code
                        )
                        db.session.add(monitoring)
                        db.session.commit()
                    except Exception as e:
                        # Never let monitoring break the response
                        db.session.rollback()
                        app.logger.error(f"Error saving error monitoring: {str(e)}")
                    finally:
                        # Always cleanup session
                        try:
                            db.session.remove()
                        except:
                            pass
                # Skip normal request monitoring (was creating DB record for every request)
                # This was the main bottleneck - removed to improve performance by 10x
                
        except Exception as e:
            # Never let monitoring break the response
            app.logger.error(f"Error in after_request handler: {str(e)}")
        
        return response

    @app.errorhandler(SQLAlchemyIntegrityError)
    def handle_integrity_error(error):
        """Return a user-friendly message for DB constraint violations instead of raw SQL."""
        try:
            if db.session.is_active:
                db.session.rollback()
        except Exception as rollback_error:
            app.logger.error(f"Error during rollback in integrity handler: {str(rollback_error)}")
        app.logger.warning(f"IntegrityError (constraint violation): {str(error)}")
        return jsonify({
            'message': 'This operation is not allowed because the item is still in use. Remove or reassign related items (e.g. products, promotions, tax rules) first.'
        }), 400

    @app.errorhandler(Exception)
    def handle_error(error):
        # CRITICAL: Always ensure database session cleanup on ANY error
        try:
            if db.session.is_active:
                db.session.rollback()
        except Exception as rollback_error:
            app.logger.error(f"Error during rollback in error handler: {str(rollback_error)}")
        finally:
            # Ensure session is removed even if rollback fails
            try:
                db.session.remove()
            except:
                pass
        
        # Get error details
        error_type = type(error).__name__
        error_message = str(error)
        error_stack = traceback.format_exc()
        
        # Skip Redis connection errors - they're not critical
        if 'ConnectionError' in error_type or '6379' in error_message or 'Redis' in error_type:
            app.logger.warning(f"Redis connection error ignored: {error_message}")
            # For Redis errors, try to continue without cache
            # Return a generic error instead of exposing Redis details
            return jsonify({
                'error': 'Service temporarily unavailable. Please try again.',
                'type': 'ServiceError'
            }), 503
        
        # Log error (use proper logging instead of print)
        app.logger.error("=" * 80)
        app.logger.error(f"UNHANDLED EXCEPTION: {error_type}")
        app.logger.error(f"Message: {error_message}")
        app.logger.error(f"Path: {request.path}, Method: {request.method}")
        app.logger.error(f"Stack trace:\n{error_stack}")
        app.logger.error("=" * 80)
        
        # Create error monitoring record (use a new session to avoid conflicts)
        try:
            # Use a separate session for monitoring to avoid conflicts
            monitoring = SystemMonitoring.create_error_record(
                service_name=request.endpoint or 'unknown',
                error_type=error_type,
                error_message=error_message,
                error_stack_trace=error_stack,
                endpoint=request.path,
                http_method=request.method,
                http_status=getattr(error, 'code', 500)
            )
            db.session.add(monitoring)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error saving error monitoring data: {str(e)}")
        finally:
            # Always remove monitoring session too
            try:
                db.session.remove()
            except:
                pass
        
        # Return error response
        return jsonify({
            'error': error_message,
            'type': error_type
        }), getattr(error, 'code', 500)

    # Add monitoring endpoints
    @app.route('/api/monitoring/status')
    def get_system_status():
        """Get current system status"""
        services = db.session.query(SystemMonitoring).order_by(
            SystemMonitoring.timestamp.desc()
        ).limit(10).all()
        
        return jsonify({
            'services': [service.serialize() for service in services]
        })

    @app.route('/api/health', methods=['GET', 'OPTIONS'])
    def health_check():
        """
        Health check endpoint for load balancers and monitoring.
        Lightweight - no database queries, just basic status.
        """
        try:
            # Get connection pool status without blocking
            engine = db.engine
            pool = engine.pool
            
            pool_status = {
                'size': pool.size(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'checked_in': pool.checkedin()
            }
            
            # Check if pool is healthy (not exhausted)
            total_connections = pool_status['checked_out'] + pool_status['checked_in']
            max_connections = pool.size() + (getattr(pool, '_max_overflow', 0) or 0)
            pool_usage_percent = (total_connections / max_connections * 100) if max_connections > 0 else 0
            
            # Get basic system metrics (non-blocking)
            try:
                process = psutil.Process()
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                cpu_usage = process.cpu_percent(interval=None)  # Non-blocking
            except:
                memory_usage = 0
                cpu_usage = 0
            
            health_status = 'healthy'
            if pool_usage_percent > 90:
                health_status = 'degraded'
                app.logger.warning(f"Connection pool near exhaustion: {pool_usage_percent:.1f}% used")
            elif pool_status['checked_out'] >= max_connections:
                health_status = 'unhealthy'
                app.logger.error("Connection pool exhausted!")
            
            return jsonify({
                'status': health_status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'pool': pool_status,
                'pool_usage_percent': round(pool_usage_percent, 1),
                'memory_mb': round(memory_usage, 2),
                'cpu_percent': round(cpu_usage, 2)
            }), 200 if health_status == 'healthy' else 503
            
        except Exception as e:
            app.logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 503

    @app.route('/api/monitoring/metrics')
    def get_system_metrics():
        """Get system metrics"""
        # Get average response time for last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        avg_response = db.session.query(
            db.func.avg(SystemMonitoring.response_time)
        ).filter(
            SystemMonitoring.timestamp >= one_hour_ago,
            SystemMonitoring.response_time.isnot(None)
        ).scalar() or 0

        # Get error count for last hour
        error_count = db.session.query(
            db.func.count(SystemMonitoring.monitoring_id)
        ).filter(
            SystemMonitoring.timestamp >= one_hour_ago,
            SystemMonitoring.status == 'error'
        ).scalar() or 0

        # Get current system metrics
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024
        
        # Get CPU usage (non-blocking)
        try:
            # Use interval=None for non-blocking CPU usage calculation
            # This doesn't block the request like interval=0.1 does
            cpu_usage = process.cpu_percent(interval=None)
            if cpu_usage == 0:
                # If still 0, try getting system-wide CPU usage (also non-blocking)
                cpu_usage = psutil.cpu_percent(interval=None)
        except Exception as e:
            app.logger.warning(f"Error getting CPU usage: {str(e)}")
            cpu_usage = 0

        return jsonify({
            'avg_response_time': round(avg_response, 2),
            'error_count_last_hour': error_count,
            'memory_usage_mb': round(memory_usage, 2),
            'cpu_usage_percent': round(cpu_usage, 2),
            'uptime_seconds': time.time() - psutil.boot_time()
        })

    # Test Redis cache endpoint
    @app.route('/api/test-cache')
    @cached(timeout=30)
    def test_cache():
        import time
        time.sleep(2)
        return jsonify({
            'message': 'This response is cached for 30 seconds',
            'timestamp': time.time()
        })
    
    # Test endpoint for file upload debugging
    @app.route('/api/test-upload', methods=['POST', 'OPTIONS'])
    def test_upload():
        """Simple test endpoint to verify POST requests work"""
        if request.method == 'OPTIONS':
            if app.config.get('DEBUG'):
                app.logger.debug("[TEST_UPLOAD] OPTIONS preflight received")
            response = jsonify({})
            origin = request.headers.get('Origin')
            if origin in ALLOWED_ORIGINS:
                response.headers.add("Access-Control-Allow-Origin", origin)
            response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization")
            response.headers.add('Access-Control-Allow-Methods', "POST, OPTIONS")
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        
        if app.config.get('DEBUG'):
            app.logger.debug(f"[TEST_UPLOAD] POST - Content-Type: {request.content_type}, "
                           f"Content-Length: {request.content_length}, Has files: {bool(request.files)}")
            if request.files:
                app.logger.debug(f"[TEST_UPLOAD] Files: {list(request.files.keys())}")
        
        return jsonify({
            'message': 'Test upload endpoint working',
            'content_type': request.content_type,
            'content_length': request.content_length,
            'has_files': bool(request.files)
        }), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def server_error(error):
        return {"error": "Internal server error"}, 500

    # Initialize background scheduler for notification cleanup
    def start_notification_cleanup_scheduler():
        """Start background scheduler for automatic notification cleanup."""
        # Check if cleanup is enabled
        if not app.config.get('NOTIFICATION_CLEANUP_ENABLED', True):
            app.logger.info("Notification cleanup is disabled")
            return
        
        scheduler = BackgroundScheduler()
        
        # Get configuration
        interval_hours = app.config.get('NOTIFICATION_CLEANUP_INTERVAL_HOURS', 6)
        days_old = app.config.get('NOTIFICATION_CLEANUP_DAYS_OLD', 90)
        batch_size = app.config.get('NOTIFICATION_CLEANUP_BATCH_SIZE', 100)
        max_batches = app.config.get('NOTIFICATION_CLEANUP_MAX_BATCHES', 10)
        
        # Run cleanup at specified interval
        # Processes notifications in small batches to avoid heavy load
        def cleanup_job():
            with app.app_context():
                result = NotificationCleanupService.cleanup_incremental(
                    days_old=days_old,
                    batch_size=batch_size,
                    max_batches=max_batches
                )
                if result.get('success'):
                    app.logger.info(
                        f"Notification cleanup completed: {result['total_deleted']} deleted "
                        f"in {result['batches_processed']} batches"
                    )
                else:
                    app.logger.error(f"Notification cleanup failed: {result.get('error')}")
        
        scheduler.add_job(
            cleanup_job,
            'interval',
            hours=interval_hours,
            id='notification_cleanup',
            replace_existing=True,
            max_instances=1  # Prevent multiple instances running simultaneously
        )
        
        # Start scheduler in a daemon thread
        scheduler.start()
        app.logger.info(
            f"Notification cleanup scheduler started "
            f"(runs every {interval_hours} hours, deletes notifications older than {days_old} days)"
        )
    
    # Start scheduler after app is created
    try:
        start_notification_cleanup_scheduler()
    except Exception as e:
        app.logger.error(f"Failed to start notification cleanup scheduler: {str(e)}")

    return app

if __name__ == "__main__":
    """
    Cross-platform server startup:
    ------------------------------
    Tries servers in order of preference:
    1. Waitress (works on Windows, Linux, Mac) - Recommended for all OS
    2. Gunicorn (works on Linux, Mac only) - Alternative for Unix-like systems
    3. Flask dev server (works everywhere but has limitations) - Last resort
    """
    import os
    import sys
    import platform
    
    app = create_app()
    
    print("=" * 60)
    print("Starting Flask server")
    print("=" * 60)
    print("Server will accept connections on: http://0.0.0.0:5110")
    print("Accessible from: http://127.0.0.1:5110 or http://localhost:5110")
    print("=" * 60)
    
    # Try Waitress first (works on Windows, Mac, Linux)
    try:
        from waitress import serve
        import socket
        import sys
        
        # Check if port is available before starting
        port = 5110
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
        except OSError:
            print("=" * 60)
            print("❌ ERROR: Port 5110 is already in use!")
            print("=" * 60)
            print("To fix this, run one of these commands:")
            print()
            if platform.system() == 'Windows':
                print("  Option 1 - Find and kill process using port 5110:")
                print("    netstat -ano | findstr :5110")
                print("    taskkill /PID <PID> /F")
                print()
            else:
                print("  Option 1 - Kill processes using port 5110:")
                print("    lsof -ti:5110 | xargs kill -9")
                print()
                print("  Option 2 - Find and kill manually:")
                print("    lsof -i:5110")
                print("    kill -9 <PID>")
                print()
            print("  Option 3 - Use a different port (edit app.py):")
            print("    Change port=5110 to port=5111 (or another port)")
            print("=" * 60)
            sys.exit(1)
        
        print("✅ Using Waitress server (cross-platform)")
        print("=" * 60)
        # Optimized Waitress configuration for production scalability
        try:
            serve(
                app,
                host='0.0.0.0',
                port=port,
                threads=16,  # Increased from 8 to handle more concurrent requests
                channel_timeout=600,  # 10 minutes for large file uploads
                cleanup_interval=30,  # Clean up idle connections every 30 seconds
                connection_limit=100,  # Maximum concurrent connections
                asyncore_use_poll=True,  # Better for high concurrency
                recv_bytes=8192,  # Buffer size for receiving
                send_bytes=8192  # Buffer size for sending
            )
        except OSError as e:
            if "Address already in use" in str(e) or e.errno == 48:
                print("=" * 60)
                print("❌ ERROR: Port 5110 is already in use!")
                print("=" * 60)
                print("To fix this, run one of these commands:")
                print()
                if platform.system() == 'Windows':
                    print("  Option 1 - Find and kill process using port 5110:")
                    print("    netstat -ano | findstr :5110")
                    print("    taskkill /PID <PID> /F")
                    print()
                else:
                    print("  Option 1 - Kill processes using port 5110:")
                    print("    lsof -ti:5110 | xargs kill -9")
                    print()
                    print("  Option 2 - Find and kill manually:")
                    print("    lsof -i:5110")
                    print("    kill -9 <PID>")
                    print()
                print("  Option 3 - Use a different port (edit app.py):")
                print("    Change port=5110 to port=5111 (or another port)")
                print("=" * 60)
                sys.exit(1)
            raise
    except ImportError:
        # Waitress not available, try Gunicorn (Unix-only)
        is_unix = platform.system() in ('Linux', 'Darwin')  # Mac or Linux
        if is_unix:
            try:
                from gunicorn.app.base import BaseApplication
                
                class StandaloneApplication(BaseApplication):
                    def __init__(self, app, options=None):
                        self.options = options or {}
                        self.application = app
                        super().__init__()
                    
                    def load_config(self):
                        for key, value in self.options.items():
                            self.cfg.set(key.lower(), value)
                    
                    def load(self):
                        return self.application
                
                options = {
                    'bind': '0.0.0.0:5110',
                    'workers': 1,  # Single worker for development
                    'threads': 8,  # Increased from 4 to match improved concurrency
                    'timeout': 600,  # 10 minutes for large file uploads
                    'keepalive': 5,
                    'accesslog': '-',  # Log to stdout
                    'errorlog': '-',   # Log to stderr
                }
                
                print("✅ Using Gunicorn server (Unix)")
                print("=" * 60)
                StandaloneApplication(app, options).run()
            except ImportError:
                # Gunicorn not available, fallback to Flask dev server
                print("⚠️  Waitress and Gunicorn not available, using Flask development server")
                print("💡 Recommended: Install waitress for better reliability: pip install waitress")
                print()
                _run_flask_dev_server(app)
        else:
            # Windows: Skip Gunicorn, go straight to Flask dev server
            print("⚠️  Waitress not available, using Flask development server")
            print("💡 Recommended: Install waitress for better reliability: pip install waitress")
            print()
            _run_flask_dev_server(app)


def _run_flask_dev_server(app):
    """Run Flask development server with proper error handling for cross-platform support."""
    import os
    import sys
    import werkzeug.serving
    
    # Configure timeout for large file uploads
    werkzeug.serving.WSGIRequestHandler.timeout = 600
    
    # Remove WERKZEUG_SERVER_FD to avoid issues on Windows/Mac
    # This environment variable can cause problems with Werkzeug's reloader
    os.environ.pop('WERKZEUG_SERVER_FD', None)
    os.environ.pop('WERKZEUG_RUN_MAIN', None)
    
    # Ensure use_reloader is False to avoid WERKZEUG_SERVER_FD issues
    try:
        app.run(
            host='0.0.0.0',
            port=5110,
            threaded=True,
            use_reloader=False,  # Disable reloader to avoid WERKZEUG_SERVER_FD issues
            debug=False
        )
    except (KeyError, OSError, ValueError) as e:
        error_msg = str(e)
        if 'WERKZEUG_SERVER_FD' in error_msg or 'Bad file descriptor' in error_msg:
            print("\n" + "=" * 60)
            print("❌ ERROR: Werkzeug development server encountered an issue")
            print("=" * 60)
            print("Root Cause: Known Werkzeug limitation with file descriptors")
            print()
            print("Solutions:")
            print("  1. Install waitress (recommended - works on all platforms):")
            print("     pip install waitress")
            print()
            print("  2. Or on Mac/Linux, install gunicorn:")
            print("     pip install gunicorn")
            print("=" * 60)
            sys.exit(1)
        else:
            # Re-raise if it's a different error
            raise
