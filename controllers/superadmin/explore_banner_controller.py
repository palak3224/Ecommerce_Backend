import os
from collections import defaultdict
from models.explore_banner import ExploreBannerItem
from common.database import db
from services.s3_service import get_s3_service
from flask import current_app
from datetime import datetime
from PIL import Image

# --- Explore banner image specification ---
BANNER_ALLOWED_EXTS = {'jpg', 'jpeg', 'png', 'webp'}
BANNER_ALLOWED_MIMES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
BANNER_MAX_BYTES = 5 * 1024 * 1024      # 5 MB
BANNER_TARGET_W = 1200
BANNER_TARGET_H = 600
BANNER_ASPECT = 2.0                     # 2:1
BANNER_ASPECT_TOLERANCE = 0.02          # ~1 px on a 1200x600 image


class BannerValidationError(ValueError):
    """Raised when an uploaded banner image violates the required spec."""


class BannerDeleteError(ValueError):
    """Raised when deleting an item would violate the minimum-items-per-group rule."""


def validate_banner_image(image_file):
    """
    Enforce the explore-banner image spec: JPG/PNG/WebP, <= 5 MB, 2:1 aspect
    ratio, and at least 1200x600 px. Raises ValueError on any violation.
    Leaves the file pointer reset to the start for the subsequent upload.
    """
    filename = getattr(image_file, 'filename', '') or ''
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    mime = (getattr(image_file, 'mimetype', '') or getattr(image_file, 'content_type', '') or '').lower()
    if ext not in BANNER_ALLOWED_EXTS and mime not in BANNER_ALLOWED_MIMES:
        raise BannerValidationError('Banner image must be a JPG, PNG or WebP file.')

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
        raise BannerValidationError('Could not read the image file. Please upload a valid JPG, PNG or WebP.')
    finally:
        try:
            image_file.seek(0)
        except (IOError, OSError):
            pass

    if width < BANNER_TARGET_W or height < BANNER_TARGET_H:
        raise BannerValidationError(f'Banner image must be at least {BANNER_TARGET_W}×{BANNER_TARGET_H} px.')
    if abs((width / height) - BANNER_ASPECT) > BANNER_ASPECT_TOLERANCE:
        raise BannerValidationError('Banner image must have a 2:1 aspect ratio (e.g. 1200×600 px).')


class ExploreBannerItemController:
    """Business logic for Explore-screen banner items (Superadmin)."""

    @staticmethod
    def _base_query():
        """Non-deleted banner items."""
        return ExploreBannerItem.query.filter_by(deleted_at=None)

    @staticmethod
    def list_all_grouped():
        """All non-deleted items, grouped by `group_key` (for the admin panel)."""
        items = ExploreBannerItemController._base_query().order_by(
            ExploreBannerItem.group_key, 
            ExploreBannerItem.display_order
        ).all()
        grouped = defaultdict(list)
        for item in items:
            grouped[item.group_key].append(item)
        return grouped

    @staticmethod
    def list_active_grouped():
        """Active, non-deleted items, grouped by `group_key` (for the mobile app)."""
        items = (
            ExploreBannerItem.query
            .filter_by(deleted_at=None, is_active=True)  # FIX: Added deleted_at filter
            .order_by(ExploreBannerItem.group_key, ExploreBannerItem.display_order)
            .all()
        )
        grouped = defaultdict(list)
        for item in items:
            grouped[item.group_key].append(item)
        return grouped

    @staticmethod
    def get(item_id):
        return ExploreBannerItemController._base_query().filter_by(id=item_id).first()

    @staticmethod
    def _upload_image(image_file):
        """Upload an image to S3 and return its public URL. Raises on failure."""
        if not hasattr(image_file, 'filename') or not image_file.filename:
            raise Exception("Invalid file object: missing filename")

        validate_banner_image(image_file)

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
        """Create a new explore banner item."""
        group_key = data.get('group_key')
        if not group_key or group_key not in ExploreBannerItem.BANNER_GROUPS:
            raise ValueError(f"Invalid or missing group_key. Must be one of {ExploreBannerItem.BANNER_GROUPS}.")

        existing_count = ExploreBannerItemController._base_query().filter_by(group_key=group_key).count()
        if existing_count >= ExploreBannerItem.MAX_ITEMS_PER_GROUP:
            raise ValueError(
                f"Maximum of {ExploreBannerItem.MAX_ITEMS_PER_GROUP} items allowed for the '{group_key}' banner group."
            )

        image_url = data.get('image_url')
        if image_file:
            image_url = ExploreBannerItemController._upload_image(image_file)

        if not image_url:
            raise ValueError("Banner image is required.")

        display_order = data.get('display_order')
        if display_order is None:
            display_order = existing_count

        # FIX: Allow empty strings for title, cta_text, cta_path
        banner_item = ExploreBannerItem(
            group_key=group_key,
            image_url=image_url,
            title=data.get('title', ''),
            cta_text=data.get('cta_text', ''),
            cta_path=data.get('cta_path', ''),
            display_order=display_order,
            is_active=data.get('is_active', True),
        )
        try:
            db.session.add(banner_item)
            db.session.commit()
            return banner_item
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create explore banner item: {e}", exc_info=True)
            raise

    @staticmethod
    def update(item_id, data, image_file=None):
        """Update an explore banner item."""
        banner_item = ExploreBannerItemController.get(item_id)
        if not banner_item:
            raise ValueError("Explore banner item not found.")

        if image_file:
            banner_item.image_url = ExploreBannerItemController._upload_image(image_file)
        elif data.get('image_url'):
            banner_item.image_url = data['image_url']

        # group_key cannot be changed on update.
        # FIX: Allow empty strings for title, cta_text, cta_path
        for field in ('title', 'cta_text', 'cta_path', 'display_order', 'is_active'):
            if field in data:
                setattr(banner_item, field, data[field])

        try:
            db.session.commit()
            return banner_item
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update explore banner item {item_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def delete(item_id):
        """
        Soft-delete a banner item. Allows deletion of all items in a group.
        """
        banner_item = ExploreBannerItemController.get(item_id)
        if not banner_item:
            raise ValueError("Explore banner item not found.")

        # FIX: Allow deletion of all items - removed the guard completely
        # The frontend already has validation, and groups can have 0 items
        
        banner_item.deleted_at = datetime.utcnow()
        try:
            db.session.commit()
            return banner_item
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to delete explore banner item {item_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def reorder(group_key, ordered_ids):
        """
        Set the carousel order for a specific group from a list of item ids.
        """
        if not group_key or group_key not in ExploreBannerItem.BANNER_GROUPS:
            raise ValueError(f"Invalid or missing group_key. Must be one of {ExploreBannerItem.BANNER_GROUPS}.")
        if not isinstance(ordered_ids, list):
            raise ValueError("A list of banner item ids is required.")

        items_in_group = {
            b.id: b for b in ExploreBannerItemController._base_query().filter_by(group_key=group_key).all()
        }
        
        if len(ordered_ids) != len(items_in_group):
            raise ValueError("The provided list of IDs does not match the number of items in the group.")

        unknown = [bid for bid in ordered_ids if bid not in items_in_group]
        if unknown:
            raise ValueError(f"Unknown banner item id(s) for this group: {unknown}.")

        for index, bid in enumerate(ordered_ids):
            items_in_group[bid].display_order = index
        try:
            db.session.commit()
            return list(items_in_group.values())
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to reorder explore banner items for group {group_key}: {e}", exc_info=True)
            raise