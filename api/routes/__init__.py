from flask import Blueprint
from .catalog_routes import catalog_bp
from .product_auxiliary_routes import product_aux_bp

def init_routes(app):
    """Initialize all route blueprints."""
    app.register_blueprint(catalog_bp, url_prefix='/api/catalog')
    app.register_blueprint(product_aux_bp, url_prefix='/api/auxiliary') 