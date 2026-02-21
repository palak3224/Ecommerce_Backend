"""
Database initialization script.
Run this script to create the database and tables.
Usage: python init_db.py
"""

import os
import mysql.connector
from dotenv import load_dotenv
from flask import current_app
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
    db_uri = os.getenv('DATABASE_URI') or (current_app.config.get('SQLALCHEMY_DATABASE_URI') if current_app else None)
    if not db_uri:
        print("Error: DATABASE_URI is not set. Add it to your .env or set the environment variable.")
        raise ValueError("DATABASE_URI is not set")
    # Database name may include query string (e.g. railway?charset=utf8)
    db_name = db_uri.split('/')[-1].split('?')[0]

    # Extract credentials and host from URI (format: scheme://user:password@host:port/dbname)
    auth_part = db_uri.split('@')[0].split('://')[1]
    user, password = auth_part.split(':', 1)  # password may contain ':'
    host_port = db_uri.split('@')[1].split('/')[0]
    if ':' in host_port:
        host, port_str = host_port.rsplit(':', 1)
        port = int(port_str)
    else:
        host = host_port
        port = 3306

    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
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
                # Check current enum values first
                result = conn.execute(text("""
                    SELECT DISTINCT auth_provider 
                    FROM users 
                    WHERE auth_provider IS NOT NULL
                """))
                current_values = [row[0] for row in result]
                
                # Only proceed if there are uppercase values
                has_uppercase = any(val and val.isupper() for val in current_values)
                
                if has_uppercase:
                    print("Found uppercase enum values, converting to lowercase...")
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
                else:
                    print("✓ auth_provider enum already correct (no changes needed)")
        except Exception as e:
            # If the column doesn't exist or is already correct, that's okay
            if "doesn't exist" in str(e) or "Duplicate column" in str(e) or "Unknown column" in str(e):
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
        'newsletter_subscriptions', 'holi_giveaway_registrations', 'merchant_transactions',
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

