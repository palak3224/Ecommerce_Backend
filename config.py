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

    # Redis Cache - DISABLED by default to avoid connection errors
    # Set CACHE_TYPE='redis' and REDIS_URL in environment if you want to use Redis
    CACHE_TYPE = 'null'  # Always use null cache - no Redis connection attempts
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    # Don't set REDIS_URL or CACHE_REDIS_URL - this prevents Flask-Caching from trying to connect

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'svg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx']

    MAIL_SERVER = 'smtp.gmail.com'  # Replace with your SMTP server
    MAIL_PORT = 587  # Common ports: 587 (TLS), 465 (SSL)
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = (os.getenv('MAIL_SENDER_NAME', 'AOIN'), os.getenv('MAIL_USERNAME'))

    FRONTEND_URL = 'https://aoinstore.com'  # No trailing slash to prevent double slashes in URLs

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
    
    # Notification Cleanup Configuration
    NOTIFICATION_CLEANUP_ENABLED = os.getenv('NOTIFICATION_CLEANUP_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    NOTIFICATION_CLEANUP_DAYS_OLD = int(os.getenv('NOTIFICATION_CLEANUP_DAYS_OLD', '90'))
    NOTIFICATION_CLEANUP_INTERVAL_HOURS = int(os.getenv('NOTIFICATION_CLEANUP_INTERVAL_HOURS', '6'))
    NOTIFICATION_CLEANUP_BATCH_SIZE = int(os.getenv('NOTIFICATION_CLEANUP_BATCH_SIZE', '100'))
    NOTIFICATION_CLEANUP_MAX_BATCHES = int(os.getenv('NOTIFICATION_CLEANUP_MAX_BATCHES', '10'))

class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True

class ProductionConfig(Config):
    """Configuration for production environment."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI')
    DEBUG = False

# Environment mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Return the configuration class based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'default')
    return config.get(env, config['default'])
