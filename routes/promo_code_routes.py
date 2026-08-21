# FILE: routes/promo_code_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from http import HTTPStatus
from decimal import Decimal

from auth.models.models import User
from common.database import db
from services.checkout_quote_service import QuoteError, price_basket
from services.promotion_service import resolve_promotion

promo_code_bp = Blueprint('promo_code_bp', __name__, url_prefix='/api/promo-code')

@promo_code_bp.route('/apply', methods=['POST'])
@jwt_required()
def apply_promo_code():
    """
    Validates a promotion code and returns the discount details.
    Receives the promotion code and the list of cart items.
    ---
    tags:
      - Promotions
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - promo_code
              - cart_items
            properties:
              promo_code:
                type: string
                description: The promotion code entered by the user.
              cart_items:
                type: array
                description: "A list of items currently in the user's cart."
                items:
                  type: object
                  properties:
                    product_id:
                      type: integer
                    quantity:
                      type: integer
                    price:
                      type: number
    responses:
      200:
        description: Promotion applied successfully.
        schema:
          type: object
          properties:
            message:
              type: string
            discount_amount:
              type: number
            promotion_id:
              type: integer
            new_total:
              type: number
      400:
        description: Invalid request or promotion cannot be applied.
        schema:
          type: object
          properties:
            error:
              type: string
      404:
        description: Promotion code not found.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    data = request.get_json()
    if not data or not data.get('promo_code') or not isinstance(data.get('cart_items'), list):
        return jsonify({'error': 'Promo code and cart items are required.'}), HTTPStatus.BAD_REQUEST

    promo_code = data['promo_code']
    cart_items = data['cart_items']
    if not cart_items:
        return jsonify({'error': 'Cart is empty.'}), HTTPStatus.BAD_REQUEST

    user_id = get_jwt_identity()

    # Delegate to the same pricer the checkout quote uses, rather than re-implementing
    # the discount rules here.
    #
    # This endpoint used to compute discounts from the `price` the browser sent, in
    # float arithmetic with round() — while the quote read prices from the database in
    # Decimal with ROUND_HALF_UP. Two implementations of "what is this code worth" that
    # were required to agree and did not: the customer could be shown one number on the
    # cart page and charged against another. Worse, a min_order_value judged against a
    # client-supplied price is not a rule at all, since the browser can claim any total
    # it likes.
    #
    # Quantities and product ids still come from the request; every amount comes from
    # the database.
    try:
        totals, lines = price_basket(user_id, {
            'items': [
                {'product_id': i.get('product_id'), 'quantity': i.get('quantity')}
                for i in cart_items
            ],
            'promo_code': promo_code,
        })
    except QuoteError as e:
        # Out of stock, product withdrawn, basket unpriceable, or a promo rejected for
        # a reason the customer can act on (below the minimum, already used).
        return jsonify({'error': str(e)}), HTTPStatus.BAD_REQUEST

    # price_basket silently grants no discount for an unknown/expired/inactive code, so
    # ask the validator directly for the reason to report. Same rules, same module.
    if not totals.get('promotion_id'):
        basket_total = sum(
            Decimal(l['original_listed_inclusive_price_per_unit']) * l['quantity']
            for l in lines
        )
        resolution = resolve_promotion(
            promo_code,
            user=User.query.get(user_id),
            basket_total_inclusive=basket_total,
        )
        return (
            jsonify({'error': resolution.message or 'Invalid promotion code.'}),
            resolution.http_status or HTTPStatus.BAD_REQUEST,
        )

    item_discounts = {
        l['product_id']: float(
            Decimal(l['discount_amount_per_unit_applied']) * l['quantity']
        )
        for l in lines
    }
    new_total = float(sum(Decimal(l['line_item_total_inclusive_gst']) for l in lines))

    return jsonify({
        'message': 'Promotion applied successfully!',
        'discount_amount': float(totals['discount_amount']),
        'new_total': round(new_total, 2),
        'promotion_id': totals['promotion_id'],
        'item_discounts': item_discounts,
    }), HTTPStatus.OK
