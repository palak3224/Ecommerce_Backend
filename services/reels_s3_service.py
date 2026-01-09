"""
AWS S3 Service for Reels Video Storage
Handles upload, update, and delete operations for reel videos to S3
Uses boto3 (Python AWS SDK) with multipart upload support for large files
"""
import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Dict, Optional


class ReelsS3Service:
    """Service for handling reel video uploads to AWS S3"""
    
    def __init__(self):
        """Initialize S3 client with credentials from environment"""
        # Get required environment variables
        self.bucket_name = os.getenv('AWS_S3_REELS_BUCKET', 'aoin-reels-prod')
        self.region = os.getenv('AWS_REGION', 'ap-south-1')
        self.cloudfront_base_url = os.getenv('CLOUDFRONT_REELS_BASE_URL')
        self.s3_prefix = os.getenv('AWS_S3_REELS_PREFIX', 'reels/')
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        # Validate required environment variables
        if not self.cloudfront_base_url:
            raise ValueError("CLOUDFRONT_REELS_BASE_URL environment variable is required")
        
        if not aws_access_key_id:
            raise ValueError("AWS_ACCESS_KEY_ID environment variable is required")
        
        if not aws_secret_access_key:
            raise ValueError("AWS_SECRET_ACCESS_KEY environment variable is required")
        
        # Normalize prefix (ensure it ends with /)
        if self.s3_prefix and not self.s3_prefix.endswith('/'):
            self.s3_prefix = self.s3_prefix + '/'
        
        # Normalize CloudFront URL (remove trailing slash)
        if self.cloudfront_base_url:
            self.cloudfront_base_url = self.cloudfront_base_url.rstrip('/')
        
        # Configure boto3 client
        # Note: boto3 automatically handles multipart uploads for large files (>8MB)
        # The upload_fileobj method automatically uses multipart upload
        try:
            config = Config(
                region_name=self.region,
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            
            # Initialize S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=self.region,
                config=config
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize S3 client: {str(e)}")
    
    def _generate_s3_key(self, merchant_id: int, product_id: int, reel_id: int) -> str:
        """
        Generate S3 key for reel video.
        Format: reels/{merchant_id}/product-{product_id}/{reel_id}.mp4
        (Always uses .mp4 extension as per requirements, even if original file is .webm or .mov)
        
        Args:
            merchant_id: Merchant ID
            product_id: Product ID
            reel_id: Reel ID
            
        Returns:
            str: S3 object key
        """
        # Ensure prefix doesn't have double slashes
        prefix = self.s3_prefix.rstrip('/')
        return f"{prefix}/{merchant_id}/product-{product_id}/{reel_id}.mp4"
    
    def _generate_cloudfront_url(self, s3_key: str) -> str:
        """
        Generate CloudFront URL from S3 key.
        Format: ${CLOUDFRONT_REELS_BASE_URL}/reels/{merchant_id}/product-{product_id}/{reel_id}.mp4
        
        Args:
            s3_key: S3 object key
            
        Returns:
            str: CloudFront URL
        """
        # Ensure no double slashes
        base_url = self.cloudfront_base_url.rstrip('/')
        s3_key_clean = s3_key.lstrip('/')
        return f"{base_url}/{s3_key_clean}"
    
    def _extract_s3_key_from_url(self, cloudfront_url: str) -> Optional[str]:
        """
        Extract S3 key from CloudFront URL.
        
        Args:
            cloudfront_url: CloudFront URL
            
        Returns:
            str: S3 key or None if extraction fails
        """
        if not cloudfront_url:
            return None
        
        # If it's already an S3 key (starts with reels/), return as is
        if cloudfront_url.startswith(self.s3_prefix.rstrip('/')):
            return cloudfront_url
        
        # If it's a CloudFront URL, extract the key
        if self.cloudfront_base_url and self.cloudfront_base_url in cloudfront_url:
            # Remove CloudFront base URL and leading slash
            key = cloudfront_url.replace(self.cloudfront_base_url, '').lstrip('/')
            return key
        
        # If it contains the prefix, try to extract from URL
        if self.s3_prefix.rstrip('/') in cloudfront_url:
            parts = cloudfront_url.split(self.s3_prefix.rstrip('/'))
            if len(parts) > 1:
                return self.s3_prefix.rstrip('/') + '/' + parts[1].split('?')[0]  # Remove query params
        
        return None
    
    def upload_reel_video(
        self, 
        file, 
        merchant_id: int, 
        product_id: int, 
        reel_id: int,
        file_extension: str = 'mp4'
    ) -> Dict:
        """
        Upload a reel video file to S3.
        
        Args:
            file: FileStorage object from Flask request
            merchant_id: Merchant ID
            product_id: Product ID
            reel_id: Reel ID
            file_extension: File extension (default: mp4)
            
        Returns:
            dict: {
                'url': CloudFront URL,
                's3_key': S3 object key (for deletion),
                'bytes': File size in bytes
            }
            
        Raises:
            Exception: If upload fails
        """
        # Validate inputs
        if not file:
            raise ValueError("File object is required")
        
        if not isinstance(merchant_id, int) or merchant_id <= 0:
            raise ValueError(f"Invalid merchant_id: {merchant_id}")
        
        if not isinstance(product_id, int) or product_id <= 0:
            raise ValueError(f"Invalid product_id: {product_id}")
        
        if not isinstance(reel_id, int) or reel_id <= 0:
            raise ValueError(f"Invalid reel_id: {reel_id}")
        
        try:
            current_app.logger.info(
                f"[REELS_S3] Starting S3 upload for reel {reel_id}: "
                f"merchant_id={merchant_id}, product_id={product_id}, "
                f"filename={getattr(file, 'filename', 'unknown')}, bucket={self.bucket_name}"
            )
            
            # Generate S3 key (always uses .mp4 extension as per requirements)
            s3_key = self._generate_s3_key(merchant_id, product_id, reel_id)
            current_app.logger.info(f"[REELS_S3] Generated S3 key: {s3_key}")
            
            # Reset file pointer to beginning (critical for file streams)
            file_position_reset = False
            if hasattr(file, 'seek') and hasattr(file, 'tell'):
                try:
                    current_pos = file.tell()
                    if current_pos != 0:
                        file.seek(0)
                        file_position_reset = True
                        current_app.logger.info(f"[REELS_S3] Reset file pointer from position {current_pos} to 0")
                except (IOError, OSError, AttributeError) as seek_error:
                    current_app.logger.warning(f"[REELS_S3] Could not seek file to beginning: {seek_error}")
                    # Try to reset anyway if possible
                    try:
                        file.seek(0)
                        file_position_reset = True
                    except:
                        pass
            
            # Determine content type based on extension
            content_type_map = {
                'mp4': 'video/mp4',
                'webm': 'video/webm',
                'mov': 'video/quicktime'
            }
            content_type = content_type_map.get(file_extension.lower(), 'video/mp4')
            
            # Get file size (handle different file object types)
            file_size = 0
            try:
                if hasattr(file, 'content_length') and file.content_length:
                    file_size = file.content_length
                elif hasattr(file, 'seek') and hasattr(file, 'tell'):
                    # Try to get size by seeking to end
                    try:
                        file.seek(0, 2)  # Move to end
                        file_size = file.tell()
                        file.seek(0)  # Reset to start
                    except (IOError, OSError, AttributeError):
                        # If we can't determine size, that's okay - S3 will handle it
                        current_app.logger.warning("[REELS_S3] Could not determine file size, proceeding anyway")
                        file_size = 0
            except Exception as size_error:
                current_app.logger.warning(f"[REELS_S3] Error getting file size: {size_error}, proceeding anyway")
            
            upload_args = {
                'ContentType': content_type
            }
            
            # Generate thumbnail S3 key and URL
            thumbnail_s3_key = s3_key.replace('.mp4', '_thumb.jpg')
            thumbnail_url = self._generate_cloudfront_url(thumbnail_s3_key)
            
            # Generate thumbnail BEFORE uploading video (so we can read from original file)
            thumbnail_generated = False
            try:
                # Reset file pointer for thumbnail generation
                if hasattr(file, 'seek'):
                    file.seek(0)
                thumbnail_generated = self._generate_and_upload_thumbnail(
                    file, merchant_id, product_id, reel_id, thumbnail_s3_key
                )
            except Exception as thumb_error:
                # Log but don't fail the upload if thumbnail generation fails
                current_app.logger.warning(
                    f"[REELS_S3] Thumbnail generation failed for reel {reel_id}: {str(thumb_error)}"
                )
            
            # Reset file pointer again for video upload
            if hasattr(file, 'seek'):
                file.seek(0)
            
            current_app.logger.info(
                f"[REELS_S3] Uploading to S3: bucket={self.bucket_name}, "
                f"key={s3_key}, content_type={content_type}, size={file_size} bytes"
            )
            
            # Upload to S3 (boto3 automatically uses multipart upload for large files >8MB)
            # This handles large video files efficiently
            try:
                self.s3_client.upload_fileobj(
                    file,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs=upload_args
                )
            except Exception as upload_error:
                # Log detailed error before re-raising
                current_app.logger.error(
                    f"[REELS_S3] S3 upload_fileobj failed: {str(upload_error)}",
                    exc_info=True
                )
                raise
            
            current_app.logger.info(f"[REELS_S3] S3 upload completed successfully for key: {s3_key}")
            
            # Construct CloudFront URL
            cloudfront_url = self._generate_cloudfront_url(s3_key)
            current_app.logger.info(f"[REELS_S3] CloudFront URL: {cloudfront_url}")
            
            result = {
                'url': cloudfront_url,
                's3_key': s3_key,
                'bytes': file_size,
                'thumbnail_url': thumbnail_url if thumbnail_generated else None,
                'thumbnail_s3_key': thumbnail_s3_key if thumbnail_generated else None
            }
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            current_app.logger.error(
                f"[REELS_S3] AWS S3 upload error for reel {reel_id}: "
                f"Code={error_code}, Message={error_message}, Full error: {str(e)}"
            )
            
            # Provide specific error messages for common issues
            if error_code == 'AccessDenied':
                raise Exception(f"AWS S3 Access Denied: Check your AWS credentials and bucket permissions. Details: {error_message}")
            elif error_code == 'NoSuchBucket':
                raise Exception(f"AWS S3 Bucket not found: {self.bucket_name}. Check your bucket name configuration.")
            elif error_code == 'InvalidAccessKeyId':
                raise Exception(f"AWS S3 Invalid Access Key: Check your AWS_ACCESS_KEY_ID environment variable.")
            elif error_code == 'SignatureDoesNotMatch':
                raise Exception(f"AWS S3 Signature Mismatch: Check your AWS_SECRET_ACCESS_KEY environment variable.")
            elif error_code == 'InvalidBucketName':
                raise Exception(f"AWS S3 Invalid bucket name: {self.bucket_name}")
            elif error_code == 'BucketAlreadyOwnedByYou':
                # This shouldn't happen, but handle gracefully
                raise Exception(f"AWS S3 Bucket already exists: {self.bucket_name}")
            else:
                raise Exception(f"AWS S3 upload failed ({error_code}): {error_message}")
        except ValueError as ve:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            current_app.logger.error(
                f"[REELS_S3] Unexpected error uploading reel video to S3: {str(e)}",
                exc_info=True
            )
            raise Exception(f"Failed to upload reel video to S3: {str(e)}")
    
    def _generate_and_upload_thumbnail(
        self,
        video_file,
        merchant_id: int,
        product_id: int,
        reel_id: int,
        thumbnail_s3_key: str
    ) -> bool:
        """
        Generate thumbnail from video and upload to S3.
        
        Args:
            video_file: Video file object
            merchant_id: Merchant ID
            product_id: Product ID
            reel_id: Reel ID
            thumbnail_s3_key: S3 key for thumbnail
            
        Returns:
            bool: True if thumbnail was generated and uploaded successfully
        """
        import subprocess
        import tempfile
        import os
        
        try:
            # Reset file pointer
            if hasattr(video_file, 'seek'):
                video_file.seek(0)
            
            # Create temporary files
            temp_video = None
            temp_thumbnail = None
            
            try:
                # Save video to temp file
                temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                video_file.seek(0)
                temp_video.write(video_file.read())
                temp_video.flush()
                temp_video.close()
                
                # Create temp thumbnail file
                temp_thumbnail = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                temp_thumbnail.close()
                
                # Use ffmpeg to extract frame at 1 second (or first frame if video is shorter)
                # Command: ffmpeg -i input.mp4 -ss 00:00:01 -vframes 1 -q:v 2 output.jpg
                cmd = [
                    'ffmpeg',
                    '-i', temp_video.name,
                    '-ss', '00:00:01',  # Seek to 1 second
                    '-vframes', '1',    # Extract 1 frame
                    '-q:v', '2',        # High quality
                    '-y',               # Overwrite output
                    temp_thumbnail.name
                ]
                
                # Run ffmpeg
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # 30 second timeout
                )
                
                if result.returncode != 0:
                    # If seeking to 1 second fails, try first frame
                    cmd_fallback = [
                        'ffmpeg',
                        '-i', temp_video.name,
                        '-vframes', '1',
                        '-q:v', '2',
                        '-y',
                        temp_thumbnail.name
                    ]
                    result = subprocess.run(
                        cmd_fallback,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30
                    )
                
                if result.returncode != 0:
                    current_app.logger.warning(
                        f"[REELS_S3] ffmpeg failed to generate thumbnail: {result.stderr.decode()}"
                    )
                    return False
                
                # Check if thumbnail was created
                if not os.path.exists(temp_thumbnail.name) or os.path.getsize(temp_thumbnail.name) == 0:
                    current_app.logger.warning("[REELS_S3] Thumbnail file was not created or is empty")
                    return False
                
                # Upload thumbnail to S3
                with open(temp_thumbnail.name, 'rb') as thumb_file:
                    self.s3_client.upload_fileobj(
                        thumb_file,
                        self.bucket_name,
                        thumbnail_s3_key,
                        ExtraArgs={'ContentType': 'image/jpeg'}
                    )
                
                current_app.logger.info(f"[REELS_S3] Thumbnail uploaded successfully: {thumbnail_s3_key}")
                return True
                
            finally:
                # Cleanup temp files
                try:
                    if temp_video and os.path.exists(temp_video.name):
                        os.unlink(temp_video.name)
                    if temp_thumbnail and os.path.exists(temp_thumbnail.name):
                        os.unlink(temp_thumbnail.name)
                except Exception as cleanup_error:
                    current_app.logger.warning(f"[REELS_S3] Failed to cleanup temp files: {str(cleanup_error)}")
            
        except FileNotFoundError:
            current_app.logger.warning("[REELS_S3] ffmpeg not found. Thumbnail generation skipped.")
            return False
        except subprocess.TimeoutExpired:
            current_app.logger.warning("[REELS_S3] Thumbnail generation timed out")
            return False
        except Exception as e:
            current_app.logger.error(f"[REELS_S3] Error generating thumbnail: {str(e)}", exc_info=True)
            return False
    
    def delete_reel_video(self, url_or_s3_key: str, delete_thumbnail: bool = True) -> bool:
        """
        Delete a reel video file from S3.
        
        Args:
            url_or_s3_key: Either a CloudFront URL or S3 key
            delete_thumbnail: Whether to also delete the associated thumbnail
            
        Returns:
            bool: True if deletion succeeded, False otherwise
            
        Note:
            Does not raise exceptions - logs errors only
        """
        try:
            # Extract S3 key from URL if it's a CloudFront URL
            s3_key = self._extract_s3_key_from_url(url_or_s3_key)
            
            if not s3_key:
                current_app.logger.warning(f"[REELS_S3] Could not extract S3 key from URL: {url_or_s3_key}")
                return False
            
            # Delete video from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            current_app.logger.info(f"[REELS_S3] Successfully deleted reel video from S3: {s3_key}")
            
            # Delete thumbnail if requested
            if delete_thumbnail:
                thumbnail_s3_key = s3_key.replace('.mp4', '_thumb.jpg')
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=thumbnail_s3_key
                    )
                    current_app.logger.info(f"[REELS_S3] Successfully deleted reel thumbnail from S3: {thumbnail_s3_key}")
                except Exception as thumb_error:
                    # Don't fail if thumbnail deletion fails
                    current_app.logger.warning(f"[REELS_S3] Failed to delete thumbnail {thumbnail_s3_key}: {str(thumb_error)}")
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                current_app.logger.warning(f"[REELS_S3] Video file not found in S3 (may have been already deleted): {s3_key}")
            else:
                current_app.logger.error(f"[REELS_S3] AWS S3 delete error: {str(e)}")
            return False
        except Exception as e:
            current_app.logger.error(f"[REELS_S3] Unexpected error deleting reel video from S3: {str(e)}")
            return False


