"""
Merchant intro video CRUD.

One active video per merchant. Every write path takes a row lock before
deciding whether one already exists, because SELECT-then-INSERT races cleanly
through a double-clicked upload button.
"""

import os
import shutil
import subprocess
from datetime import datetime, timedelta

from flask import current_app

from common.database import db
from common.text_sanitize import sanitize_plain_text, validate_text_length
from models.merchant_intro_video import (
    MerchantIntroVideo,
    MODERATION_APPROVED,
    MODERATION_PENDING,
    MODERATION_REJECTED,
    STATUS_PROCESSING,
    STATUS_READY,
)

# --------------------------------------------------------------------------- #
# Limits
# --------------------------------------------------------------------------- #

# mp4/mov only. webm is deliberately excluded: it does not play in Safari/iOS
# and this codebase has no transcoding pipeline, so accepting it would ship
# videos a large share of shoppers cannot watch.
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov'}
ALLOWED_VIDEO_MIME_TYPES = {'video/mp4', 'video/quicktime'}

# 50MB, not 100. app.config['MAX_CONTENT_LENGTH'] is 100MB and Werkzeug rejects
# oversize bodies before the view runs, so the ceiling needs headroom for
# multipart overhead if the merchant is to get a JSON error rather than a 413.
MAX_VIDEO_SIZE = 50 * 1024 * 1024
MAX_VIDEO_DURATION_SECONDS = 60

MAX_TITLE_CHARS = 120
MAX_CAPTION_CHARS = 500

# @rate_limit degrades to a no-op without Redis, so the real guard is counted
# in the database.
MAX_UPLOADS_PER_DAY = 10


class IntroVideoError(Exception):
    """Carries an HTTP status and optional field details up to the route."""

    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


def _moderation_default():
    """
    Moderation is off at launch (matching how reels ship). Flipping the config
    flag routes new uploads to a review queue without a migration.
    """
    if current_app.config.get('MERCHANT_INTRO_VIDEO_MODERATION_ENABLED', False):
        return MODERATION_PENDING
    return MODERATION_APPROVED


def _extension_of(filename):
    if not filename or '.' not in filename:
        return None
    return filename.rsplit('.', 1)[1].lower()


def _detect_mime(file):
    """
    Detect the real container from the file header.

    Deliberately does NOT fall back to the filename. An extension fallback
    would defeat the whole check: any payload renamed to .mp4 would be
    "detected" as video/mp4 and wave itself through. If we can read a header,
    it has to actually be an ISO-BMFF container.

    Returns None only when the file is too short to hold a header, which the
    size check has already rejected.
    """
    header = file.read(12)
    file.seek(0)

    if len(header) < 12:
        return None

    box_type = header[4:8]

    # ISO-BMFF (mp4/mov): bytes 4-8 are 'ftyp'; the preceding 4 are the box size.
    if box_type == b'ftyp':
        brand = header[8:12]
        if brand[:2] == b'qt':
            return 'video/quicktime'
        return 'video/mp4'

    # Classic QuickTime predates the ftyp box and opens on one of these atoms.
    # Still a structural check — an arbitrary payload will not have a valid
    # atom type at offset 4.
    if box_type in (b'moov', b'mdat', b'free', b'skip', b'wide', b'pnot'):
        return 'video/quicktime'

    return None


def _find_ffprobe():
    """
    Locate ffprobe.

    shutil.which alone is not enough: under gunicorn the service PATH is often
    just the virtualenv bin directory, so a perfectly good /usr/bin/ffprobe is
    invisible to it. reels_s3_service hits the same problem and falls back to
    explicit paths; do the same here rather than silently giving up on duration
    verification in production.
    """
    found = shutil.which('ffprobe')
    if found:
        return found
    for path in ('/usr/bin/ffprobe', '/usr/local/bin/ffprobe', '/bin/ffprobe'):
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None


