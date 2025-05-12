from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from common.cache import cached
import os
import cloudinary
from cloudinary import CloudinaryImage
import cloudinary.uploader
import cloudinary.api

from config import get_config
from common.database import db
from common.cache import cache
from auth.routes import auth_bp
from api.users.routes import users_bp
from api.merchants.routes import merchants_bp
from api.routes.catalog_routes import catalog_bp
from api.routes.product_routes import product_bp
from auth import email_init
from api.routes.product_auxiliary_routes import product_aux_bp

def create_app(config_name='default'):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # Configure Cloudinary
    cloudinary.config(
        cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=app.config['CLOUDINARY_API_KEY'],
        api_secret=app.config['CLOUDINARY_API_SECRET']
    )
    
    # Configure CORS
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "expose_headers": ["Content-Type", "Authorization"]
        }
    })
    
    db.init_app(app)
    cache.init_app(app)
    jwt = JWTManager(app)
    Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(merchants_bp, url_prefix='/api/merchants')
    app.register_blueprint(catalog_bp, url_prefix='/api/catalog')
    app.register_blueprint(product_bp, url_prefix='/api')
    app.register_blueprint(product_aux_bp, url_prefix='/api/product-auxiliary')
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
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404
    
    @app.errorhandler(500)
    def server_error(error):
        return {"error": "Internal server error"}, 500
    
    return app

def add_headers(response):
    """Add necessary CORS headers to all responses."""
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

if __name__ == "__main__":
    app = create_app()
    app.after_request(add_headers)
    email_init.init_app(app)
    app.run(host='0.0.0.0', port=5000)
