from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from http import HTTPStatus

from auth.utils import super_admin_role_required
from controllers.superadmin.explore_banner_controller import (
    ExploreBannerController,
    BannerValidationError,
)
from models.explore_banner import ExploreBanner

explore_banner_bp = Blueprint('explore_banner', __name__)


def _parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def _extract_payload():
    """
    Read banner fields from either multipart/form-data (with an optional
    `image` file) or a JSON body.
    Returns (data_dict, image_file).
    """
    image_file = request.files.get('image') if request.files else None
    if request.content_type and 'application/json' in request.content_type and not image_file:
        body = request.get_json(silent=True) or {}
        data = {
            'slot': body.get('slot'),
            'title': body.get('title'),
            'cta_text': body.get('cta_text'),
            'cta_path': body.get('cta_path'),
            'image_url': body.get('image_url'),
            'display_order': body.get('display_order'),
            'is_active': body.get('is_active'),
        }
    else:
        form = request.form
        data = {
            'slot': form.get('slot'),
            'title': form.get('title'),
            'cta_text': form.get('cta_text'),
            'cta_path': form.get('cta_path'),
            'image_url': form.get('image_url'),
            'display_order': int(form['display_order']) if form.get('display_order') not in (None, '') else None,
            'is_active': _parse_bool(form.get('is_active')) if form.get('is_active') is not None else None,
        }
    return data, image_file


# ---------------------------------------------------------------------------
# PUBLIC — consumed by the mobile app's Explore screen
# ---------------------------------------------------------------------------
@explore_banner_bp.route('/api/explore-banners', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_public_explore_banners():
    """Return active explore banners for the mobile app."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        banners = ExploreBannerController.list_active()
        return jsonify([b.serialize() for b in banners]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error fetching explore banners: {e}", exc_info=True)
        return jsonify({'message': 'Failed to fetch explore banners.', 'error': str(e)}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# SUPERADMIN — CRUD
# ---------------------------------------------------------------------------
@explore_banner_bp.route('/api/superadmin/explore-banners', methods=['GET', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def list_explore_banners():
    """List all explore banners (admin)."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        banners = ExploreBannerController.list_all()
        return jsonify({
            'banners': [b.serialize() for b in banners],
            'max_banners': ExploreBanner.MAX_BANNERS,
        }), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing explore banners: {e}", exc_info=True)
        return jsonify({'message': f'Failed to list explore banners: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners', methods=['POST', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def create_explore_banner():
    """Create an explore banner (admin). Accepts multipart/form-data or JSON."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data, image_file = _extract_payload()

        missing = [f for f in ('title', 'cta_text', 'cta_path') if not (data.get(f) or '').strip()]
        if missing:
            return jsonify({'message': f"Missing required field(s): {', '.join(missing)}."}), \
                HTTPStatus.BAD_REQUEST
        if not image_file and not data.get('image_url'):
            return jsonify({'message': 'Banner image is required.'}), HTTPStatus.BAD_REQUEST

        banner = ExploreBannerController.create(data, image_file=image_file)
        return jsonify(banner.serialize()), HTTPStatus.CREATED
    except BannerValidationError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        current_app.logger.error(f"Error creating explore banner: {e}", exc_info=True)
        return jsonify({'message': f'Failed to create explore banner: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners/<int:banner_id>', methods=['PUT', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def update_explore_banner(banner_id):
    """Update an explore banner (admin). Accepts multipart/form-data or JSON."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data, image_file = _extract_payload()
        banner = ExploreBannerController.update(banner_id, data, image_file=image_file)
        return jsonify(banner.serialize()), HTTPStatus.OK
    except BannerValidationError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except Exception as e:
        current_app.logger.error(f"Error updating explore banner {banner_id}: {e}", exc_info=True)
        return jsonify({'message': f'Failed to update explore banner: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners/<int:banner_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def delete_explore_banner(banner_id):
    """Delete an explore banner (admin)."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        banner = ExploreBannerController.delete(banner_id)
        return jsonify({'message': 'Explore banner deleted successfully', 'id': banner.id}), HTTPStatus.OK
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except Exception as e:
        current_app.logger.error(f"Error deleting explore banner {banner_id}: {e}", exc_info=True)
        return jsonify({'message': f'Failed to delete explore banner: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR
