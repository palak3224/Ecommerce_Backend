# routes/checkout_routes.py
"""Checkout quoting.

`POST /api/checkout/quote` is the only way a browser learns what its basket costs
for payment purposes. It takes intent (products, quantities, a promo code) and
returns money the server computed, addressed by an opaque quote id.

The browser never sends an amount again after this point — it sends the quote id.
"""
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from common.response import success_response, error_response
from common.database import db
from services.checkout_quote_service import (
    QuoteError,
    build_quote,
    load_spendable_quote,
)

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/api/checkout/quote", methods=["POST"])
@jwt_required()
def create_checkout_quote():
    """Price the caller's basket and return a spendable quote."""
    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}

    # Any amount the caller sent is ignored, but say so out loud: a client still
    # sending totals is a frontend that has not finished migrating.
    for stale_key in ("amount", "amount_major", "amount_minor", "total_amount",
                      "shipping_amount", "item_discount_inclusive"):
        if stale_key in payload:
            current_app.logger.info(
                "checkout/quote: ignoring client-supplied '%s' (server prices the basket)",
                stale_key,
            )

    try:
        quote = build_quote(user_id, payload)
    except QuoteError as e:
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Failed to build checkout quote: %s", e, exc_info=True)
        return error_response("Could not price your basket. Please try again.", 500)

    return success_response("Quote created", quote.serialize(), 201)


@checkout_bp.route("/api/checkout/quote/<quote_id>", methods=["GET"])
@jwt_required()
def get_checkout_quote(quote_id):
    """Re-read a quote — used to show the customer what they are about to pay."""
    user_id = get_jwt_identity()
    try:
        quote = load_spendable_quote(quote_id, user_id)
    except QuoteError as e:
        return error_response(str(e), 400)
    return success_response("Quote retrieved", quote.serialize())
