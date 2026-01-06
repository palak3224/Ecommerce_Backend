import cloudinary
import cloudinary.uploader
from typing import Dict, Optional
from flask import current_app
from .base_storage_service import BaseStorageService


class CloudinaryStorageService(BaseStorageService):
    """Cloudinary implementation of storage service."""
    
    def __init__(self, config):
        """
        Initialize Cloudinary storage service.
        
        Args:
            config: Flask app config object with Cloudinary credentials
        """
        self.config = config
        # Configure Cloudinary (it's safe to call multiple times)
        # Cloudinary is already configured in app.py, but we ensure it's set here too
        cloudinary.config(
            cloud_name=config.get('CLOUDINARY_CLOUD_NAME'),
            api_key=config.get('CLOUDINARY_API_KEY'),
            api_secret=config.get('CLOUDINARY_API_SECRET'),
            secure=True
        )
    
    def upload_video(self, file, folder: str, **kwargs) -> Dict:
        """
        Upload video file to Cloudinary.
        
        Args:
            file: File object to upload
            folder: Cloudinary folder path
            **kwargs: Additional Cloudinary options (e.g., resource_type, allowed_formats)
            
        Returns:
            Dict with standardized format:
                - url: Video secure URL
                - public_id: Cloudinary public ID
                - format: Video format
                - bytes: File size
                - duration: Duration in seconds (if available)
                - thumbnail_url: Thumbnail URL if generated
        """
        try:
            # Default options
            upload_options = {
                'folder': folder,
                'resource_type': 'video',
                'unique_filename': True,
                'overwrite': True,
            }
            
            # Merge with any additional options
            upload_options.update(kwargs)
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file,
                **upload_options
            )
            
            # Extract duration if available
            duration = None
            if 'duration' in upload_result:
                duration = int(float(upload_result['duration']))
            
            # Generate thumbnail URL if video was uploaded
            thumbnail_url = None
            if upload_result.get('public_id'):
                try:
                    thumbnail_url = cloudinary.CloudinaryImage(
                        upload_result['public_id']
                    ).build_url(
                        resource_type='video',
                        format='jpg',
                        transformation=[
                            {'width': 640, 'height': 360, 'crop': 'fill'},
                            {'quality': 'auto'},
                            {'fetch_format': 'auto'}
                        ]
                    )
                except Exception as e:
                    current_app.logger.warning(f"Failed to generate thumbnail URL: {str(e)}")
            
            return {
                'url': upload_result.get('secure_url', ''),
                'public_id': upload_result.get('public_id', ''),
                'format': upload_result.get('format', ''),
                'bytes': upload_result.get('bytes', 0),
                'duration': duration,
                'thumbnail_url': thumbnail_url
            }
            
        except Exception as e:
            current_app.logger.error(f"Cloudinary video upload failed: {str(e)}")
            raise Exception(f"Video upload failed: {str(e)}")
    
    def generate_thumbnail(self, video_public_id: str, **kwargs) -> str:
        """
        Generate thumbnail from Cloudinary video.
        
        Args:
            video_public_id: Cloudinary public ID of the video
            **kwargs: Additional transformation options
            
        Returns:
            str: Thumbnail URL
        """
        try:
            # Default thumbnail transformation
            transformation = [
                {'width': 640, 'height': 360, 'crop': 'fill'},
                {'quality': 'auto'},
                {'fetch_format': 'auto'}
            ]
            
            # Allow custom transformations via kwargs
            if 'transformation' in kwargs:
                transformation = kwargs['transformation']
            
            thumbnail_url = cloudinary.CloudinaryImage(video_public_id).build_url(
                resource_type='video',
                format='jpg',
                transformation=transformation
            )
            
            return thumbnail_url
            
        except Exception as e:
            current_app.logger.error(f"Cloudinary thumbnail generation failed: {str(e)}")
            raise Exception(f"Thumbnail generation failed: {str(e)}")
    
    def delete_video(self, public_id: str) -> bool:
        """
        Delete video from Cloudinary.
        
        Args:
            public_id: Cloudinary public ID
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type='video'
            )
            
            return result.get('result') == 'ok'
            
        except Exception as e:
            current_app.logger.error(f"Cloudinary video deletion failed: {str(e)}")
            return False
    
    def get_video_url(self, public_id: str) -> str:
        """
        Get video URL from Cloudinary.
        
        Args:
            public_id: Cloudinary public ID
            
        Returns:
            str: Video secure URL
        """
        try:
            # Build secure URL
            video_url = cloudinary.CloudinaryImage(public_id).build_url(
                resource_type='video'
            )
            return video_url
            
        except Exception as e:
            current_app.logger.error(f"Failed to get Cloudinary video URL: {str(e)}")
            raise Exception(f"Failed to get video URL: {str(e)}")

