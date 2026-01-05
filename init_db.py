"""
Database initialization script.
Run this script to create the database and tables.
Usage: python init_db.py
"""

import os
import mysql.connector
from dotenv import load_dotenv
from app import create_app
from common.database import db
from sqlalchemy import text

# Import all models to ensure db.create_all() creates all tables
# This matches what app.py does with "from models import *"
# Importing all models ensures all tables are created by db.create_all()
from models import *  # Import all models from models package
from models.shop import *  # Import all shop models
from models.shop.shop_product_variant import ShopProductVariant, ShopVariantAttributeValue  # Shop variants
from models.visit_tracking import VisitTracking
from models.customer_profile import CustomerProfile
from models.user_address import UserAddress
from models.wishlist_item import WishlistItem
from models.cart import Cart, CartItem
from models.order import Order, OrderItem, OrderStatusHistory
from models.shipment import Shipment, ShipmentItem
from models.support_ticket_model import SupportTicket, SupportTicketMessage
from models.youtube_token import YouTubeToken
from models.tax_rate import TaxRate
from models.carousel import Carousel

# --- Auth models ---
from auth.models.models import (
    User,
    MerchantProfile,
    RefreshToken,
    EmailVerification,
    PhoneVerification,
    UserRole,
    AuthProvider
)
from auth.models.merchant_document import (
    MerchantDocument,
    VerificationStatus,
    DocumentType,
    DocumentStatus
)
from auth.models.country_config import (
    CountryConfig,
    CountryCode
)

# --- Superadmin models ---
from models.category import Category
from models.brand import Brand
from models.brand_request import BrandRequest
from models.attribute import Attribute
from models.attribute_value import AttributeValue
from models.category_attribute import CategoryAttribute
from models.promotion import Promotion
from models.product_promotion import ProductPromotion
from models.tax_category import TaxCategory
from models.homepage import HomepageCategory
from models.subscription import SubscriptionPlan

from models.gst_rule import GSTRule

from models.merchant_transaction import MerchantTransaction

# --- Merchant models ---
from models.product import Product
from models.product_meta import ProductMeta
from models.product_tax import ProductTax
from models.product_shipping import ProductShipping
from models.product_media import ProductMedia
from models.product_stock import ProductStock
from models.review import Review
from models.product_attribute import ProductAttribute
from models.recently_viewed import RecentlyViewed
from models.merchant_dimension_preset import MerchantDimensionPreset

# --- Shop models ---
from models.shop.shop import Shop

# --- Live Streaming models ---
from models.live_stream import LiveStream, LiveStreamComment, LiveStreamViewer, StreamStatus

# --- Payment models ---
from models.payment_card import PaymentCard
from models.enums import CardTypeEnum, CardStatusEnum

# --- Monitoring models ---
from models.system_monitoring import SystemMonitoring

# --- Newsletter models ---
from models.newsletter_subscription import NewsletterSubscription

# Load environment variables
load_dotenv()

def create_database():
    """Create the database if it doesn't exist."""
    db_uri = os.getenv('DATABASE_URI')
    db_name = db_uri.split('/')[-1]

    # Extract credentials and host from URI
    auth_part = db_uri.split('@')[0].split('://')[1]
    user = auth_part.split(':')[0]
    password = auth_part.split(':')[1]
    host = db_uri.split('@')[1].split('/')[0]

    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )

        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' created or already exists.")

        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

def init_country_configs():
    """Initialize country-specific configurations."""
    print("\nInitializing Country Configurations:")
    print("-------------------------------------")
    
    # Initialize India configuration
    print("\nIndia (IN) Configuration:")
    print("-------------------------")
    india_docs = CountryConfig.get_required_documents(CountryCode.INDIA.value)
    print(f"Required Documents: {len(india_docs)} documents configured")
    
    india_validations = CountryConfig.get_field_validations(CountryCode.INDIA.value)
    print(f"Field Validations: {len(india_validations)} validation rules configured")
    
    india_bank_fields = CountryConfig.get_bank_fields(CountryCode.INDIA.value)
    print(f"Bank Fields: {len(india_bank_fields)} bank fields configured")
    
    india_tax_fields = CountryConfig.get_tax_fields(CountryCode.INDIA.value)
    print(f"Tax Fields: {len(india_tax_fields)} tax fields configured")

    # Initialize Global configuration
    print("\nGlobal Configuration:")
    print("---------------------")
    global_docs = CountryConfig.get_required_documents(CountryCode.GLOBAL.value)
    print(f"Required Documents: {len(global_docs)} documents configured")
    
    global_validations = CountryConfig.get_field_validations(CountryCode.GLOBAL.value)
    print(f"Field Validations: {len(global_validations)} validation rules configured")
    
    global_bank_fields = CountryConfig.get_bank_fields(CountryCode.GLOBAL.value)
    print(f"Bank Fields: {len(global_bank_fields)} bank fields configured")
    
    global_tax_fields = CountryConfig.get_tax_fields(CountryCode.GLOBAL.value)
    print(f"Tax Fields: {len(global_tax_fields)} tax fields configured")

    print("\nCountry configurations initialized successfully.")

def init_tax_categories():
    """Initialize standard tax categories."""
    print("\nInitializing Tax Categories:")
    print("----------------------------")
    
    tax_categories = [
        {
            'name': 'Standard Rate',
            'description': 'Standard tax rate applicable to most goods and services',
            'tax_rate': 18.00
        },
        {
            'name': 'Reduced Rate',
            'description': 'Reduced tax rate for specific goods and services',
            'tax_rate': 12.00
        },
        {
            'name': 'Zero Rate',
            'description': 'Zero tax rate for exempted goods and services',
            'tax_rate': 0.00
        }
    ]
    
    for tax_data in tax_categories:
        existing_tax = TaxCategory.query.filter_by(name=tax_data['name']).first()
        if not existing_tax:
            tax_category = TaxCategory(**tax_data)
            db.session.add(tax_category)
            print(f"Created tax category: {tax_data['name']} ({tax_data['tax_rate']}%)")
    
    db.session.commit()
    print("Tax categories initialized successfully.")

def init_brand_categories():
    """Initialize brand-category relationships."""
    print("\nInitializing Brand-Category Relationships:")
    print("----------------------------------------")
    print("Brand-category relationships will be managed manually by users.")
    print("No automatic associations will be made.")
    
    # No automatic associations - brands will be associated with categories
    # through user actions in the application
    db.session.commit()
    print("Brand-category relationships initialized successfully.")

def init_product_stocks():
    """Initialize product stocks for existing products."""
    print("\nInitializing Product Stocks:")
    print("---------------------------")
    
    # Get all products without stock records
    products = Product.query.all()
    
    for product in products:
        existing_stock = ProductStock.query.filter_by(product_id=product.product_id).first()
        if not existing_stock:
            stock = ProductStock(
                product_id=product.product_id,
                stock_qty=0,
                low_stock_threshold=5,  # Default threshold
               
            )
            db.session.add(stock)
            print(f"Created stock record for product: {product.product_name}")
    
    db.session.commit()
    print("Product stocks initialized successfully.")

def init_recently_viewed():
    """Initialize recently viewed table."""
    print("\nInitializing Recently Viewed Table:")
    print("----------------------------------")
    
    # Check if the table exists using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    if 'recently_viewed' not in inspector.get_table_names():
        print("Creating recently_viewed table...")
        RecentlyViewed.__table__.create(db.engine)
        print("Recently viewed table created successfully.")
    else:
        print("Recently viewed table already exists.")

def init_homepage_categories():
    """Initialize homepage categories table."""
    print("\nInitializing Homepage Categories:")
    print("--------------------------------")
    
    # Check if the table exists using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    if 'homepage_categories' not in inspector.get_table_names():
        print("Creating homepage_categories table...")
        HomepageCategory.__table__.create(db.engine)
        print("Homepage categories table created successfully.")
    else:
        print("Homepage categories table already exists.")

def init_subscription_plans():
    """Initialize standard subscription plans."""
    print("\nInitializing Subscription Plans:")
    print("------------------------------")
    
    # Check if can_place_premium column exists, if not add it
    try:
        with db.engine.connect() as conn:
            conn.execute(text("""
                SELECT can_place_premium 
                FROM subscription_plans 
                LIMIT 1
            """))
    except Exception:
        print("Adding can_place_premium column to subscription_plans table...")
        with db.engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE subscription_plans 
                ADD COLUMN can_place_premium BOOLEAN NOT NULL DEFAULT FALSE
            """))
            conn.commit()
    
    subscription_plans = [
        {
            'name': 'Basic',
            'description': 'Basic subscription plan with limited features',
            'featured_limit': 10,
            'promo_limit': 10,
            'duration_days': 30,
            'price': 399,
            'active_flag': True,
            'can_place_premium': False,
            'approval_status': 'approved'
        },
        {
            'name': 'Professional',
            'description': 'Professional subscription plan with advanced features',
            'featured_limit': 50,
            'promo_limit': 50,
            'duration_days': 30,
            'price': 999,
            'active_flag': True,
            'can_place_premium': True,
            'approval_status': 'approved'
        },
        {
            'name': 'Enterprise',
            'description': 'Enterprise subscription plan with unlimited features',
            'featured_limit': 999999,
            'promo_limit': 999999,
            'duration_days': 30,
            'price': 1999,
            'active_flag': True,
            'can_place_premium': True,
            'approval_status': 'approved'
        }
    ]
    
    for plan_data in subscription_plans:
        existing_plan = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
        if not existing_plan:
            subscription_plan = SubscriptionPlan(**plan_data)
            db.session.add(subscription_plan)
            print(f"Created subscription plan: {plan_data['name']} (${plan_data['price']})")
        else:
            # Update existing plan with new values
            for key, value in plan_data.items():
                setattr(existing_plan, key, value)
            print(f"Updated subscription plan: {plan_data['name']} (${plan_data['price']})")
    
    db.session.commit()
    print("Subscription plans initialized successfully.")

def init_payment_cards():
    """Initialize payment cards table and encryption key."""
    print("\nInitializing Payment Cards:")
    print("--------------------------")
    
    # Check if the table exists using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    if 'payment_cards' not in inspector.get_table_names():
        print("Creating payment_cards table...")
        PaymentCard.__table__.create(db.engine)
        print("Payment cards table created successfully.")
    else:
        print("Payment cards table already exists.")
    
    # Check if CARD_ENCRYPTION_KEY exists in app config
    app = create_app()
    with app.app_context():
        if not app.config.get('CARD_ENCRYPTION_KEY'):
            from cryptography.fernet import Fernet
            app.config['CARD_ENCRYPTION_KEY'] = Fernet.generate_key()
            print("Generated new card encryption key.")
        else:
            print("Card encryption key already exists.")

def init_system_monitoring():
    """Initialize system monitoring table."""
    print("\nInitializing System Monitoring:")
    print("-----------------------------")
    
    # Check if the table exists using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    if 'system_monitoring' not in inspector.get_table_names():
        print("Creating system_monitoring table...")
        SystemMonitoring.__table__.create(db.engine)
        print("System monitoring table created successfully.")
    else:
        print("System monitoring table already exists.")
    
    # Create initial system status record
    initial_status = SystemMonitoring.create_service_status(
        service_name='system_init',
        status='up',
        response_time=0.0,
        memory_usage=0.0,
        cpu_usage=0.0
    )
    db.session.add(initial_status)
    db.session.commit()
    print("Initial system status record created.")

def init_live_streaming():
    """Initialize live streaming tables."""
    print("\nInitializing Live Streaming Tables:")
    print("---------------------------------")
    
    # Check if the tables exist using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    tables = ['live_streams', 'live_stream_comments', 'live_stream_viewers']
    
    for table in tables:
        if table not in inspector.get_table_names():
            print(f"Creating {table} table...")
            if table == 'live_streams':
                LiveStream.__table__.create(db.engine)
            elif table == 'live_stream_comments':
                LiveStreamComment.__table__.create(db.engine)
            elif table == 'live_stream_viewers':
                LiveStreamViewer.__table__.create(db.engine)
            print(f"{table} table created successfully.")
        else:
            print(f"{table} table already exists.")
    
    # Add stream_status enum if it doesn't exist
    try:
        with db.engine.connect() as conn:
            conn.execute(text("""
                SELECT stream_status 
                FROM live_streams 
                LIMIT 1
            """))
    except Exception:
        print("Adding stream_status enum to live_streams table...")
        with db.engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE live_streams 
                MODIFY COLUMN status ENUM('scheduled', 'live', 'ended', 'cancelled') 
                NOT NULL DEFAULT 'scheduled'
            """))
            conn.commit()
    
    print("Live streaming tables initialized successfully.")

