from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from http import HTTPStatus

from auth.utils import super_admin_role_required
from controllers.superadmin.explore_banner_controller import (
    ExploreBannerItemController,
    BannerValidationError,
)
from models.explore_banner import ExploreBannerItem

explore_banner_bp = Blueprint('explore_banner', __name__)


def _parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def _extract_payload():
    """
    Read banner item fields from either multipart/form-data (with an optional
    `image` file) or a JSON body.
    Returns (data_dict, image_file).
    """
    image_file = request.files.get('image') if request.files else None
    if request.content_type and 'application/json' in request.content_type and not image_file:
        body = request.get_json(silent=True) or {}
        data = {
            'group_key': body.get('group_key'),
            'title': body.get('title', ''),  # FIX: Default to empty string
            'cta_text': body.get('cta_text', ''),
            'cta_path': body.get('cta_path', ''),
            'image_url': body.get('image_url'),
            'display_order': body.get('display_order'),
            'is_active': body.get('is_active'),
        }
    else:
        form = request.form
        data = {
            'group_key': form.get('group_key'),
            'title': form.get('title', ''),  # FIX: Default to empty string
            'cta_text': form.get('cta_text', ''),
            'cta_path': form.get('cta_path', ''),
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
    """Return active explore banner items, grouped by type, for the mobile app."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        grouped_items = ExploreBannerItemController.list_active_grouped()
        serialized_groups = {
            group: [item.serialize() for item in items]
            for group, items in grouped_items.items()
        }
        return jsonify(serialized_groups), HTTPStatus.OK
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
def list_explore_banner_items():
    """List all explore banner items (admin), grouped by type."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        grouped_items = ExploreBannerItemController.list_all_grouped()
        serialized_groups = {
            group: [item.serialize() for item in items]
            for group, items in grouped_items.items()
        }
        return jsonify({
            'banner_groups': serialized_groups,
            'group_keys': ExploreBannerItem.BANNER_GROUPS,
            'max_items_per_group': ExploreBannerItem.MAX_ITEMS_PER_GROUP,
        }), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing explore banner items: {e}", exc_info=True)
        return jsonify({'message': f'Failed to list explore banner items: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners/groups/<group_key>/order', methods=['PUT', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def reorder_explore_banner_items(group_key):
    """Set the carousel order for a specific group. Body: { "order": [id, id, id] }."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True) or {}
        order = body.get('order')
        items = ExploreBannerItemController.reorder(group_key, order)
        return jsonify({'items': [item.serialize() for item in items]}), HTTPStatus.OK
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        current_app.logger.error(f"Error reordering explore banner items: {e}", exc_info=True)
        return jsonify({'message': f'Failed to reorder explore banner items: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners', methods=['POST', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def create_explore_banner_item():
    """Create an explore banner item (admin). Accepts multipart/form-data or JSON."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data, image_file = _extract_payload()

        # FIX: Only validate group_key and image - title, cta_text, cta_path are optional
        if not (data.get('group_key') or '').strip():
            return jsonify({'message': "Missing required field: group_key."}), \
                HTTPStatus.BAD_REQUEST
        if not image_file and not data.get('image_url'):
            return jsonify({'message': 'Banner image is required.'}), HTTPStatus.BAD_REQUEST

        banner_item = ExploreBannerItemController.create(data, image_file=image_file)
        return jsonify(banner_item.serialize()), HTTPStatus.CREATED
    except BannerValidationError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        current_app.logger.error(f"Error creating explore banner item: {e}", exc_info=True)
        return jsonify({'message': f'Failed to create explore banner item: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners/<int:item_id>', methods=['PUT', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def update_explore_banner_item(item_id):
    """Update an explore banner item (admin). Accepts multipart/form-data or JSON."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data, image_file = _extract_payload()
        banner_item = ExploreBannerItemController.update(item_id, data, image_file=image_file)
        return jsonify(banner_item.serialize()), HTTPStatus.OK
    except BannerValidationError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except Exception as e:
        current_app.logger.error(f"Error updating explore banner item {item_id}: {e}", exc_info=True)
        return jsonify({'message': f'Failed to update explore banner item: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR


@explore_banner_bp.route('/api/superadmin/explore-banners/<int:item_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@super_admin_role_required
def delete_explore_banner_item(item_id):
    """Delete an explore banner item (admin)."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        banner_item = ExploreBannerItemController.delete(item_id)
        return jsonify({'message': 'Explore banner item deleted successfully', 'id': banner_item.id}), HTTPStatus.OK
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except Exception as e:
        current_app.logger.error(f"Error deleting explore banner item {item_id}: {e}", exc_info=True)
        return jsonify({'message': f'Failed to delete explore banner item: {str(e)}'}), \
            HTTPStatus.INTERNAL_SERVER_ERROR