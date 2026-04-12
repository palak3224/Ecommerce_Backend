"""Merchant account deletion API (same URL prefix as merchant dashboard)."""
from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from flask_jwt_extended import get_jwt_identity, jwt_required

from auth.utils import merchant_role_required
from services.merchant_account_deletion_service import (
    cancel_deletion,
    deletion_status_for_user,
    request_deletion,
)

merchant_account_deletion_bp = Blueprint("merchant_account_deletion_bp", __name__)


@merchant_account_deletion_bp.route("/account/deletion-status", methods=["GET", "OPTIONS"])
@cross_origin()
@jwt_required()
@merchant_role_required
def merchant_deletion_status():
    if request.method == "OPTIONS":
        return "", 204
    body, code = deletion_status_for_user(get_jwt_identity())
    return jsonify(body), code


@merchant_account_deletion_bp.route("/account/deletion-request", methods=["POST", "OPTIONS"])
@cross_origin()
@jwt_required()
@merchant_role_required
def merchant_deletion_request():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    body, code = request_deletion(get_jwt_identity(), password=password)
    return jsonify(body), code


@merchant_account_deletion_bp.route("/account/deletion-cancel", methods=["POST", "OPTIONS"])
@cross_origin()
@jwt_required()
@merchant_role_required
def merchant_deletion_cancel():
    if request.method == "OPTIONS":
        return "", 204
    body, code = cancel_deletion(get_jwt_identity())
    return jsonify(body), code