def migrate_business_phone_column_size():
    """Increase business_phone column size from 20 to 30 characters."""
    print("\nMigrating business_phone column size:")
    print("------------------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'merchant_profiles' in inspector.get_table_names():
        existing_columns = {col['name']: col for col in inspector.get_columns('merchant_profiles')}
        
        if 'business_phone' in existing_columns:
            current_column = existing_columns['business_phone']
            current_type = str(current_column.get('type', ''))
            
            # Check if it's still VARCHAR(20) or smaller
            if 'varchar(20)' in current_type.lower() or 'varchar(19)' in current_type.lower():
                print("Increasing business_phone column size from 20 to 30 characters...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text("""
                            ALTER TABLE merchant_profiles 
                            MODIFY COLUMN business_phone VARCHAR(30) NOT NULL
                        """))
                        conn.commit()
                    print("✓ business_phone column size increased successfully")
                except Exception as e:
                    print(f"✗ Failed to increase business_phone column size: {str(e)}")
            else:
                print(f"✓ business_phone column already has correct size ({current_type})")
        else:
            print("✗ business_phone column does not exist")
    else:
        print("✗ merchant_profiles table does not exist")

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

def migrate_phone_verification_user_id_nullable():
    """Make user_id nullable in phone_verifications table for phone sign-up flow."""
    print("\nMigrating phone_verifications user_id column:")
    print("--------------------------------------------")
    
    inspector = db.inspect(db.engine)
    
    if 'phone_verifications' in inspector.get_table_names():
        existing_columns = {col['name']: col for col in inspector.get_columns('phone_verifications')}
        
        if 'user_id' in existing_columns:
            current_column = existing_columns['user_id']
            is_nullable = current_column.get('nullable', True)
            
            if not is_nullable:
                print("Making user_id column nullable in phone_verifications table...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text("""
                            ALTER TABLE phone_verifications 
                            MODIFY COLUMN user_id INT NULL
                        """))
                        conn.commit()
                    print("✓ user_id column is now nullable")
                except Exception as e:
                    print(f"✗ Failed to make user_id nullable: {str(e)}")
            else:
                print("✓ user_id column is already nullable")
        else:
            print("✗ user_id column does not exist in phone_verifications table")
    else:
        print("✗ phone_verifications table does not exist")

def migrate_all_missing_columns():
    """
    Comprehensive migration function that adds all missing columns from models to database.
    This function is safe to run multiple times - it checks for existing columns before adding.
    Preserves all existing data.
    
    FUTURE-PROOF: Automatically handles new columns added to any model.
    """
    print("\n" + "=" * 70)
    print("COMPREHENSIVE COLUMN MIGRATION")
    print("=" * 70)
    print("\nThis will add any missing columns from model definitions to the database.")
    print("All existing data will be preserved.\n")
    
    from sqlalchemy import inspect, MetaData, Table, text
    
    inspector = db.inspect(db.engine)
    
    # Track statistics
    stats = {
        'tables_checked': 0,
        'columns_added': 0,
        'indexes_added': 0,
        'errors': [],
        'warnings': []
    }
    
    # Get all registered models
    all_models = []
    for mapper in db.Model.registry.mappers:
        model_class = mapper.class_
        if hasattr(model_class, '__tablename__') and hasattr(model_class, '__table__'):
            all_models.append(model_class)
    
    print(f"Found {len(all_models)} models to check\n")
    
    for model_class in all_models:
        table_name = model_class.__tablename__
        stats['tables_checked'] += 1
        
        # Check if table exists
        if table_name not in inspector.get_table_names():
            print(f"⚠ Table '{table_name}' does not exist - will be created by db.create_all()")
            continue
        
        print(f"\nChecking table: {table_name}")
        print("-" * 50)
        
        # Get existing columns in database
        existing_columns = {col['name']: col for col in inspector.get_columns(table_name)}
        existing_column_names = set(existing_columns.keys())
        
        # Get model columns
        model_columns = {}
        for column in model_class.__table__.columns:
            model_columns[column.name] = column
        
        # Find missing columns
        missing_columns = set(model_columns.keys()) - existing_column_names
        
        if not missing_columns:
            print(f"  ✓ All columns exist")
            continue
        
        print(f"  Found {len(missing_columns)} missing column(s)")
        
        # Add missing columns one by one
        for col_name in sorted(missing_columns):  # Sort for consistent ordering
            column = model_columns[col_name]
            
            try:
                # Build ALTER TABLE statement
                sql_type = _get_sql_type_improved(column)
                nullable = "NULL" if column.nullable else "NOT NULL"
                
                # Handle server_default (database-level defaults)
                default_clause = ""
                if column.server_default is not None:
                    default_clause = _get_server_default_clause(column.server_default)
                elif column.default is not None:
                    # Handle Python-level defaults
                    default_value = _get_default_value_improved(column.default, column.type)
                    if default_value:
                        default_clause = f" DEFAULT {default_value}"
                elif not column.nullable:
                    # For NOT NULL columns without default, set a safe default
                    default_clause = _get_safe_default_for_type_improved(column.type)
                
                # Build ALTER TABLE statement
                alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {sql_type} {nullable}{default_clause}"
                
                print(f"  → Adding column: {col_name} ({sql_type})")
                
                with db.engine.connect() as conn:
                    conn.execute(text(alter_sql))
                    conn.commit()
                
                stats['columns_added'] += 1
                print(f"    ✓ Added successfully")
                
                # Handle indexes (including composite indexes)
                _add_indexes_for_column(table_name, col_name, column, inspector, stats)
                
            except Exception as e:
                error_msg = f"Failed to add column {table_name}.{col_name}: {str(e)}"
                
                # Check if it's a duplicate column error (might have been added concurrently)
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    stats['warnings'].append(f"{table_name}.{col_name} - Column may have been added by another process")
                    print(f"    ℹ Column may have been added by another process")
                else:
                    stats['errors'].append(error_msg)
                    print(f"    ✗ {error_msg}")
                    import traceback
                    print(f"    Error details: {traceback.format_exc()}")
    
    # Summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Tables checked: {stats['tables_checked']}")
    print(f"Columns added: {stats['columns_added']}")
    print(f"Indexes added: {stats['indexes_added']}")
    if stats['warnings']:
        print(f"\nWarnings: {len(stats['warnings'])}")
        for warning in stats['warnings'][:5]:  # Show first 5
            print(f"  - {warning}")
        if len(stats['warnings']) > 5:
            print(f"  ... and {len(stats['warnings']) - 5} more")
    if stats['errors']:
        print(f"\nErrors encountered: {len(stats['errors'])}")
        for error in stats['errors'][:5]:  # Show first 5
            print(f"  - {error}")
        if len(stats['errors']) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")
    else:
        print("\n✓ All migrations completed successfully!")
    print("=" * 70 + "\n")
    
    return len(stats['errors']) == 0


def _get_sql_type_improved(column):
    """Convert SQLAlchemy column type to SQL string - IMPROVED VERSION."""
    from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, Date, Text, Numeric, Enum, JSON, Float, SmallInteger
    from sqlalchemy.dialects.mysql import TINYINT, MEDIUMINT, LONGTEXT
    
    col_type = column.type
    
    # Handle String types
    if isinstance(col_type, String):
        length = col_type.length if col_type.length else 255
        if length > 65535:
            return "LONGTEXT"
        return f"VARCHAR({length})"
    
    # Handle Integer types
    if isinstance(col_type, Integer):
        return "INTEGER"
    if isinstance(col_type, BigInteger):
        return "BIGINT"
    if isinstance(col_type, SmallInteger):
        return "SMALLINT"
    if isinstance(col_type, TINYINT):
        return "TINYINT"
    if isinstance(col_type, MEDIUMINT):
        return "MEDIUMINT"
    
    # Handle Boolean
    if isinstance(col_type, Boolean):
        return "BOOLEAN"
    
    # Handle Float
    if isinstance(col_type, Float):
        precision = getattr(col_type, 'precision', None)
        if precision:
            return f"FLOAT({precision})"
        return "FLOAT"
    
    # Handle DateTime
    if isinstance(col_type, DateTime):
        return "DATETIME"
    
    # Handle Date
    if isinstance(col_type, Date):
        return "DATE"
    
    # Handle Text types
    if isinstance(col_type, Text):
        if isinstance(col_type, LONGTEXT):
            return "LONGTEXT"
        return "TEXT"
    
    # Handle Numeric/Decimal
    if isinstance(col_type, Numeric):
        precision = col_type.precision if col_type.precision else 10
        scale = col_type.scale if col_type.scale else 2
        return f"DECIMAL({precision},{scale})"
    
    # Handle Enum
    if isinstance(col_type, Enum):
        enum_values = _get_enum_values(col_type)
        enum_str = "','".join(str(v) for v in enum_values)
        return f"ENUM('{enum_str}')"
    
    # Handle JSON
    if isinstance(col_type, JSON) or 'JSON' in str(col_type).upper():
        return "JSON"
    
    # Handle custom types (like AuthProviderType)
    if hasattr(col_type, 'impl'):
        # Recursively get type from implementation
        return _get_sql_type_improved(type('DummyColumn', (), {'type': col_type.impl})())
    
    # Fallback: try to infer from string representation
    type_str = str(col_type).upper()
    if 'VARCHAR' in type_str or 'STRING' in type_str:
        return "VARCHAR(255)"
    if 'INT' in type_str:
        return "INTEGER"
    if 'BOOL' in type_str:
        return "BOOLEAN"
    if 'TEXT' in type_str:
        return "TEXT"
    
    # Ultimate fallback
    return "TEXT"


def _get_enum_values(enum_type):
    """Extract enum values from SQLAlchemy Enum type."""
    try:
        if hasattr(enum_type, 'enums'):
            return enum_type.enums
        elif hasattr(enum_type, 'enum_class'):
            return [e.value for e in enum_type.enum_class]
        elif hasattr(enum_type, 'python_type'):
            enum_class = enum_type.python_type
            return [e.value for e in enum_class]
    except:
        pass
    # Fallback
    return ['pending', 'approved', 'rejected']


def _get_server_default_clause(server_default):
    """Extract server default clause from SQLAlchemy server_default."""
    if server_default is None:
        return ""
    
    # Handle SQLAlchemy text() defaults
    if hasattr(server_default, 'arg'):
        arg = server_default.arg
        if isinstance(arg, str):
            # Check if it's a SQL function
            if 'CURRENT_TIMESTAMP' in arg.upper() or 'NOW()' in arg.upper():
                return " DEFAULT CURRENT_TIMESTAMP"
            elif 'FALSE' in arg.upper() or arg.upper() == '0':
                return " DEFAULT 0"
            elif 'TRUE' in arg.upper() or arg.upper() == '1':
                return " DEFAULT 1"
            else:
                # Try to parse as SQL
                return f" DEFAULT {arg}"
        elif callable(arg):
            # For callable server defaults, we can't easily convert
            return ""  # Will rely on application-level default
    
    # Handle string defaults directly
    if isinstance(server_default, str):
        if server_default.upper() in ('CURRENT_TIMESTAMP', 'NOW()'):
            return " DEFAULT CURRENT_TIMESTAMP"
        return f" DEFAULT {server_default}"
    
    return ""


def _get_default_value_improved(default, column_type):
    """Extract default value from column default - IMPROVED VERSION."""
    if default is None:
        return None
    
    # Handle SQLAlchemy default objects
    if hasattr(default, 'arg'):
        arg = default.arg
        
        # Handle callable defaults (functions, lambdas)
        if callable(arg):
            try:
                result = arg()
                return _format_default_value(result, column_type)
            except Exception:
                # Can't evaluate callable - will need application-level handling
                return None
        
        # Handle scalar defaults
        return _format_default_value(arg, column_type)
    
    # Handle direct callable
    if callable(default):
        try:
            result = default()
            return _format_default_value(result, column_type)
        except Exception:
            return None
    
    # Handle direct scalar
    return _format_default_value(default, column_type)


def _format_default_value(value, column_type):
    """Format a default value for SQL."""
    if value is None:
        return None
    
    # Handle numeric types
    if isinstance(value, (int, float)):
        return str(value)
    
    # Handle boolean
    if isinstance(value, bool):
        return "1" if value else "0"
    
    # Handle strings
    if isinstance(value, str):
        # Escape single quotes
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    
    # Handle enum values
    if hasattr(value, 'value'):
        return f"'{value.value}'"
    
    # Handle datetime objects
    if hasattr(value, 'isoformat'):
        return f"'{value.isoformat()}'"
    
    return f"'{str(value)}'"


def _get_safe_default_for_type_improved(column_type):
    """Get a safe default value for NOT NULL columns without explicit defaults - IMPROVED."""
    from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, Date, Text, Numeric, Enum, Float
    
    if isinstance(column_type, (Integer, BigInteger)):
        return " DEFAULT 0"
    elif isinstance(column_type, Boolean):
        return " DEFAULT 0"
    elif isinstance(column_type, String):
        return " DEFAULT ''"
    elif isinstance(column_type, (DateTime, Date)):
        return " DEFAULT CURRENT_TIMESTAMP"
    elif isinstance(column_type, (Numeric, Float)):
        return " DEFAULT 0.00"
    elif isinstance(column_type, Enum):
        try:
            enum_values = _get_enum_values(column_type)
            if enum_values:
                return f" DEFAULT '{enum_values[0]}'"
        except:
            pass
        return " DEFAULT 'pending'"
    
    return ""  # No default - application must handle


def _add_indexes_for_column(table_name, col_name, column, inspector, stats):
    """Add indexes for a column, including composite indexes."""
    try:
        existing_indexes = {idx['name']: idx for idx in inspector.get_indexes(table_name)}
        
        # Handle single-column index
        if column.index and not column.unique:
            index_name = f"ix_{table_name}_{col_name}"
            if index_name not in existing_indexes:
                index_sql = f"CREATE INDEX `{index_name}` ON `{table_name}` (`{col_name}`)"
                with db.engine.connect() as conn:
                    conn.execute(text(index_sql))
                    conn.commit()
                stats['indexes_added'] += 1
                print(f"    ✓ Created index: {index_name}")
        
        # Handle unique index
        if column.unique:
            index_name = f"ix_{table_name}_{col_name}"
            # Check if unique constraint exists
            unique_indexes = [name for name, idx in existing_indexes.items() if idx.get('unique', False)]
            if index_name not in unique_indexes:
                index_sql = f"CREATE UNIQUE INDEX `{index_name}` ON `{table_name}` (`{col_name}`)"
                with db.engine.connect() as conn:
                    conn.execute(text(index_sql))
                    conn.commit()
                stats['indexes_added'] += 1
                print(f"    ✓ Created unique index: {index_name}")
    
    except Exception as idx_error:
        # Index might already exist or have a different name
        if "Duplicate key name" not in str(idx_error) and "already exists" not in str(idx_error).lower():
            print(f"    ⚠ Index creation warning: {str(idx_error)}")

def init_database():
    """Initialize the database with all tables and initial data."""
    app = create_app()
    with app.app_context():
        print("Initializing Database:")
        print("=====================")
        
        # SAFETY CHECK: Warn if running on production (informational only, no input required)
        db_uri = os.getenv('DATABASE_URI', '')
        db_uri_lower = db_uri.lower()
        is_production = any(keyword in db_uri_lower for keyword in ['production', 'prod', 'live', 'main'])
        
        if is_production:
            print("\n" + "=" * 70)
            print("⚠️  WARNING: This appears to be a PRODUCTION database!")
            print("=" * 70)
            print(f"Database URI: {db_uri[:50]}..." if len(db_uri) > 50 else f"Database URI: {db_uri}")
            print("\n⚠️  IMPORTANT REMINDERS:")
            print("   • Ensure you have a database backup")
            print("   • This script is safe - it only adds missing columns/data")
            print("   • It will NOT delete or modify existing data")
            print("   • Running during maintenance window is recommended")
            print("\n✓ Proceeding with migration automatically...")
            print("=" * 70 + "\n")
        else:
            print("\n" + "=" * 70)
            print("ℹ️  REMINDER: Before running on production:")
            print("   1. Take a database backup")
            print("   2. Test on staging first")
            print("   3. Run during maintenance window")
            print("=" * 70 + "\n")
        
        # Create database if it doesn't exist
        create_database()
        
        # Create all tables
        print("\nCreating tables...")
        db.create_all()
        print("✓ All tables created successfully.")
        
        # Verify all tables are created
        verify_all_tables()
        
        # Run comprehensive column migration FIRST (before other specific migrations)
        print("\n" + "=" * 70)
        print("RUNNING COMPREHENSIVE COLUMN MIGRATION")
        print("=" * 70)
        migrate_all_missing_columns()
        
        # Run specific migrations (these handle edge cases for specific columns)
        migrate_profile_img_column()
        migrate_date_of_birth_gender_columns()
        migrate_auth_provider_enum()
        migrate_business_phone_column_size()
        migrate_carousel_orientation()
        migrate_phone_verification_user_id_nullable()
        
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
        print("  3. Run comprehensive column migration (adds missing columns)")
        print("  4. Run specific migrations")
        print("  5. Initialize default data")
        print("  6. Create super admin user (if configured)")
        print("\nNote: This script is safe to run multiple times.")
        print("      It will preserve all existing data.\n")
        print("Starting initialization...\n")
        
        init_database()
        
    except Exception as e:
        print("\n" + "=" * 50)
        print("✗ ERROR: Database initialization failed!")
        print("=" * 50)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
