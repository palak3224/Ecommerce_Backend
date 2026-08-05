"""
S3 storage for merchant intro videos.

Composes ReelsS3Service rather than duplicating it: that service already owns
the video bucket, the CloudFront URL scheme, multipart upload and the ffmpeg
thumbnail generator. Intro videos live under their own key prefix in the same
bucket so lifecycle rules can target them independently.
"""

import uuid
from typing import Dict, Optional

from botocore.exceptions import ClientError
from flask import current_app

from services.reels_s3_service import get_reels_s3_service

INTRO_VIDEO_PREFIX = 'merchant-intro-videos'

CONTENT_TYPE_BY_EXTENSION = {
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
}


class MerchantIntroVideoS3Service:
    """Upload/delete merchant intro videos and their thumbnails."""

    def __init__(self):
        # Raises ValueError when AWS/CloudFront config is missing — callers
        # translate that into a 500 with a configuration hint.
        self._reels = get_reels_s3_service()

    @property
    def bucket_name(self):
        return self._reels.bucket_name

    def _video_key(self, merchant_id: int, video_id: int, extension: str = 'mp4') -> str:
        # A UUID in the key means a replacement never reuses a URL, so we can
        # cache immutably at the CDN and never serve a stale video.
        return f"{INTRO_VIDEO_PREFIX}/{merchant_id}/{video_id}-{uuid.uuid4().hex}.{extension}"

    def _thumbnail_key(self, video_key: str) -> str:
        base = video_key.rsplit('.', 1)[0]
        return f"{base}_thumb.jpg"

    def upload_intro_video(
        self,
        file,
        merchant_id: int,
        video_id: int,
        file_extension: str = 'mp4',
    ) -> Dict:
        """
        Upload the video (and a best-effort thumbnail) to S3.

        Returns dict with url, s3_key, thumbnail_url, thumbnail_s3_key, bytes.
        Raises on video upload failure; a thumbnail failure is logged and
        returns thumbnail_* as None (ffmpeg is not guaranteed to be installed).
        """
        if not file:
            raise ValueError("File object is required")
        if not isinstance(merchant_id, int) or merchant_id <= 0:
            raise ValueError(f"Invalid merchant_id: {merchant_id}")
        if not isinstance(video_id, int) or video_id <= 0:
            raise ValueError(f"Invalid video_id: {video_id}")

        extension = (file_extension or 'mp4').lower()
        if extension not in CONTENT_TYPE_BY_EXTENSION:
            extension = 'mp4'
        content_type = CONTENT_TYPE_BY_EXTENSION[extension]

        s3_key = self._video_key(merchant_id, video_id, extension)
        thumbnail_s3_key = self._thumbnail_key(s3_key)

        file_size = 0
        try:
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
        except (IOError, OSError, AttributeError):
            current_app.logger.warning(
                "[INTRO_VIDEO_S3] Could not determine file size; proceeding."
            )

        # Thumbnail first, while the original file handle is still readable.
        thumbnail_generated = False
        try:
            file.seek(0)
            thumbnail_generated = self._reels._generate_and_upload_thumbnail(
                file, merchant_id, video_id, thumbnail_s3_key, product_id=None
            )
        except Exception as thumb_error:
            current_app.logger.warning(
                f"[INTRO_VIDEO_S3] Thumbnail generation failed for intro video "
                f"{video_id} (continuing without one): {thumb_error}"
            )

        try:
            file.seek(0)
            self._reels.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'ContentDisposition': 'inline',
                    # Safe to cache forever: the key is UUID-unique per upload.
                    'CacheControl': 'public, max-age=31536000, immutable',
                },
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            current_app.logger.error(
                f"[INTRO_VIDEO_S3] Upload failed for merchant {merchant_id}: "
                f"{error_code} — {error_message}"
            )
            raise Exception(f"S3 upload failed ({error_code}): {error_message}")

        current_app.logger.info(
            f"[INTRO_VIDEO_S3] Uploaded intro video {video_id} for merchant "
            f"{merchant_id}: {s3_key} ({file_size} bytes)"
        )

        return {
            'url': self._reels._generate_cloudfront_url(s3_key),
            's3_key': s3_key,
            'bytes': file_size,
            'thumbnail_url': (
                self._reels._generate_cloudfront_url(thumbnail_s3_key)
                if thumbnail_generated else None
            ),
            'thumbnail_s3_key': thumbnail_s3_key if thumbnail_generated else None,
        }

    def delete_intro_video(
        self, video_s3_key: Optional[str], thumbnail_s3_key: Optional[str] = None
    ) -> bool:
        """
        Best-effort delete. Never raises: an orphaned object is a cleanup-job
        problem, not a reason to fail the merchant's request.
        """
        ok = True
        for key in (video_s3_key, thumbnail_s3_key):
            if not key:
                continue
            try:
                self._reels.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                current_app.logger.info(f"[INTRO_VIDEO_S3] Deleted {key}")
            except Exception as e:
                ok = False
                current_app.logger.warning(
                    f"[INTRO_VIDEO_S3] Failed to delete {key} (orphaned): {e}"
                )
        return ok


_intro_video_s3_service_instance = None


def get_merchant_intro_video_s3_service() -> MerchantIntroVideoS3Service:
    """Singleton accessor, matching the other S3 service factories."""
    global _intro_video_s3_service_instance
    if _intro_video_s3_service_instance is None:
        _intro_video_s3_service_instance = MerchantIntroVideoS3Service()
    return _intro_video_s3_service_instance


def reset_merchant_intro_video_s3_service():
    """Reset the singleton (tests, or after config changes)."""
    global _intro_video_s3_service_instance
    _intro_video_s3_service_instance = None
