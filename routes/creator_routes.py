"""
Creator module routes: onboarding (categories + availability) and future creator-only endpoints.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError

from auth.controllers import creator_onboarding
from auth.utils import creator_role_required


class CreatorOnboardingSchema(Schema):
    category_ids = fields.List(fields.Int(), required=True, validate=validate.Length(min=5))
    availability = fields.Str(required=True, validate=validate.OneOf(["available", "busy"]))
    language_preferences = fields.Str(load_default=None, allow_none=True)
    portfolio_links = fields.List(fields.Str(), load_default=None, allow_none=True)


creator_bp = Blueprint("creator", __name__)


@creator_bp.route("/onboarding", methods=["POST"])
@jwt_required()
@creator_role_required
def onboarding():
    """
    Complete creator onboarding: save at least 5 categories and availability.
    Call after OTP verification; requires Creator JWT.
    """
    try:
        schema = CreatorOnboardingSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({
            "error": "Validation failed.",
            "code": "VALIDATION_ERROR",
            "details": e.messages
        }), 400

    user_id = get_jwt_identity()
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid token.", "code": "UNAUTHORIZED"}), 401

    response, status_code = creator_onboarding(
        user_id=user_id,
        category_ids=data["category_ids"],
        availability=data["availability"],
        language_preferences=data.get("language_preferences"),
        portfolio_links=data.get("portfolio_links"),
    )
    return jsonify(response), status_code
