"""
Database Migration Script
Run this script to apply any pending database migrations.
This script is safe to run on existing databases - it checks if migrations are needed.

Usage: python run_migrations.py
"""

import os
from dotenv import load_dotenv
from app import create_app
from common.database import db
from sqlalchemy import text, inspect

# Load environment variables
load_dotenv()

def migrate_date_of_birth_gender_columns():
    """Add date_of_birth and gender columns to users table if they don't exist."""
    print("\nMigrating date_of_birth and gender columns:")
    print("-------------------------------------------")
    
    inspector = inspect(db.engine)
    
    if 'users' not in inspector.get_table_names():
        print("✗ users table does not exist. Please run 'python init_db.py' first.")
        return False
    
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    all_added = True
    
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
            all_added = False
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
            all_added = False
    else:
        print("✓ gender column already exists")
    
    return all_added


def migrate_notification_type_enum():
    """Extend merchant_notifications.notification_type to accept every enum value.

    init_db.py's auto-migration only ever ADDs columns — it never MODIFYs one — so
    adding a member to the Python NotificationType enum leaves the MySQL ENUM
    unchanged and the insert fails with "Data truncated for column
    'notification_type'". This is Landmine #2 in docs/MULTI_CURRENCY.md, and it
    applies to any Enum column, not just money.

    Idempotent: it rewrites the column definition to the full current set every
    time, so running it twice is a no-op and adding a future value needs no new
    migration function.
    """
    print("\nMigrating merchant_notifications.notification_type:")
    print("---------------------------------------------------")

    from models.enums import NotificationType

    inspector = inspect(db.engine)
    if 'merchant_notifications' not in inspector.get_table_names():
        print("- merchant_notifications table does not exist yet; skipping.")
        return True

    if db.engine.dialect.name != 'mysql':
        print(f"- dialect is {db.engine.dialect.name}, not mysql; nothing to alter.")
        return True

    # SQLAlchemy stores Enum columns by NAME, so the ENUM must list the member
    # names ('REEL_LIKED'), not their values ('reel_liked').
    names = [m.name for m in NotificationType]
    values_sql = ", ".join(f"'{n}'" for n in names)

    try:
        with db.engine.connect() as conn:
            conn.execute(text(
                f"ALTER TABLE merchant_notifications "
                f"MODIFY COLUMN notification_type ENUM({values_sql}) NOT NULL"
            ))
            conn.commit()
        print(f"\u2713 notification_type now accepts: {', '.join(names)}")
        return True
    except Exception as e:
        print(f"\u2717 Failed to alter notification_type: {e}")
        return False


def run_migrations():
    """Run all database migrations."""
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("DATABASE MIGRATION SCRIPT")
        print("=" * 50)
        print("\nThis script will apply pending database migrations.")
        print("It's safe to run on existing databases.\n")
        
        try:
            # Run migrations
            success = migrate_date_of_birth_gender_columns()
            success = migrate_notification_type_enum() and success
            
            if success:
                print("\n" + "=" * 50)
                print("✓ All migrations completed successfully!")
                print("=" * 50)
            else:
                print("\n" + "=" * 50)
                print("⚠ Some migrations may have failed. Please check the errors above.")
                print("=" * 50)
        
        except Exception as e:
            print("\n" + "=" * 50)
            print("✗ ERROR: Migration failed!")
            print("=" * 50)
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = run_migrations()
    exit(0 if success else 1)

