"""
AWS S3 Service for Reels Video Storage
Handles upload, update, and delete operations for reel videos to S3
Uses boto3 (Python AWS SDK) with multipart upload support for large files
"""
import os
import uuid
import shutil
import subprocess
import tempfile
from flask import current_app
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Dict, Optional, Union


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
    
    def _generate_s3_key(
        self, merchant_id: int, reel_id: int, product_id: Optional[int] = None
    ) -> str:
        """
        Generate S3 key for reel video.
        AOIN: reels/{merchant_id}/product-{product_id}/{reel_id}.mp4
        External: reels/{merchant_id}/external/{reel_id}.mp4
        """
        prefix = self.s3_prefix.rstrip('/')
        if product_id is not None and product_id > 0:
            return f"{prefix}/{merchant_id}/product-{product_id}/{reel_id}.mp4"
        return f"{prefix}/{merchant_id}/external/{reel_id}.mp4"
    
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
        reel_id: int,
        product_id: Optional[int] = None,
        file_extension: str = 'mp4',
    ) -> Dict:
        """
        Upload a reel video file to S3.
        For AOIN reels pass product_id; for external reels pass product_id=None.

        Args:
            file: FileStorage object from Flask request
            merchant_id: Merchant ID
            reel_id: Reel ID
            product_id: Product ID (None for external reels)
            file_extension: File extension (default: mp4)

        Returns:
            dict: url, s3_key, bytes, thumbnail_url, thumbnail_s3_key
        """
        if not file:
            raise ValueError("File object is required")
        if not isinstance(merchant_id, int) or merchant_id <= 0:
            raise ValueError(f"Invalid merchant_id: {merchant_id}")
        if not isinstance(reel_id, int) or reel_id <= 0:
            raise ValueError(f"Invalid reel_id: {reel_id}")
        try:
            current_app.logger.info(
                f"[REELS_S3] Starting S3 upload for reel {reel_id}: "
                f"merchant_id={merchant_id}, product_id={product_id}, "
                f"filename={getattr(file, 'filename', 'unknown')}, bucket={self.bucket_name}"
            )
            s3_key = self._generate_s3_key(merchant_id, reel_id, product_id=product_id)
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
            
            current_app.logger.info("=" * 80)
            current_app.logger.info(f"[REELS_S3] 🖼️  STARTING THUMBNAIL GENERATION PROCESS")
            current_app.logger.info(f"[REELS_S3] 📋 Reel ID: {reel_id}")
            current_app.logger.info(f"[REELS_S3] 📋 Merchant ID: {merchant_id}")
            current_app.logger.info(f"[REELS_S3] 📋 Product ID: {product_id}")
            current_app.logger.info(f"[REELS_S3] 📋 Thumbnail S3 Key: {thumbnail_s3_key}")
            current_app.logger.info(f"[REELS_S3] 📋 Thumbnail URL: {thumbnail_url}")
            current_app.logger.info("=" * 80)
            
            # Generate thumbnail BEFORE uploading video (so we can read from original file)
            thumbnail_generated = False
            try:
                # Reset file pointer for thumbnail generation
                current_app.logger.info(f"[REELS_S3] ⏳ Step 1: Resetting file pointer for thumbnail generation...")
                if hasattr(file, 'seek'):
                    try:
                        file.seek(0)
                        file_position = file.tell()
                        current_app.logger.info(f"[REELS_S3] ✅ File pointer reset to position: {file_position}")
                    except Exception as seek_error:
                        current_app.logger.error(f"[REELS_S3] ❌ Failed to reset file pointer: {str(seek_error)}")
                        raise
                else:
                    current_app.logger.warning(f"[REELS_S3] ⚠️  File object does not have 'seek' method")
                
                current_app.logger.info(f"[REELS_S3] ⏳ Step 2: Calling thumbnail generation method...")
                thumbnail_generated = self._generate_and_upload_thumbnail(
                    file, merchant_id, reel_id, thumbnail_s3_key, product_id=product_id
                )
                
                if thumbnail_generated:
                    current_app.logger.info("=" * 80)
                    current_app.logger.info(f"[REELS_S3] ✅ SUCCESS: Thumbnail generated and uploaded!")
                    current_app.logger.info(f"[REELS_S3] 📋 Thumbnail URL: {thumbnail_url}")
                    current_app.logger.info("=" * 80)
                else:
                    current_app.logger.warning("=" * 80)
                    current_app.logger.warning(f"[REELS_S3] ⚠️  WARNING: Thumbnail generation returned False")
                    current_app.logger.warning(f"[REELS_S3] 📋 This might be due to ffmpeg not being available")
                    current_app.logger.warning("=" * 80)
                    
            except Exception as thumb_error:
                # Log but don't fail the upload if thumbnail generation fails
                current_app.logger.error("=" * 80)
                current_app.logger.error(f"[REELS_S3] ❌ ERROR: Thumbnail generation failed for reel {reel_id}")
                current_app.logger.error(f"[REELS_S3] ❌ Error Type: {type(thumb_error).__name__}")
                current_app.logger.error(f"[REELS_S3] ❌ Error Message: {str(thumb_error)}")
                current_app.logger.error(f"[REELS_S3] ❌ Error Details:", exc_info=True)
                current_app.logger.error("=" * 80)
            
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
        reel_id: int,
        thumbnail_s3_key: str,
        product_id: Optional[int] = None,
    ) -> bool:
        """
        Generate thumbnail from video and upload to S3.
        
        Args:
            video_file: Video file object
            merchant_id: Merchant ID
            reel_id: Reel ID
            thumbnail_s3_key: S3 key for thumbnail
            product_id: Product ID (optional, for external reels None)
            
        Returns:
            bool: True if thumbnail was generated and uploaded successfully
        """
        current_app.logger.info(f"[REELS_S3] 🎬 THUMBNAIL GENERATION METHOD CALLED")
        
        try:
            # Step 1: Reset file pointer
            current_app.logger.info(f"[REELS_S3] 📍 Step 2.1: Checking file object type and resetting pointer...")
            current_app.logger.info(f"[REELS_S3] 📍 File object type: {type(video_file)}")
            current_app.logger.info(f"[REELS_S3] 📍 File object has 'seek': {hasattr(video_file, 'seek')}")
            current_app.logger.info(f"[REELS_S3] 📍 File object has 'read': {hasattr(video_file, 'read')}")
            
            if hasattr(video_file, 'seek'):
                try:
                    video_file.seek(0)
                    position = video_file.tell() if hasattr(video_file, 'tell') else 'unknown'
                    current_app.logger.info(f"[REELS_S3] ✅ File pointer reset successfully. Position: {position}")
                except Exception as seek_error:
                    current_app.logger.error(f"[REELS_S3] ❌ Failed to seek file: {str(seek_error)}")
                    raise
            else:
                current_app.logger.warning(f"[REELS_S3] ⚠️  File object does not support seeking")
            
            # Step 2: Create temporary files
            current_app.logger.info(f"[REELS_S3] 📍 Step 2.2: Creating temporary files...")
            temp_video = None
            temp_thumbnail = None
            
            try:
                # Save video to temp file
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.3: Saving video to temporary file...")
                temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                current_app.logger.info(f"[REELS_S3] 📍 Temp video file path: {temp_video.name}")
                
                # Reset file pointer before reading
                if hasattr(video_file, 'seek'):
                    video_file.seek(0)
                
                # Read video file
                current_app.logger.info(f"[REELS_S3] 📍 Reading video file content...")
                video_content = video_file.read()
                video_size = len(video_content) if video_content else 0
                current_app.logger.info(f"[REELS_S3] ✅ Video content read. Size: {video_size} bytes")
                
                if video_size == 0:
                    current_app.logger.error(f"[REELS_S3] ❌ Video file is empty! Cannot generate thumbnail.")
                    return False
                
                # Write to temp file
                temp_video.write(video_content)
                temp_video.flush()
                temp_video.close()
                current_app.logger.info(f"[REELS_S3] ✅ Video saved to temp file: {temp_video.name}")
                
                # Verify temp file exists and has content
                if not os.path.exists(temp_video.name):
                    current_app.logger.error(f"[REELS_S3] ❌ Temp video file was not created!")
                    return False
                
                temp_file_size = os.path.getsize(temp_video.name)
                current_app.logger.info(f"[REELS_S3] ✅ Temp video file verified. Size: {temp_file_size} bytes")
                
                if temp_file_size == 0:
                    current_app.logger.error(f"[REELS_S3] ❌ Temp video file is empty!")
                    return False
                
                # Create temp thumbnail file
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.4: Creating temporary thumbnail file...")
                temp_thumbnail = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                current_app.logger.info(f"[REELS_S3] 📍 Temp thumbnail file path: {temp_thumbnail.name}")
                temp_thumbnail.close()
                current_app.logger.info(f"[REELS_S3] ✅ Temp thumbnail file created")
                
                # Step 3: Check if ffmpeg is available and find its path
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.5: Checking if ffmpeg is available...")
                current_app.logger.info(f"[REELS_S3] 📍 Current PATH: {os.environ.get('PATH', 'Not set')}")
                
                # Try to find ffmpeg using multiple methods
                ffmpeg_path = None
                possible_paths = [
                    '/usr/bin/ffmpeg',
                    '/usr/local/bin/ffmpeg',
                    '/bin/ffmpeg',
                    'ffmpeg'  # Try PATH as fallback
                ]
                
                # First try shutil.which (more reliable)
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path:
                    current_app.logger.info(f"[REELS_S3] ✅ Found ffmpeg using shutil.which: {ffmpeg_path}")
                else:
                    # Try common paths
                    current_app.logger.info(f"[REELS_S3] 📍 shutil.which didn't find ffmpeg, trying common paths...")
                    for path in possible_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            ffmpeg_path = path
                            current_app.logger.info(f"[REELS_S3] ✅ Found ffmpeg at: {ffmpeg_path}")
                            break
                
                if not ffmpeg_path:
                    # Try subprocess to find it
                    try:
                        which_result = subprocess.run(
                            ['which', 'ffmpeg'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=5
                        )
                        if which_result.returncode == 0:
                            ffmpeg_path = which_result.stdout.decode().strip()
                            current_app.logger.info(f"[REELS_S3] ✅ Found ffmpeg using 'which': {ffmpeg_path}")
                    except Exception as which_error:
                        current_app.logger.warning(f"[REELS_S3] ⚠️  'which' command failed: {str(which_error)}")
                
                if not ffmpeg_path:
                    current_app.logger.error(f"[REELS_S3] ❌ ffmpeg not found in PATH or common locations!")
                    current_app.logger.error(f"[REELS_S3] 📍 PATH: {os.environ.get('PATH', 'Not set')}")
                    current_app.logger.error(f"[REELS_S3] 📍 Tried paths: {possible_paths}")
                    return False
                
                # Verify ffmpeg works
                try:
                    ffmpeg_check = subprocess.run(
                        [ffmpeg_path, '-version'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5
                    )
                    if ffmpeg_check.returncode == 0:
                        version_output = ffmpeg_check.stderr.decode()[:100] if ffmpeg_check.stderr else ffmpeg_check.stdout.decode()[:100]
                        current_app.logger.info(f"[REELS_S3] ✅ ffmpeg is working!")
                        current_app.logger.info(f"[REELS_S3] 📍 ffmpeg version info: {version_output[:200]}")
                    else:
                        current_app.logger.error(f"[REELS_S3] ❌ ffmpeg found but check failed with return code: {ffmpeg_check.returncode}")
                        if ffmpeg_check.stderr:
                            current_app.logger.error(f"[REELS_S3] ❌ Error: {ffmpeg_check.stderr.decode()[:200]}")
                        return False
                except Exception as check_error:
                    current_app.logger.error(f"[REELS_S3] ❌ Error running ffmpeg: {str(check_error)}")
                    return False
                
                # Step 4: Use ffmpeg to extract frame at 1 second
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.6: Running ffmpeg to extract frame at 1 second...")
                current_app.logger.info(f"[REELS_S3] 📍 Command: {ffmpeg_path} -i {temp_video.name} -ss 00:00:01 -vframes 1 -q:v 2 -y {temp_thumbnail.name}")
                
                cmd = [
                    ffmpeg_path,  # Use the found path
                    '-i', temp_video.name,
                    '-ss', '00:00:01',  # Seek to 1 second
                    '-vframes', '1',    # Extract 1 frame
                    '-q:v', '2',        # High quality
                    '-y',               # Overwrite output
                    temp_thumbnail.name
                ]
                
                current_app.logger.info(f"[REELS_S3] 📍 Full command: {' '.join(cmd)}")
                
                # Run ffmpeg
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # 30 second timeout
                )
                
                current_app.logger.info(f"[REELS_S3] 📍 ffmpeg return code: {result.returncode}")
                
                if result.stdout:
                    current_app.logger.info(f"[REELS_S3] 📍 ffmpeg stdout: {result.stdout.decode()[:200]}")
                
                if result.stderr:
                    stderr_output = result.stderr.decode()
                    current_app.logger.info(f"[REELS_S3] 📍 ffmpeg stderr (first 500 chars): {stderr_output[:500]}")
                
                if result.returncode != 0:
                    # If seeking to 1 second fails, try first frame
                    current_app.logger.warning(f"[REELS_S3] ⚠️  First attempt failed. Trying to extract first frame instead...")
                    
                    cmd_fallback = [
                        ffmpeg_path,  # Use the found path
                        '-i', temp_video.name,
                        '-vframes', '1',
                        '-q:v', '2',
                        '-y',
                        temp_thumbnail.name
                    ]
                    
                    current_app.logger.info(f"[REELS_S3] 📍 Fallback command: {' '.join(cmd_fallback)}")
                    
                    result = subprocess.run(
                        cmd_fallback,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30
                    )
                    
                    current_app.logger.info(f"[REELS_S3] 📍 Fallback return code: {result.returncode}")
                    
                    if result.stderr:
                        stderr_output = result.stderr.decode()
                        current_app.logger.info(f"[REELS_S3] 📍 Fallback stderr (first 500 chars): {stderr_output[:500]}")
                
                if result.returncode != 0:
                    current_app.logger.error(f"[REELS_S3] ❌ ffmpeg failed to generate thumbnail!")
                    current_app.logger.error(f"[REELS_S3] ❌ Return code: {result.returncode}")
                    if result.stderr:
                        current_app.logger.error(f"[REELS_S3] ❌ Error output: {result.stderr.decode()}")
                    return False
                
                current_app.logger.info(f"[REELS_S3] ✅ ffmpeg executed successfully!")
                
                # Step 5: Check if thumbnail was created
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.7: Verifying thumbnail file was created...")
                if not os.path.exists(temp_thumbnail.name):
                    current_app.logger.error(f"[REELS_S3] ❌ Thumbnail file does not exist at: {temp_thumbnail.name}")
                    return False
                
                thumbnail_size = os.path.getsize(temp_thumbnail.name)
                current_app.logger.info(f"[REELS_S3] ✅ Thumbnail file exists. Size: {thumbnail_size} bytes")
                
                if thumbnail_size == 0:
                    current_app.logger.error(f"[REELS_S3] ❌ Thumbnail file is empty!")
                    return False
                
                # Step 6: Upload thumbnail to S3
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.8: Uploading thumbnail to S3...")
                current_app.logger.info(f"[REELS_S3] 📍 Bucket: {self.bucket_name}")
                current_app.logger.info(f"[REELS_S3] 📍 Key: {thumbnail_s3_key}")
                
                with open(temp_thumbnail.name, 'rb') as thumb_file:
                    self.s3_client.upload_fileobj(
                        thumb_file,
                        self.bucket_name,
                        thumbnail_s3_key,
                        ExtraArgs={'ContentType': 'image/jpeg'}
                    )
                
                current_app.logger.info(f"[REELS_S3] ✅ Thumbnail uploaded to S3 successfully!")
                current_app.logger.info(f"[REELS_S3] 📍 S3 Key: {thumbnail_s3_key}")
                
                # Verify the upload
                try:
                    self.s3_client.head_object(Bucket=self.bucket_name, Key=thumbnail_s3_key)
                    current_app.logger.info(f"[REELS_S3] ✅ Thumbnail verified in S3!")
                except Exception as verify_error:
                    current_app.logger.warning(f"[REELS_S3] ⚠️  Could not verify thumbnail in S3: {str(verify_error)}")
                
                return True
                
            finally:
                # Cleanup temp files
                current_app.logger.info(f"[REELS_S3] 📍 Step 2.9: Cleaning up temporary files...")
                try:
                    if temp_video and os.path.exists(temp_video.name):
                        os.unlink(temp_video.name)
                        current_app.logger.info(f"[REELS_S3] ✅ Deleted temp video: {temp_video.name}")
                    if temp_thumbnail and os.path.exists(temp_thumbnail.name):
                        os.unlink(temp_thumbnail.name)
                        current_app.logger.info(f"[REELS_S3] ✅ Deleted temp thumbnail: {temp_thumbnail.name}")
                except Exception as cleanup_error:
                    current_app.logger.warning(f"[REELS_S3] ⚠️  Failed to cleanup temp files: {str(cleanup_error)}")
            
        except FileNotFoundError as fnf_error:
            current_app.logger.error("=" * 80)
            current_app.logger.error(f"[REELS_S3] ❌ FileNotFoundError: {str(fnf_error)}")
            current_app.logger.error(f"[REELS_S3] 📍 PATH environment: {os.environ.get('PATH', 'Not set')}")
            current_app.logger.error(f"[REELS_S3] 📍 Install ffmpeg: sudo apt-get install ffmpeg (Ubuntu) or brew install ffmpeg (macOS)")
            current_app.logger.error("=" * 80)
            return False
        except subprocess.TimeoutExpired as timeout_error:
            current_app.logger.error("=" * 80)
            current_app.logger.error(f"[REELS_S3] ❌ TimeoutError: Thumbnail generation timed out after 30 seconds!")
            current_app.logger.error(f"[REELS_S3] 📍 The video file might be corrupted or too large to process")
            current_app.logger.error("=" * 80)
            return False
        except Exception as e:
            current_app.logger.error("=" * 80)
            current_app.logger.error(f"[REELS_S3] ❌ Unexpected error generating thumbnail!")
            current_app.logger.error(f"[REELS_S3] ❌ Error Type: {type(e).__name__}")
            current_app.logger.error(f"[REELS_S3] ❌ Error Message: {str(e)}")
            current_app.logger.error(f"[REELS_S3] ❌ Full traceback:", exc_info=True)
            current_app.logger.error("=" * 80)
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

