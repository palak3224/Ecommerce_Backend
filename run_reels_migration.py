"""
Script to create reels table directly in the database.
Run this if Flask-Migrate is not set up.
"""
import os
from dotenv import load_dotenv
import pymysql
from urllib.parse import urlparse

load_dotenv()

# Parse DATABASE_URI from environment
database_uri = os.getenv('DATABASE_URI', 'mysql+pymysql://root:nihalsql@localhost:3306/ecommerce_db')

# Parse the URI (format: mysql+pymysql://user:password@host:port/database)
# Remove the mysql+pymysql:// prefix
uri = database_uri.replace('mysql+pymysql://', '').replace('mysql://', '')
parts = uri.split('@')
if len(parts) == 2:
    user_pass = parts[0].split(':')
    host_db = parts[1].split('/')
    host_port = host_db[0].split(':')
    
    db_config = {
        'host': host_port[0],
        'port': int(host_port[1]) if len(host_port) > 1 else 3306,
        'user': user_pass[0],
        'password': user_pass[1] if len(user_pass) > 1 else '',
        'database': host_db[1] if len(host_db) > 1 else 'ecommerce_db',
        'charset': 'utf8mb4'
    }
else:
    # Fallback to default
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'nihalsql',
        'database': 'ecommerce_db',
        'charset': 'utf8mb4'
    }

# Read SQL file
sql_file_path = os.path.join(os.path.dirname(__file__), 'migrations', 'sql', '001_create_reels_table.sql')

try:
    # Connect to database
    connection = pymysql.connect(**db_config)
    
    with connection.cursor() as cursor:
        # Read and execute SQL file
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
            # Execute SQL (split by semicolon for multiple statements)
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
        
        connection.commit()
        print("✅ Reels table created successfully!")
        
except Exception as e:
    print(f"❌ Error creating reels table: {str(e)}")
    if 'connection' in locals():
        connection.rollback()
finally:
    if 'connection' in locals():
        connection.close()