# Singleton instance
_reels_s3_service_instance = None


def get_reels_s3_service():
    """
    Get or create singleton reels S3 service instance.
    
    Returns:
        ReelsS3Service: Singleton instance of the S3 service
        
    Raises:
        ValueError: If required environment variables are missing
        Exception: If S3 client initialization fails
    """
    global _reels_s3_service_instance
    
    # If instance exists and is valid, return it
    if _reels_s3_service_instance is not None:
        return _reels_s3_service_instance
    
    # Try to create new instance
    try:
        _reels_s3_service_instance = ReelsS3Service()
        return _reels_s3_service_instance
    except Exception as e:
        # Log error
        try:
            from flask import current_app
            if current_app:
                current_app.logger.error(
                    f"[REELS_S3] Failed to initialize S3 service: {str(e)}",
                    exc_info=True
                )
        except:
            # If we can't log, that's okay - just raise the error
            pass
        
        # Reset instance
        _reels_s3_service_instance = None
        
        # Re-raise the error so caller knows initialization failed
        raise


def reset_reels_s3_service():
    """Reset the singleton instance (useful for testing or after code changes)"""
    global _reels_s3_service_instance
    _reels_s3_service_instance = None


def generate_thumbnail_for_existing_reel(video_s3_key: str) -> Optional[Dict]:
    """
    Generate thumbnail for an existing reel by downloading video from S3.
    This is useful for regenerating thumbnails for reels that were uploaded before thumbnail generation was implemented.
    
    Args:
        video_s3_key: S3 key of the video file
        
    Returns:
        dict with 'thumbnail_url' and 'thumbnail_s3_key' if successful, None otherwise
    """
    import tempfile
    import os
    import subprocess
    
    service = get_reels_s3_service()
    temp_video = None
    temp_thumbnail = None
    
    try:
        # Extract thumbnail S3 key from video key
        thumbnail_s3_key = video_s3_key.replace('.mp4', '_thumb.jpg')
        thumbnail_url = service._generate_cloudfront_url(thumbnail_s3_key)
        
        # Download video to temp file
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_video.close()
        
        # Download from S3
        service.s3_client.download_file(
            service.bucket_name,
            video_s3_key,
            temp_video.name
        )
        
        # Create temp thumbnail file
        temp_thumbnail = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_thumbnail.close()
        
        # Use ffmpeg to extract frame
        cmd = [
            'ffmpeg',
            '-i', temp_video.name,
            '-ss', '00:00:01',
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            temp_thumbnail.name
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        if result.returncode != 0:
            # Try first frame
            cmd_fallback = [
                'ffmpeg',
                '-i', temp_video.name,
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                temp_thumbnail.name
            ]
            result = subprocess.run(
                cmd_fallback,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )
        
        if result.returncode != 0 or not os.path.exists(temp_thumbnail.name) or os.path.getsize(temp_thumbnail.name) == 0:
            return None
        
        # Upload thumbnail to S3
        with open(temp_thumbnail.name, 'rb') as thumb_file:
            service.s3_client.upload_fileobj(
                thumb_file,
                service.bucket_name,
                thumbnail_s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
        
        return {
            'thumbnail_url': thumbnail_url,
            'thumbnail_s3_key': thumbnail_s3_key
        }
            
    except FileNotFoundError:
        # ffmpeg not available
        try:
            from flask import current_app
            if current_app:
                current_app.logger.warning("[REELS_S3] ffmpeg not found. Cannot generate thumbnail for existing reel.")
        except:
            pass
        return None
    except Exception as e:
        try:
            from flask import current_app
            if current_app:
                current_app.logger.error(f"[REELS_S3] Failed to generate thumbnail for existing reel: {str(e)}", exc_info=True)
        except:
            pass
        return None
    finally:
        # Cleanup temp files
        if temp_video and os.path.exists(temp_video.name):
            try:
                os.unlink(temp_video.name)
            except Exception:
                pass
        if temp_thumbnail and os.path.exists(temp_thumbnail.name):
            try:
                os.unlink(temp_thumbnail.name)
            except Exception:
                pass

