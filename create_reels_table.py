"""
Simple script to create reels table using SQLAlchemy.
This uses db.create_all() which will create the table if it doesn't exist.
"""
from app import create_app
from common.database import db
from models.reel import Reel

def create_reels_table():
    """Create reels table if it doesn't exist."""
    app = create_app()
    with app.app_context():
        try:
            # Import the Reel model to ensure it's registered
            # Create all tables (will only create missing ones)
            db.create_all()
            print("✅ Reels table created successfully!")
            print("✅ You can now test the reel upload API in Postman.")
        except Exception as e:
            print(f"❌ Error creating reels table: {str(e)}")
            raise

if __name__ == "__main__":
    create_reels_table()