def _probe_duration_and_resolution(file):
    """
    Read duration/resolution with ffprobe when the binary is available.

    Returns (duration_seconds|None, resolution|None, verified: bool). ffmpeg is
    optional in this deployment (see reels_s3_service), so a missing binary is
    not an error — it just means duration stays an unverified client hint.
    """
    ffprobe = _find_ffprobe()
    if not ffprobe:
        current_app.logger.info(
            "[INTRO_VIDEO] ffprobe unavailable; duration will not be verified."
        )
        return None, None, False

    import tempfile

    temp_path = None
    try:
        file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp:
            temp_path = temp.name
            shutil.copyfileobj(file, temp)
        file.seek(0)

        result = subprocess.run(
            [
                ffprobe, '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height:format=duration',
                '-of', 'default=noprint_wrappers=1',
                temp_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None, None, False

        output = result.stdout.decode('utf-8', errors='ignore')
        width = height = duration = None
        for line in output.splitlines():
            key, _, value = line.partition('=')
            if key == 'width':
                width = value.strip()
            elif key == 'height':
                height = value.strip()
            elif key == 'duration':
                try:
                    duration = int(round(float(value.strip())))
                except (TypeError, ValueError):
                    duration = None

        resolution = f"{width}x{height}" if width and height else None
        return duration, resolution, duration is not None
    except Exception as e:
        current_app.logger.warning(f"[INTRO_VIDEO] ffprobe failed: {e}")
        return None, None, False
    finally:
        file.seek(0)
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _validate_video_file(file):
    """
    Validate the upload and return (extension, size, mime, duration,
    resolution, duration_verified). Raises IntroVideoError on any failure.
    """
    if file is None or not getattr(file, 'filename', ''):
        raise IntroVideoError("No video file provided.", 400)

    extension = _extension_of(file.filename)
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise IntroVideoError(
            f"Invalid file type. Allowed formats: "
            f"{', '.join(sorted(e.upper() for e in ALLOWED_VIDEO_EXTENSIONS))}.",
            400,
            {'field': 'video', 'allowed_extensions': sorted(ALLOWED_VIDEO_EXTENSIONS)},
        )

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size == 0:
        raise IntroVideoError("Video file is empty.", 400, {'field': 'video'})
    if size > MAX_VIDEO_SIZE:
        raise IntroVideoError(
            f"Video must be smaller than {MAX_VIDEO_SIZE // (1024 * 1024)}MB.",
            400,
            {
                'field': 'video',
                'file_size_bytes': size,
                'max_size_bytes': MAX_VIDEO_SIZE,
            },
        )

    # Reject on failure to recognise, not just on recognising something wrong:
    # an unrecognised container with a .mp4 name is exactly the case worth
    # blocking.
    mime = _detect_mime(file)
    if mime is None or mime not in ALLOWED_VIDEO_MIME_TYPES:
        raise IntroVideoError(
            "That file is not a valid MP4 or MOV video.",
            400,
            {'field': 'video', 'detected_mime_type': mime},
        )

    duration, resolution, verified = _probe_duration_and_resolution(file)
    if verified and duration and duration > MAX_VIDEO_DURATION_SECONDS:
        raise IntroVideoError(
            f"Video must be {MAX_VIDEO_DURATION_SECONDS} seconds or shorter "
            f"(this one is {duration}s).",
            400,
            {'field': 'video', 'duration_seconds': duration},
        )

    return extension, size, mime, duration, resolution, verified


def _validate_metadata(title, caption):
    """Sanitise title/caption; raises IntroVideoError with per-field details."""
    errors = {}
    clean_title = sanitize_plain_text(title, allow_newlines=False)
    clean_caption = sanitize_plain_text(caption, allow_newlines=True)

    title_errors = validate_text_length(clean_title, 'Title', MAX_TITLE_CHARS)
    if title_errors:
        errors['title'] = title_errors
    caption_errors = validate_text_length(clean_caption, 'Caption', MAX_CAPTION_CHARS)
    if caption_errors:
        errors['caption'] = caption_errors

    if errors:
        raise IntroVideoError("Validation error", 400, errors)
    return clean_title, clean_caption


def _client_duration_hint(raw):
    """Accept the browser-measured duration as an unverified hint."""
    if raw in (None, ''):
        return None
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    if value <= 0 or value > 24 * 60 * 60:
        return None
    return value


def _enforce_daily_cap(merchant_id):
    since = datetime.utcnow() - timedelta(days=1)
    if MerchantIntroVideo.count_uploads_since(merchant_id, since) >= MAX_UPLOADS_PER_DAY:
        raise IntroVideoError(
            f"Upload limit reached ({MAX_UPLOADS_PER_DAY} per day). Try again later.",
            429,
        )


def _s3_service():
    from services.merchant_intro_video_s3_service import (
        get_merchant_intro_video_s3_service,
    )
    try:
        return get_merchant_intro_video_s3_service()
    except ValueError as e:
        current_app.logger.error(f"[INTRO_VIDEO] Storage not configured: {e}")
        raise IntroVideoError(
            "Video storage is not configured. Please contact support.", 500
        )
    except Exception as e:
        current_app.logger.error(f"[INTRO_VIDEO] Storage init failed: {e}", exc_info=True)
        raise IntroVideoError("Failed to initialise video storage.", 500)


class MerchantIntroVideoController:
    """All operations take the MerchantProfile row, never a client-supplied id."""

    # ---------------------------------------------------------------- #
    # Read
    # ---------------------------------------------------------------- #

    @staticmethod
    def get_for_owner(merchant_profile):
        """The merchant's own view. None (not an error) when they have no video."""
        return MerchantIntroVideo.get_active_for_merchant(merchant_profile.id)

    @staticmethod
    def get_public(merchant_profile):
        """
        The shopper-facing view: None unless both the merchant and the video
        pass their visibility rules. Callers must not distinguish "hidden"
        from "absent" in the response.
        """
        if not merchant_profile.is_public_media_visible():
            return None
        video = MerchantIntroVideo.get_active_for_merchant(merchant_profile.id)
        if video is None or not video.is_publicly_visible():
            return None
        return video

    # ---------------------------------------------------------------- #
    # Create / replace
    # ---------------------------------------------------------------- #

    @staticmethod
    def create(merchant_profile, file, title=None, caption=None, duration_hint=None):
        """
        Upload a new intro video. 409 if one already exists — replacing is an
        explicit action (see `replace_file`) so a stray POST cannot silently
        overwrite a merchant's video.
        """
        existing = MerchantIntroVideo.lock_active_for_merchant(merchant_profile.id)
        if existing is not None:
            raise IntroVideoError(
                "An intro video already exists. Replace or delete it first.", 409
            )

        _enforce_daily_cap(merchant_profile.id)
        clean_title, clean_caption = _validate_metadata(title, caption)
        extension, size, mime, duration, resolution, verified = _validate_video_file(file)
        if not verified:
            duration = _client_duration_hint(duration_hint)

        video = MerchantIntroVideo(
            merchant_id=merchant_profile.id,
            title=clean_title,
            caption=clean_caption,
            status=STATUS_PROCESSING,
            moderation_status=_moderation_default(),
            is_active=True,
        )
        db.session.add(video)
        # flush, never commit: a crash mid-upload must not leave a permanently
        # "processing" row that blocks the merchant's next attempt with a 409.
        db.session.flush()

        return MerchantIntroVideoController._upload_and_finalise(
            video, file, merchant_profile.id, extension, size, mime,
            duration, resolution, verified,
        )

    @staticmethod
    def replace_file(merchant_profile, file, title=None, caption=None, duration_hint=None):
        """
        Swap the file on the existing video, keeping metadata unless overridden.
        The new object is uploaded before the old one is deleted, so a failed
        upload leaves the merchant's current video intact.
        """
        video = MerchantIntroVideo.lock_active_for_merchant(merchant_profile.id)
        if video is None:
            raise IntroVideoError("No intro video to replace.", 404)

        _enforce_daily_cap(merchant_profile.id)
        clean_title, clean_caption = _validate_metadata(title, caption)
        extension, size, mime, duration, resolution, verified = _validate_video_file(file)
        if not verified:
            duration = _client_duration_hint(duration_hint)

        old_video_key = video.video_s3_key
        old_thumbnail_key = video.thumbnail_s3_key

        if title is not None:
            video.title = clean_title
        if caption is not None:
            video.caption = clean_caption
        video.status = STATUS_PROCESSING
        video.failure_reason = None
        # A new file is new content: it has to clear moderation again.
        video.moderation_status = _moderation_default()
        video.moderation_notes = None
        video.moderated_at = None
        video.moderated_by = None
        db.session.flush()

        result = MerchantIntroVideoController._upload_and_finalise(
            video, file, merchant_profile.id, extension, size, mime,
            duration, resolution, verified,
        )

        if old_video_key:
            try:
                _s3_service().delete_intro_video(old_video_key, old_thumbnail_key)
            except Exception as e:
                # Orphaned object; the purge job sweeps it. Never fail here —
                # the merchant's new video is already live.
                current_app.logger.warning(
                    f"[INTRO_VIDEO] Could not delete replaced objects for merchant "
                    f"{merchant_profile.id}: {e}"
                )
        return result

    @staticmethod
    def _upload_and_finalise(
        video, file, merchant_id, extension, size, mime, duration, resolution, verified
    ):
        """Push bytes to S3 and commit the row, or roll back cleanly."""
        s3 = _s3_service()
        upload = None
        try:
            upload = s3.upload_intro_video(
                file, merchant_id, video.id, file_extension=extension
            )

            video.video_url = upload['url']
            video.video_s3_key = upload['s3_key']
            video.thumbnail_url = upload.get('thumbnail_url')
            video.thumbnail_s3_key = upload.get('thumbnail_s3_key')
            video.file_size_bytes = upload.get('bytes') or size
            video.video_format = extension
            video.mime_type = mime
            video.duration_seconds = duration
            video.duration_verified = bool(verified)
            video.resolution = resolution
            video.status = STATUS_READY
            video.updated_at = datetime.utcnow()

            db.session.commit()
            current_app.logger.info(
                f"[INTRO_VIDEO] Merchant {merchant_id} intro video {video.id} ready."
            )
            return video
        except IntroVideoError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"[INTRO_VIDEO] Upload failed for merchant {merchant_id}: {e}",
                exc_info=True,
            )
            # The row was rolled back, so clean up anything that did reach S3.
            if upload:
                try:
                    s3.delete_intro_video(upload.get('s3_key'), upload.get('thumbnail_s3_key'))
                except Exception:
                    pass
            raise IntroVideoError(
                "Failed to upload the video. Please try again.", 500
            )

    # ---------------------------------------------------------------- #
    # Update / delete
    # ---------------------------------------------------------------- #

    @staticmethod
    def update_metadata(merchant_profile, title=None, caption=None, is_active=None):
        """Title/caption/visibility only — never touches the stored file."""
        video = MerchantIntroVideo.get_active_for_merchant(merchant_profile.id)
        if video is None:
            raise IntroVideoError("No intro video found.", 404)

        clean_title, clean_caption = _validate_metadata(title, caption)
        if title is not None:
            video.title = clean_title
        if caption is not None:
            video.caption = clean_caption
        if is_active is not None:
            if not isinstance(is_active, bool):
                raise IntroVideoError(
                    "Validation error", 400, {'is_active': ['Must be true or false.']}
                )
            video.is_active = is_active
        video.updated_at = datetime.utcnow()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[INTRO_VIDEO] Metadata update failed: {e}", exc_info=True)
            raise IntroVideoError("Failed to update the intro video.", 500)
        return video

    @staticmethod
    def delete(merchant_profile):
        """
        Soft delete the row, then best-effort remove the S3 objects. Row first:
        if the S3 call fails we would rather have an orphaned object than a
        video the merchant thinks they deleted still showing on their profile.
        """
        video = MerchantIntroVideo.lock_active_for_merchant(merchant_profile.id)
        if video is None:
            raise IntroVideoError("No intro video found.", 404)

        video_key = video.video_s3_key
        thumbnail_key = video.thumbnail_s3_key
        video.soft_delete()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[INTRO_VIDEO] Delete failed: {e}", exc_info=True)
            raise IntroVideoError("Failed to delete the intro video.", 500)

        if video_key:
            try:
                _s3_service().delete_intro_video(video_key, thumbnail_key)
            except Exception as e:
                current_app.logger.warning(
                    f"[INTRO_VIDEO] Row deleted but S3 cleanup failed for merchant "
                    f"{merchant_profile.id}: {e}"
                )
        return True

    # ---------------------------------------------------------------- #
    # Moderation (used only when MERCHANT_INTRO_VIDEO_MODERATION_ENABLED)
    # ---------------------------------------------------------------- #

    @staticmethod
    def moderate(video_id, approve, admin_user_id, notes=None):
        video = MerchantIntroVideo.query.filter(
            MerchantIntroVideo.id == video_id,
            MerchantIntroVideo.deleted_at.is_(None),
        ).first()
        if video is None:
            raise IntroVideoError("Intro video not found.", 404)

        clean_notes = sanitize_plain_text(notes, allow_newlines=True)
        if not approve and not clean_notes:
            raise IntroVideoError(
                "Validation error", 400, {'reason': ['A rejection reason is required.']}
            )
        note_errors = validate_text_length(clean_notes, 'Reason', 500)
        if note_errors:
            raise IntroVideoError("Validation error", 400, {'reason': note_errors})

        video.moderation_status = MODERATION_APPROVED if approve else MODERATION_REJECTED
        video.moderation_notes = clean_notes
        video.moderated_at = datetime.utcnow()
        video.moderated_by = admin_user_id

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[INTRO_VIDEO] Moderation failed: {e}", exc_info=True)
            raise IntroVideoError("Failed to update moderation status.", 500)
        return video
