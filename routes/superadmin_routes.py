from flask import Blueprint, request, jsonify
from auth.utils import super_admin_role_required

from flask_jwt_extended import get_jwt_identity

from controllers.superadmin.category_controller import CategoryController
from controllers.superadmin.attribute_controller import AttributeController
from controllers.superadmin.brand_controller import BrandController
from controllers.superadmin.brand_request_controller import BrandRequestController
from controllers.superadmin.promotion_controller import PromotionController
from controllers.superadmin.review_controller import ReviewController

admin_bp = Blueprint('admin_bp', __name__)

# ── CATEGORY ─────────────────────────────────────────────────────────────────────
@admin_bp.route('/categories', methods=['GET'])
@super_admin_role_required
def list_categories():
    cats = CategoryController.list_all()
    return jsonify([c.serialize() for c in cats]), 200

@admin_bp.route('/categories', methods=['POST'])
@super_admin_role_required
def create_category():
    data = request.get_json()
    cat = CategoryController.create(data)
    return jsonify(cat.serialize()), 201

@admin_bp.route('/categories/<int:cid>', methods=['PUT'])
@super_admin_role_required
def update_category(cid):
    data = request.get_json()
    cat = CategoryController.update(cid, data)
    return jsonify(cat.serialize()), 200

@admin_bp.route('/categories/<int:cid>', methods=['DELETE'])
@super_admin_role_required
def delete_category(cid):
    cat = CategoryController.soft_delete(cid)
    return jsonify(cat.serialize()), 200

# ── ATTRIBUTE ────────────────────────────────────────────────────────────────────
@admin_bp.route('/attributes', methods=['GET'])
@super_admin_role_required
def list_attributes():
    attrs = AttributeController.list_all()
    return jsonify([a.serialize() for a in attrs]), 200

@admin_bp.route('/attributes', methods=['POST'])
@super_admin_role_required
def create_attribute():
    data = request.get_json()
    a = AttributeController.create(data)
    return jsonify(a.serialize()), 201

@admin_bp.route('/attributes/<int:aid>', methods=['PUT'])
@super_admin_role_required
def update_attribute(aid):
    data = request.get_json()
    a = AttributeController.update(aid, data)
    return jsonify(a.serialize()), 200

@admin_bp.route('/attributes/<int:aid>', methods=['DELETE'])
@super_admin_role_required
def delete_attribute(aid):
    AttributeController.delete(aid)
    return '', 204

# ── BRAND REQUESTS ────────────────────────────────────────────────────────────────
@admin_bp.route('/brand-requests', methods=['GET'])
@super_admin_role_required
def list_brand_requests():
    reqs = BrandRequestController.list_pending()
    return jsonify([r.serialize() for r in reqs]), 200

@admin_bp.route('/brand-requests/<int:rid>/approve', methods=['POST'])
@super_admin_role_required
def approve_brand_request(rid):
    user_id = get_jwt_identity()
    br = BrandRequestController.approve(rid, user_id)
    return jsonify(br.serialize()), 200

@admin_bp.route('/brand-requests/<int:rid>/reject', methods=['POST'])
@super_admin_role_required
def reject_brand_request(rid):
    user_id = get_jwt_identity()
    notes = request.get_json().get('notes')
    br = BrandRequestController.reject(rid, user_id, notes)
    return jsonify(br.serialize()), 200

# ── BRANDS ────────────────────────────────────────────────────────────────────────
@admin_bp.route('/brands', methods=['GET'])
@super_admin_role_required
def list_brands():
    bs = BrandController.list_all()
    return jsonify([b.serialize() for b in bs]), 200

@admin_bp.route('/brands/<int:bid>', methods=['DELETE'])
@super_admin_role_required
def delete_brand(bid):
    b = BrandController.delete(bid)
    return jsonify(b.serialize()), 200

# ── PROMOTIONS ────────────────────────────────────────────────────────────────────
@admin_bp.route('/promotions', methods=['GET'])
@super_admin_role_required
def list_promotions():
    ps = PromotionController.list_all()
    return jsonify([p.serialize() for p in ps]), 200

@admin_bp.route('/promotions', methods=['POST'])
@super_admin_role_required
def create_promotion():
    data = request.get_json()
    p = PromotionController.create(data)
    return jsonify(p.serialize()), 201

@admin_bp.route('/promotions/<int:pid>', methods=['PUT'])
@super_admin_role_required
def update_promotion(pid):
    data = request.get_json()
    p = PromotionController.update(pid, data)
    return jsonify(p.serialize()), 200

@admin_bp.route('/promotions/<int:pid>', methods=['DELETE'])
@super_admin_role_required
def delete_promotion(pid):
    p = PromotionController.soft_delete(pid)
    return jsonify(p.serialize()), 200

# ── REVIEWS ──────────────────────────────────────────────────────────────────────
@admin_bp.route('/reviews', methods=['GET'])
@super_admin_role_required
def list_reviews():
    rs = ReviewController.list_recent()
    return jsonify([r.serialize() for r in rs]), 200

@admin_bp.route('/reviews/<int:rid>', methods=['DELETE'])
@super_admin_role_required
def delete_review(rid):
    r = ReviewController.delete(rid)
    return jsonify(r.serialize()), 200
