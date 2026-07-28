import os
from models.explore_banner import ExploreBanner
from common.database import db
from services.s3_service import get_s3_service
from flask import current_app
from datetime import datetime
from PIL import Image

# --- Explore banner image specification ---
BANNER_ALLOWED_EXTS = {'jpg', 'jpeg', 'webp'}
BANNER_ALLOWED_MIMES = {'image/jpeg', 'image/jpg', 'image/webp'}
BANNER_MAX_BYTES = 5 * 1024 * 1024      # 5 MB
BANNER_TARGET_W = 1200
BANNER_TARGET_H = 600
BANNER_ASPECT = 2.0                     # 2:1
BANNER_ASPECT_TOLERANCE = 0.02          # ~1 px on a 1200x600 image


class BannerValidationError(ValueError):
    """Raised when an uploaded banner image violates the required spec."""


def validate_banner_image(image_file):
    """
    Enforce the explore-banner image spec: JPG/WebP, <= 5 MB, 2:1 aspect
    ratio, and at least 1200x600 px. Raises ValueError on any violation.
    Leaves the file pointer reset to the start for the subsequent upload.
    """
    filename = getattr(image_file, 'filename', '') or ''
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    mime = (getattr(image_file, 'mimetype', '') or getattr(image_file, 'content_type', '') or '').lower()
    if ext not in BANNER_ALLOWED_EXTS and mime not in BANNER_ALLOWED_MIMES:
        raise BannerValidationError('Banner image must be a JPG or WebP file.')

    # File size
    size = None
    try:
        image_file.seek(0, os.SEEK_END)
        size = image_file.tell()
        image_file.seek(0)
    except (IOError, OSError):
        pass
    if size is not None and size > BANNER_MAX_BYTES:
        raise BannerValidationError('Banner image must be 5 MB or smaller.')

    # Dimensions / aspect ratio
    try:
        img = Image.open(image_file)
        width, height = img.size
    except Exception:
        raise BannerValidationError('Could not read the image file. Please upload a valid JPG or WebP.')
    finally:
        try:
            image_file.seek(0)
        except (IOError, OSError):
            pass

    if width < BANNER_TARGET_W or height < BANNER_TARGET_H:
        raise BannerValidationError(f'Banner image must be at least {BANNER_TARGET_W}×{BANNER_TARGET_H} px.')
    if abs((width / height) - BANNER_ASPECT) > BANNER_ASPECT_TOLERANCE:
        raise BannerValidationError('Banner image must have a 2:1 aspect ratio (e.g. 1200×600 px).')


class ExploreBannerController:
    """Business logic for Explore-screen banners (Superadmin)."""

    @staticmethod
    def _base_query():
        """Non-deleted banners."""
        return ExploreBanner.query.filter_by(deleted_at=None)

    @staticmethod
    def list_all():
        """All non-deleted banners ordered by display_order (for the admin panel)."""
        return ExploreBannerController._base_query().order_by(ExploreBanner.display_order).all()

    @staticmethod
    def list_active():
        """Active, non-deleted banners ordered by display_order (for the mobile app)."""
        return (
            ExploreBannerController._base_query()
            .filter_by(is_active=True)
            .order_by(ExploreBanner.display_order)
            .all()
        )

    @staticmethod
    def get(banner_id):
        return ExploreBannerController._base_query().filter_by(id=banner_id).first()

    @staticmethod
    def _upload_image(image_file):
        """Upload an image to S3 and return its public URL. Raises on failure."""
        if not hasattr(image_file, 'filename') or not image_file.filename:
            raise Exception("Invalid file object: missing filename")

        # Enforce the banner image spec (format / size / dimensions) before upload.
        validate_banner_image(image_file)

        # Reset pointer to start if needed.
        if hasattr(image_file, 'seek') and hasattr(image_file, 'tell'):
            try:
                if image_file.tell() != 0:
                    image_file.seek(0)
            except (IOError, OSError):
                pass

        s3_service = get_s3_service()
        if not s3_service:
            raise Exception("S3 service failed to initialize")

        result = s3_service.upload_explore_banner_image(image_file)
        if not result or not result.get('url'):
            raise Exception("S3 upload returned no URL")
        return result.get('url')

    @staticmethod
    def create(data, image_file=None):
        """
        Create a new explore banner.

        Enforces the MAX_BANNERS limit. Requires either an uploaded image
        file or an image_url in `data`.
        """
        existing = ExploreBannerController._base_query().all()
        if len(existing) >= ExploreBanner.MAX_BANNERS:
            raise ValueError(
                f"Maximum of {ExploreBanner.MAX_BANNERS} explore banners allowed."
            )

        # Resolve the named slot (hero / spotlight / category).
        used_slots = {b.slot for b in existing}
        slot = data.get('slot')
        if slot:
            if slot not in ExploreBanner.SLOTS:
                raise ValueError(
                    f"slot must be one of: {', '.join(ExploreBanner.SLOTS)}."
                )
            if slot in used_slots:
                raise ValueError(
                    f"The {ExploreBanner.SLOT_LABELS[slot]} slot is already in use."
                )
        else:
            # Fall back to the first free slot in canonical order.
            slot = next((s for s in ExploreBanner.SLOTS if s not in used_slots), None)
            if slot is None:
                raise ValueError("No free explore banner slot available.")

        image_url = data.get('image_url')
        if image_file:
            image_url = ExploreBannerController._upload_image(image_file)

        if not image_url:
            raise ValueError("Banner image is required.")

        banner = ExploreBanner(
            slot=slot,
            image_url=image_url,
            title=data['title'],
            cta_text=data['cta_text'],
            cta_path=data['cta_path'],
            display_order=ExploreBanner.SLOTS.index(slot),
            is_active=data.get('is_active', True),
        )
        try:
            db.session.add(banner)
            db.session.commit()
            return banner
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create explore banner: {e}", exc_info=True)
            raise

    @staticmethod
    def update(banner_id, data, image_file=None):
        banner = ExploreBannerController.get(banner_id)
        if not banner:
            raise ValueError("Explore banner not found.")

        if image_file:
            banner.image_url = ExploreBannerController._upload_image(image_file)
        elif data.get('image_url'):
            banner.image_url = data['image_url']

        for field in ('title', 'cta_text', 'cta_path', 'display_order', 'is_active'):
            if field in data and data[field] is not None:
                setattr(banner, field, data[field])

        try:
            db.session.commit()
            return banner
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update explore banner {banner_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def delete(banner_id):
        """Soft-delete a banner."""
        banner = ExploreBannerController.get(banner_id)
        if not banner:
            raise ValueError("Explore banner not found.")
        banner.deleted_at = datetime.utcnow()
        try:
            db.session.commit()
            return banner
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to delete explore banner {banner_id}: {e}", exc_info=True)
            raise
