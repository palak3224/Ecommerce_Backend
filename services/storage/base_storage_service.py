from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseStorageService(ABC):
    """Abstract base class for video storage services."""
    
    @abstractmethod
    def upload_video(self, file, folder: str, **kwargs) -> Dict:
        """
        Upload video file to storage.
        
        Args:
            file: File object to upload
            folder: Folder/path where video should be stored
            **kwargs: Additional provider-specific options
            
        Returns:
            Dict with keys:
                - url: str - Video URL (CDN URL if applicable)
                - public_id: str - Storage identifier (Cloudinary public_id or S3 key)
                - format: str - File format (mp4, mov, etc.)
                - bytes: int - File size in bytes
                - duration: Optional[int] - Duration in seconds (if available)
                - thumbnail_url: Optional[str] - Thumbnail URL if generated
        """
        pass
    
    @abstractmethod
    def generate_thumbnail(self, video_public_id: str, **kwargs) -> str:
        """
        Generate thumbnail from video.
        
        Args:
            video_public_id: Storage identifier of the video
            **kwargs: Additional provider-specific options
            
        Returns:
            str: Thumbnail URL
        """
        pass
    
    @abstractmethod
    def delete_video(self, public_id: str) -> bool:
        """
        Delete video from storage.
        
        Args:
            public_id: Storage identifier of the video
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_video_url(self, public_id: str) -> str:
        """
        Get video URL (CDN URL if applicable).
        
        Args:
            public_id: Storage identifier of the video
            
        Returns:
            str: Video URL
        """
        pass