def init_shops():
    """Initialize default shops."""
    print("\nInitializing Shops:")
    print("------------------")
    
    shops_data = [
        {
            'name': 'shop1',
            'slug': 'shop1',
            'description': 'First shop in the ecommerce platform',
            'logo_url': None,
            'is_active': True
        },
        {
            'name': 'shop2',
            'slug': 'shop2',
            'description': 'Second shop in the ecommerce platform',
            'logo_url': None,
            'is_active': True
        },
        {
            'name': 'shop3',
            'slug': 'shop3',
            'description': 'Third shop in the ecommerce platform',
            'logo_url': None,
            'is_active': True
        },
        {
            'name': 'shop4',
            'slug': 'shop4',
            'description': 'Fourth shop in the ecommerce platform',
            'logo_url': None,
            'is_active': True
        }
    ]
    
    for shop_data in shops_data:
        existing_shop = Shop.query.filter_by(name=shop_data['name']).first()
        if not existing_shop:
            shop = Shop(**shop_data)
            db.session.add(shop)
            print(f"Created shop: {shop_data['name']}")
        else:
            print(f"Shop {shop_data['name']} already exists")
    
    db.session.commit()
    print("Shops initialized successfully.")

def init_reels():
    """Initialize reels tables."""
    print("\nInitializing Reels Tables:")
    print("-------------------------")
    
    # Check if the tables exist using SQLAlchemy inspector
    inspector = db.inspect(db.engine)
    tables = ['reels', 'user_reel_likes', 'user_reel_views', 'user_reel_shares']
    
    for table in tables:
        if table not in inspector.get_table_names():
            print(f"Creating {table} table...")
            if table == 'reels':
                Reel.__table__.create(db.engine)
            elif table == 'user_reel_likes':
                UserReelLike.__table__.create(db.engine)
            elif table == 'user_reel_views':
                UserReelView.__table__.create(db.engine)
            elif table == 'user_reel_shares':
                UserReelShare.__table__.create(db.engine)
            print(f"{table} table created successfully.")
        else:
            print(f"{table} table already exists.")
    
    # Add FULLTEXT index on reels.description if it doesn't exist
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                AND table_name = 'reels'
                AND index_name = 'ft_description'
            """))
            
            index_exists = result.fetchone()[0] > 0
            
            if not index_exists:
                print("Creating FULLTEXT index on reels.description...")
                conn.execute(text("""
                    CREATE FULLTEXT INDEX ft_description ON reels(description)
                """))
                conn.commit()
                print("✓ FULLTEXT index created on reels.description")
            else:
                print("✓ FULLTEXT index already exists on reels.description")
    except Exception as e:
        print(f"⚠ Could not create FULLTEXT index (may already exist): {str(e)}")
    
    print("Reels tables initialized successfully.")

def migrate_profile_img_column():
    """Add profile_img column to users table if it doesn't exist."""
    print("\nMigrating profile_img column:")
    print("----------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'users' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'profile_img' not in existing_columns:
            print("Adding profile_img column to users table...")
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_img VARCHAR(512) NULL"))
                    conn.commit()
                print("✓ profile_img column added successfully")
            except Exception as e:
                print(f"✗ Failed to add profile_img column: {str(e)}")
        else:
            print("✓ profile_img column already exists")
    else:
        print("✗ users table does not exist")

def migrate_date_of_birth_gender_columns():
    """Add date_of_birth and gender columns to users table if they don't exist."""
    print("\nMigrating date_of_birth and gender columns:")
    print("-------------------------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'users' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add date_of_birth column if it doesn't exist
        if 'date_of_birth' not in existing_columns:
            print("Adding date_of_birth column to users table...")
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN date_of_birth DATE NULL"))
                    conn.commit()
                print("✓ date_of_birth column added successfully")
            except Exception as e:
                print(f"✗ Failed to add date_of_birth column: {str(e)}")
        else:
            print("✓ date_of_birth column already exists")
        
        # Add gender column if it doesn't exist
        if 'gender' not in existing_columns:
            print("Adding gender column to users table...")
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN gender VARCHAR(20) NULL"))
                    conn.commit()
                print("✓ gender column added successfully")
            except Exception as e:
                print(f"✗ Failed to add gender column: {str(e)}")
        else:
            print("✓ gender column already exists")
    else:
        print("✗ users table does not exist")

def migrate_auth_provider_enum():
    """Fix auth_provider enum values from uppercase to lowercase."""
    print("\nMigrating auth_provider enum:")
    print("----------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'users' in inspector.get_table_names():
        try:
            with db.engine.connect() as conn:
                # First, update any uppercase values to lowercase
                conn.execute(text("""
                    UPDATE users 
                    SET auth_provider = LOWER(auth_provider)
                    WHERE auth_provider IN ('LOCAL', 'GOOGLE', 'PHONE')
                """))
                
                # Then, modify the column to use lowercase enum values
                conn.execute(text("""
                    ALTER TABLE users 
                    MODIFY COLUMN auth_provider ENUM('local', 'google', 'phone') 
                    NOT NULL DEFAULT 'local'
                """))
                
                conn.commit()
            print("✓ auth_provider enum values fixed successfully")
        except Exception as e:
            # If the column doesn't exist or is already correct, that's okay
            if "doesn't exist" in str(e) or "Duplicate column" in str(e):
                print("✓ auth_provider enum already correct")
            else:
                print(f"⚠ Could not migrate auth_provider enum (may already be correct): {str(e)}")
    else:
        print("⚠ users table does not exist, skipping auth_provider migration")

def verify_all_tables():
    """Verify that all expected tables are created in the database."""
    print("\nVerifying all tables:")
    print("-------------------")
    
    # Expected tables from all models (based on __tablename__)
    expected_tables = {
        # Auth tables
        'users', 'merchant_profiles', 'refresh_tokens', 
        'email_verifications', 'phone_verifications', 'merchant_documents',
        'country_configs',
        
        # Core product tables
        'products', 'categories', 'brands', 'attributes', 'attribute_values',
        'category_attributes', 'product_attributes', 'product_media', 
        'product_stock', 'product_tax', 'product_shipping', 'product_meta',
        'product_promotions', 'product_placements', 'reviews', 'review_images',
        'brand_requests',
        
        # Shop tables
        'shops', 'shop_categories', 'shop_brands', 'shop_attributes', 
        'shop_attribute_values', 'shop_products', 'shop_product_attributes',
        'shop_product_media', 'shop_product_stock', 'shop_product_taxes',
        'shop_product_shipping', 'shop_product_meta', 'shop_product_promotions',
        'shop_product_placements', 'shop_product_variants', 
        'shop_variant_attribute_values', 'shop_gst_rules', 'shop_reviews',
        'shop_review_images', 'shop_wishlist_items',
        
        # Order and cart tables
        'carts', 'cart_items', 'orders', 'order_items', 'order_status_history',
        'shipments', 'shipment_items',
        'shop_carts', 'shop_cart_items', 'shop_orders', 'shop_order_items',
        'shop_order_status_history', 'shop_shipments', 'shop_shipment_items',
        
        # User-related tables
        'customer_profiles', 'user_addresses', 'wishlist_items',
        'visit_tracking', 'user_category_preferences', 'user_merchant_follows',
        
        # Reel tables
        'reels', 'user_reel_likes', 'user_reel_views', 'user_reel_shares',
        
        # Other tables
        'subscription_plans', 'subscription_histories', 'promotions', 'game_plays',
        'payment_cards', 'support_tickets', 'support_ticket_messages',
        'newsletter_subscriptions', 'merchant_transactions',
        'live_streams', 'live_stream_comments', 'live_stream_viewers',
        'homepage_categories', 'recently_viewed', 'carousels',
        'tax_rates', 'tax_categories', 'youtube_tokens', 'system_monitoring'
    }
    
    inspector = db.inspect(db.engine)
    actual_tables = set(inspector.get_table_names())
    
    # Find missing tables
    missing_tables = expected_tables - actual_tables
    
    # Find extra tables (not in expected list - might be system tables)
    extra_tables = actual_tables - expected_tables
    
    if missing_tables:
        print(f"⚠ Missing tables ({len(missing_tables)}):")
        for table in sorted(missing_tables):
            print(f"  - {table}")
    else:
        print(f"✓ All expected tables exist ({len(expected_tables)} tables)")
    
    if extra_tables:
        # Filter out common MySQL system tables
        system_tables = {'alembic_version'}  # Add other system tables if needed
        user_extra_tables = extra_tables - system_tables
        if user_extra_tables:
            print(f"\nℹ Additional tables found ({len(user_extra_tables)}):")
            for table in sorted(user_extra_tables):
                print(f"  - {table}")
    
    print(f"\nTotal tables in database: {len(actual_tables)}")
    print(f"Expected tables: {len(expected_tables)}")
    
    return len(missing_tables) == 0

def migrate_carousel_orientation():
    """Add orientation column to carousels table if it doesn't exist."""
    print("\nMigrating carousel orientation column:")
    print("--------------------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'carousels' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('carousels')]
        
        if 'orientation' not in existing_columns:
            print("Adding orientation column to carousels table...")
            try:
                with db.engine.connect() as conn:
                    # Add column with default value
                    conn.execute(text("ALTER TABLE carousels ADD COLUMN orientation VARCHAR(20) NOT NULL DEFAULT 'horizontal' AFTER type"))
                    # Update existing records
                    conn.execute(text("UPDATE carousels SET orientation = 'horizontal' WHERE orientation IS NULL OR orientation = ''"))
                    conn.commit()
                print("✓ orientation column added successfully")
            except Exception as e:
                print(f"✗ Failed to add orientation column: {str(e)}")
        else:
            print("✓ orientation column already exists")
    else:
        print("✗ carousels table does not exist")

def init_database():
    """Initialize the database with all tables and initial data."""
    app = create_app()
    with app.app_context():
        print("Initializing Database:")
        print("=====================")
        
        # Create database if it doesn't exist
        create_database()
        
        # Create all tables
        print("\nCreating tables...")
        db.create_all()
        print("✓ All tables created successfully.")
        
        # Verify all tables are created
        verify_all_tables()
        
        # Run migrations
        migrate_profile_img_column()
        migrate_date_of_birth_gender_columns()
        migrate_auth_provider_enum()
        migrate_carousel_orientation()
        
        # Initialize data
        init_country_configs()
        init_tax_categories()
        init_brand_categories()
        init_product_stocks()
        init_recently_viewed()
        init_homepage_categories()
        init_subscription_plans()
        init_payment_cards()
        init_system_monitoring()
        init_live_streaming()
        init_shops()  # Add shops initialization
        init_reels()  # Add reels initialization
        
        # Create super admin user if not exists
        admin_email = os.getenv("SUPER_ADMIN_EMAIL")
        admin_first_name = os.getenv("SUPER_ADMIN_FIRST_NAME")
        admin_last_name = os.getenv("SUPER_ADMIN_LAST_NAME")
        admin_password = os.getenv("SUPER_ADMIN_PASSWORD")

        try:
            admin = User.get_by_email(admin_email)
            if not admin:
                admin = User(
                    email=admin_email,
                    first_name=admin_first_name,
                    last_name=admin_last_name,
                    role=UserRole.SUPER_ADMIN,
                    is_email_verified=True
                )
                admin.set_password(admin_password)
                admin.save()
                print("Super admin user created.")
        except Exception as e:
            print(f"⚠ Warning: Could not check/create super admin user: {e}")
            print("   You may need to create the admin user manually or fix enum values in the database.")
        
        print("\n" + "=" * 50)
        print("✓ Database initialization completed successfully!")
        print("=" * 50)
        print("\nYou can now start the application with: python app.py")
        print("Or run the Flask development server with: flask run")


if __name__ == "__main__":
    try:
        print("=" * 50)
        print("DATABASE INITIALIZATION SCRIPT")
        print("=" * 50)
        print("\nThis script will:")
        print("  1. Create the database if it doesn't exist")
        print("  2. Create all tables")
        print("  3. Run migrations")
        print("  4. Initialize default data")
        print("  5. Create super admin user (if configured)")
        print("\nStarting initialization...\n")
        
        init_database()
        
    except Exception as e:
        print("\n" + "=" * 50)
        print("✗ ERROR: Database initialization failed!")
        print("=" * 50)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
