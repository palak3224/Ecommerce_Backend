def init_app(app):
    """
    Initialize email configuration for the application.
    
    Args:
        app: Flask application instance
    """
    # Ensure all required email configurations are set
    required_configs = [
        'MAIL_SERVER', 
        'MAIL_PORT', 
        'MAIL_DEFAULT_SENDER',
        'FRONTEND_URL'
    ]
    
    for config in required_configs:
        if not app.config.get(config):
            app.logger.warning(f"Email configuration missing: {config}")
    
    # Log email configuration status
    if app.config.get('MAIL_SERVER') and app.config.get('MAIL_PORT'):
        app.logger.info(f"Email configured with server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
    else:
        app.logger.warning("Email is not properly configured")