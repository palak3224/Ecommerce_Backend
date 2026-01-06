from flask import current_app
from .cloudinary_storage_service import CloudinaryStorageService
from .aws_storage_service import AWSStorageService


def get_storage_service(app_config=None):
    """
    Factory function to get the appropriate storage service instance.
    
    Args:
        app_config: Flask app config object. If None, uses current_app.config
        
    Returns:
        BaseStorageService: Instance of the configured storage service
        
    Raises:
        ValueError: If provider is not supported
    """
    if app_config is None:
        app_config = current_app.config
    
    provider = app_config.get('VIDEO_STORAGE_PROVIDER', 'cloudinary').lower()
    
    if provider == 'cloudinary':
        return CloudinaryStorageService(app_config)
    elif provider == 'aws':
        return AWSStorageService(app_config)
    else:
        raise ValueError(
            f"Unsupported storage provider: {provider}. "
            f"Supported providers: 'cloudinary', 'aws'"
        )

