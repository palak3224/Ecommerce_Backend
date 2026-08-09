import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration shared across environments."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_not_for_production')
    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', 'mysql+pymysql://root:nihalsql@localhost:3306/ecommerce_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Database connection pool configuration optimized for production scalability
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 15,  # Increased base pool size for better concurrency
        'max_overflow': 25,  # More overflow capacity (total: 40 connections max)
        'pool_recycle': 1800,  # Recycle connections after 30 minutes (more aggressive to prevent stale connections)
        'pool_pre_ping': True,  # Verify connections before using them (prevents stale connections)
        'pool_timeout': 20,  # Reduced timeout to fail faster if pool is exhausted
        'connect_args': {
            'connect_timeout': 10,  # MySQL connection timeout (seconds)
            'read_timeout': 30,  # Read timeout (seconds)
            'write_timeout': 30,  # Write timeout (seconds)
        },
        'echo': False  # Don't log all SQL queries (set to True for debugging)
    }

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt_dev_key_not_for_production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)  # Increased from 1 hour to 7 days to reduce token expiration issues during API testing
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'

    # Redis / Flask-Caching — see docs/backend_cache_redis.md for full picture.
    # Flask-Caching: null backend by default (create_app also forces null + strips REDIS URLs).
    # Direct Redis via common.cache.get_redis_client still exists for some features.
    CACHE_TYPE = 'null'  # null = Flask-Caching does not use Redis for @cache in normal boot
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'svg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx']

    # Reels View Tracking
    MAX_RECENT_REEL_VIEWS = int(os.getenv('MAX_RECENT_REEL_VIEWS', '50'))  # Keep 50 most recent views per user

    MAIL_SERVER = 'smtp.gmail.com'  # Replace with your SMTP server
    MAIL_PORT = 587  # Common ports: 587 (TLS), 465 (SSL)
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = (os.getenv('MAIL_SENDER_NAME', 'AOIN'), os.getenv('MAIL_USERNAME'))

    FRONTEND_URL = 'https://aoinstore.com'  # No trailing slash to prevent double slashes in URLs
    # Base URL for AOIN product page links (used when generating product_url for AOIN reels)
    PRODUCT_PAGE_BASE_URL = os.getenv('PRODUCT_PAGE_BASE_URL', os.getenv('FRONTEND_URL', 'https://aoinstore.com')).rstrip('/')

    # Currency. INR is the base/book currency: merchant prices, GST slabs, platform-fee
    # tiers and merchant settlement are all denominated in it.
    DEFAULT_CURRENCY = os.getenv('DEFAULT_CURRENCY', 'INR')
    HOME_COUNTRY_CODE = os.getenv('HOME_COUNTRY_CODE', 'IN')
    # Gates charging in any currency other than DEFAULT_CURRENCY. Keep false until the
    # currency layer ships AND Razorpay international is activated.
    FEATURE_MULTI_CURRENCY = os.getenv('FEATURE_MULTI_CURRENCY', 'false').lower() in ('1', 'true', 'yes')

    EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY', 'f60545f362ec1fdd1e5e7338')
    CARD_ENCRYPTION_KEY = os.getenv('CARD_ENCRYPTION_KEY')
    
    # ShipRocket Configuration
    SHIPROCKET_EMAIL = os.getenv('SHIPROCKET_EMAIL')
    SHIPROCKET_PASSWORD = os.getenv('SHIPROCKET_PASSWORD')
    SHIPROCKET_BASE_URL = 'https://apiv2.shiprocket.in/v1/external'

    # AWS / Translate
    AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
    FEATURE_TRANSLATION = os.getenv('FEATURE_TRANSLATION', 'false').lower() in ('1', 'true', 'yes')
    
    # Video Storage Provider
    VIDEO_STORAGE_PROVIDER = os.getenv('VIDEO_STORAGE_PROVIDER', 'cloudinary')  # 'cloudinary' or 'aws'
    
    # AWS S3 Configuration (for future use when switching to AWS)
    AWS_S3_VIDEO_BUCKET = os.getenv('AWS_S3_VIDEO_BUCKET')
    AWS_CLOUDFRONT_URL = os.getenv('AWS_CLOUDFRONT_URL')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    # Razorpay Configuration
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_1DP5mmOlF5G5ag')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'your_secret_key')
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    DEV_OTP_BYPASS = os.getenv('DEV_OTP_BYPASS', 'false').lower() == 'true'

    # App Store / Apple review helper:
    # If enabled, specific "test phone numbers" (last 10 digits match 5-5 pattern like 1111122222)
    # will NOT send SMS via Twilio and will accept a fixed OTP code (default 123456).
    APPLE_REVIEW_OTP_BYPASS = os.getenv('APPLE_REVIEW_OTP_BYPASS', 'false').lower() in ('1', 'true', 'yes')
    APPLE_REVIEW_OTP_CODE = os.getenv('APPLE_REVIEW_OTP_CODE', '123456')

    # Email OTP verification (app-based onboarding) — lifetime of the 6-digit code in minutes.
    USER_EMAIL_OTP_EXPIRY_MIN = int(os.getenv('USER_EMAIL_OTP_EXPIRY_MIN', '10'))
    MERCHANT_EMAIL_OTP_EXPIRY_MIN = int(os.getenv('MERCHANT_EMAIL_OTP_EXPIRY_MIN', '10'))

    # Notification Cleanup Configuration
    NOTIFICATION_CLEANUP_ENABLED = os.getenv('NOTIFICATION_CLEANUP_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    NOTIFICATION_CLEANUP_DAYS_OLD = int(os.getenv('NOTIFICATION_CLEANUP_DAYS_OLD', '90'))
    NOTIFICATION_CLEANUP_INTERVAL_HOURS = int(os.getenv('NOTIFICATION_CLEANUP_INTERVAL_HOURS', '6'))
    NOTIFICATION_CLEANUP_BATCH_SIZE = int(os.getenv('NOTIFICATION_CLEANUP_BATCH_SIZE', '100'))
    NOTIFICATION_CLEANUP_MAX_BATCHES = int(os.getenv('NOTIFICATION_CLEANUP_MAX_BATCHES', '10'))

    # Merchant account deletion (App Store / privacy): grace period then soft close
    ACCOUNT_DELETION_GRACE_HOURS = int(os.getenv('ACCOUNT_DELETION_GRACE_HOURS', '24'))
    MERCHANT_ACCOUNT_DELETION_JOB_ENABLED = os.getenv(
        'MERCHANT_ACCOUNT_DELETION_JOB_ENABLED', 'true'
    ).lower() in ('1', 'true', 'yes')
    MERCHANT_ACCOUNT_DELETION_JOB_INTERVAL_MINUTES = int(
        os.getenv('MERCHANT_ACCOUNT_DELETION_JOB_INTERVAL_MINUTES', '10')
    )

    # User (buyer) account deletion: grace period then soft close
    USER_ACCOUNT_DELETION_JOB_ENABLED = os.getenv(
        'USER_ACCOUNT_DELETION_JOB_ENABLED', 'true'
    ).lower() in ('1', 'true', 'yes')
    USER_ACCOUNT_DELETION_JOB_INTERVAL_MINUTES = int(
        os.getenv('USER_ACCOUNT_DELETION_JOB_INTERVAL_MINUTES', '10')
    )

    # Merchant intro video.
    # Moderation is off by default, matching how reels ship today. Turning it on
    # routes new/replaced uploads to 'pending' so they stay hidden from shoppers
    # until a superadmin approves them — no migration needed to switch.
    MERCHANT_INTRO_VIDEO_MODERATION_ENABLED = os.getenv(
        'MERCHANT_INTRO_VIDEO_MODERATION_ENABLED', 'false'
    ).lower() in ('1', 'true', 'yes')
    # Purge soft-deleted intro videos (rows + S3 objects) after the retention window.
    INTRO_VIDEO_PURGE_ENABLED = os.getenv(
        'INTRO_VIDEO_PURGE_ENABLED', 'true'
    ).lower() in ('1', 'true', 'yes')
    INTRO_VIDEO_PURGE_RETENTION_DAYS = int(
        os.getenv('INTRO_VIDEO_PURGE_RETENTION_DAYS', '30')
    )
    INTRO_VIDEO_PURGE_INTERVAL_HOURS = int(
        os.getenv('INTRO_VIDEO_PURGE_INTERVAL_HOURS', '24')
    )

class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True

class ProductionConfig(Config):
    """Configuration for production environment."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI')
    DEBUG = False


class TestingConfig(Config):
    """Configuration for automated tests (no real DB or background jobs)."""
    TESTING = True
    DEBUG = False
    SECRET_KEY = 'test-secret-key-not-for-production'
    JWT_SECRET_KEY = 'test-jwt-secret-not-for-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    NOTIFICATION_CLEANUP_ENABLED = False
    MERCHANT_ACCOUNT_DELETION_JOB_ENABLED = False
    USER_ACCOUNT_DELETION_JOB_ENABLED = False
    INTRO_VIDEO_PURGE_ENABLED = False
    FEATURE_TRANSLATION = False
    FEATURE_MULTI_CURRENCY = False
    CACHE_TYPE = 'null'


# Environment mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Return the configuration class based on config_name or FLASK_ENV."""
    env = config_name if config_name is not None else os.getenv('FLASK_ENV', 'default')
    return config.get(env, config['default'])
