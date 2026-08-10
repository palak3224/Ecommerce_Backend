from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from common.response import success_response, error_response
from common.database import db
import razorpay
import os
import hmac
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from models.checkout_quote import CheckoutQuote
from models.payment_refund import PaymentRefund, RefundStatus
from models.subscription import SubscriptionPlan
# checkout_quote_service imports minor_unit_factor from this module, but only inside a
# function body, so this direction is safe to do at module scope.
from services.checkout_quote_service import (
    QuoteError,
    consume_quote,
    load_spendable_quote,
    minor_units,
)

razorpay_bp = Blueprint('razorpay', __name__)

DEFAULT_CHARGE_CURRENCY = 'INR'

# Minor units per currency. Most are 2 (100 paise/cents), a few differ.
ZERO_DECIMAL_CURRENCIES = {'JPY', 'KRW', 'VND', 'CLP'}
THREE_DECIMAL_CURRENCIES = {'BHD', 'JOD', 'KWD', 'OMR', 'TND'}


def minor_unit_factor(currency):
    """How many minor units make one major unit of `currency`."""
    currency = (currency or DEFAULT_CHARGE_CURRENCY).upper()
    if currency in ZERO_DECIMAL_CURRENCIES:
        return 1
    if currency in THREE_DECIMAL_CURRENCIES:
        return 1000
    return 100


def _resolve_amount_minor(data, currency):
    """Resolve the request amount to an integer number of minor units.

    The caller must say which unit it is sending — we never guess. The previous
    implementation inspected the magnitude ("if the value is an integer below 1000
    it is probably rupees"), which silently multiplied any genuine sub-1000-paise
    amount by 100: a Rs 9.99 subscription sent as 999 paise was charged as Rs 999.

    Accepted keys, in precedence order:
      amount_minor  - integer minor units (paise/cents)          [preferred]
      amount_major  - decimal major units (rupees/dollars)       [preferred]
      amount        - LEGACY, minor units (business/Subscription.tsx sends paise)
      amount_rupees - LEGACY, major units (PaymentPage.tsx sends rupees)

    Raises ValueError with a user-facing message on bad input.
    """
    factor = minor_unit_factor(currency)

    def as_minor_from_major(value, key):
        try:
            # Decimal, not float: float('1234.565') * 100 lands on 123456.49999...
            major = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f'Invalid {key}: expected a number.')
        return int((major * factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    def as_minor_direct(value, key):
        try:
            minor = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f'Invalid {key}: expected an integer number of minor units.')
        if minor != minor.to_integral_value():
            raise ValueError(f'Invalid {key}: minor units must be a whole number.')
        return int(minor)

    if data.get('amount_minor') is not None:
        return as_minor_direct(data['amount_minor'], 'amount_minor')
    if data.get('amount_major') is not None:
        return as_minor_from_major(data['amount_major'], 'amount_major')

    if data.get('amount') is not None:
        current_app.logger.info(
            "razorpay create-order: deprecated 'amount' key (assuming minor units); "
            "send 'amount_minor' instead"
        )
        return as_minor_direct(data['amount'], 'amount')
    if data.get('amount_rupees') is not None:
        current_app.logger.info(
            "razorpay create-order: deprecated 'amount_rupees' key; send 'amount_major' instead"
        )
        return as_minor_from_major(data['amount_rupees'], 'amount_rupees')

    raise ValueError('Amount is required.')


# Initialize Razorpay client
def get_razorpay_client():
    return razorpay.Client(
        auth=(current_app.config.get('RAZORPAY_KEY_ID'),
              current_app.config.get('RAZORPAY_KEY_SECRET'))
    )

@razorpay_bp.route('/api/razorpay/create-order', methods=['POST'])
@jwt_required()
def create_razorpay_order():
    """Create a Razorpay order"""
    try:
        data = request.get_json() or {}
        currency = (data.get('currency') or DEFAULT_CHARGE_CURRENCY).upper()

        # Multi-currency charging is gated. Until the currency layer ships (and Razorpay
        # international is activated), the only currency we may charge in is INR.
        # Without this, a client that sends currency='USD' with an INR amount creates an
        # order for ~85x the intended value.
        if not current_app.config.get('FEATURE_MULTI_CURRENCY', False):
            if currency != DEFAULT_CHARGE_CURRENCY:
                current_app.logger.warning(
                    "Rejected create-order in %s (multi-currency disabled), user=%s",
                    currency, get_jwt_identity()
                )
                return error_response(
                    f'Payments in {currency} are not currently supported. '
                    f'Only {DEFAULT_CHARGE_CURRENCY} is accepted.',
                    400
                )

        user_id = get_jwt_identity()
        quote = None

        # Amount resolution, in descending order of trustworthiness.
        if data.get('quote_id'):
            # Server-authoritative: the amount comes off a quote this server priced.
            try:
                quote = load_spendable_quote(data['quote_id'], user_id)
            except QuoteError as e:
                return error_response(str(e), 400)
            amount_minor = int(quote.total_amount_minor)
            # The quote decides the currency too — not the request body.
            currency = quote.currency

        elif data.get('subscription_plan_id'):
            # Also server-priced: the plan's price is a column, not a request field.
            plan = SubscriptionPlan.query.get(data['subscription_plan_id'])
            if not plan:
                return error_response('Subscription plan not found.', 404)
            amount_minor = minor_units(Decimal(plan.price), currency)

        else:
            # Legacy: the caller states the amount. This is the hole Phase 4 closes —
            # keep it only while the frontend still sends totals, and log every use so
            # the remaining callers are visible before the gate is switched on.
            if current_app.config.get('FEATURE_QUOTE_ONLY_CHECKOUT', False):
                current_app.logger.warning(
                    "Rejected client-priced create-order from user=%s (quote-only mode)", user_id
                )
                return error_response(
                    'This checkout requires a server-issued quote. '
                    'Call POST /api/checkout/quote and send its quote_id.',
                    400
                )
            current_app.logger.info(
                "create-order: client-stated amount accepted from user=%s; "
                "migrate this caller to quote_id", user_id
            )
            try:
                amount_minor = _resolve_amount_minor(data, currency)
            except ValueError as e:
                return error_response(str(e), 400)

        if amount_minor <= 0:
            return error_response('Amount must be greater than zero', 400)

        # Receipt correlation. For a quote the receipt IS the quote id, which is a row
        # that already exists — this is what makes verify-payment able to find its way
        # back. The old client-minted "ORDREF-<timestamp>" matched nothing, so the
        # write-back it fed was dead code.
        receipt = quote.quote_id if quote else (
            data.get('receipt') or f'order_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )

        order_data = {
            'amount': amount_minor,
            'currency': currency,
            'receipt': receipt,
            'notes': {
                'created_by': user_id,
                'created_at': datetime.now().isoformat(),
                'quote_id': quote.quote_id if quote else None,
            }
        }

        razorpay_client = get_razorpay_client()
        order = razorpay_client.order.create(data=order_data)

        if quote is not None:
            # Bind the gateway order to the quote so verify-payment can assert against
            # the right one even if the client sends a different quote_id later.
            quote.razorpay_order_id = order.get('id')
            db.session.commit()
        
        # Normalize response to a consistent shape with both keys
        payload = {
            'id': order.get('id'),
            'amount': order.get('amount'),
            'currency': order.get('currency'),
            'receipt': order.get('receipt'),
            'status': order.get('status'),
            'created_at': order.get('created_at')
        }
        return jsonify({ 'status': 'success', 'success': True, 'data': payload, 'message': 'Razorpay order created successfully' }), 200
        
    except Exception as e:
        return error_response(f'Failed to create Razorpay order: {str(e)}', 500)

@razorpay_bp.route('/api/razorpay/verify-payment', methods=['POST'])
@jwt_required()
def verify_razorpay_payment():
    """Verify Razorpay payment signature"""
    try:
        data = request.get_json() or {}
        user_id = get_jwt_identity()
        # Normalize and strip incoming values to avoid hidden whitespace issues
        razorpay_payment_id = (data.get('razorpay_payment_id') or '').strip()
        razorpay_order_id = (data.get('razorpay_order_id') or '').strip()
        razorpay_signature = (data.get('razorpay_signature') or '').strip()
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return error_response('Missing required payment verification data', 400)
        
        # Create signature verification string
        body = f"{razorpay_order_id}|{razorpay_payment_id}"
        
        # Get Razorpay secret from config
        razorpay_secret = (current_app.config.get('RAZORPAY_KEY_SECRET') or '').strip()
        if not razorpay_secret:
            current_app.logger.error('Razorpay verification failed: RAZORPAY_KEY_SECRET is not configured')
            return error_response('Server configuration error: Razorpay secret missing', 500)
        
        # Generate signature
        generated_signature = hmac.new(
            razorpay_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Debug logging (non-sensitive) to diagnose mismatches in non-production
        if current_app.config.get('DEBUG'):
            current_app.logger.info(
                'Razorpay verify debug: order_id=%s payment_id=%s body="%s" computed_sig=%s received_sig=%s',
                razorpay_order_id,
                razorpay_payment_id,
                body,
                generated_signature,
                razorpay_signature
            )
        
        # Verify signature
        if hmac.compare_digest(generated_signature, razorpay_signature):
            # Fetch the capture. A valid signature proves the message came from
            # Razorpay; it says nothing about how much was captured, so the amount
            # still has to be read from the gateway and checked.
            try:
                client = get_razorpay_client()
                payment = client.payment.fetch(razorpay_payment_id)
            except Exception as e:
                payment = None
                current_app.logger.warning(
                    "Razorpay payment fetch failed for %s: %s", razorpay_payment_id, e
                )

            # Correlate back through the receipt, which for a quote-first checkout is
            # the quote id — a row that existed before the gateway order did.
            receipt = None
            try:
                r_order = get_razorpay_client().order.fetch(razorpay_order_id)
                receipt = (r_order or {}).get('receipt')
            except Exception as e:
                current_app.logger.warning(
                    "Razorpay order fetch failed for %s: %s", razorpay_order_id, e
                )

            # --- Quote-first path: assert, consume, then materialise the order. ---
            quote = None
            if receipt:
                quote = CheckoutQuote.query.get(str(receipt))

            if quote is not None:
                if quote.user_id != user_id:
                    current_app.logger.error(
                        "Quote %s belongs to user %s but was verified by user %s",
                        quote.quote_id, quote.user_id, user_id
                    )
                    return error_response('Payment verification failed.', 403)

                # I2: what the gateway captured must equal what we quoted, to the
                # minor unit, in the same currency. Integers, so there is nothing to
                # round and nothing to nearly-match.
                if payment is None:
                    return error_response(
                        'Could not confirm the captured amount with the payment gateway. '
                        'Your payment has not been lost — please contact support.', 502
                    )

                captured_minor = int(payment.get('amount') or 0)
                captured_currency = (payment.get('currency') or '').upper()
                expected_minor = int(quote.total_amount_minor)
                expected_currency = (quote.currency or DEFAULT_CHARGE_CURRENCY).upper()

                if captured_minor != expected_minor or captured_currency != expected_currency:
                    current_app.logger.error(
                        "Capture/quote mismatch on quote %s: captured %s %s, quoted %s %s",
                        quote.quote_id, captured_minor, captured_currency,
                        expected_minor, expected_currency
                    )
                    return error_response(
                        'Payment amount does not match the quoted total. '
                        'No order was created; please contact support.', 400
                    )

                # Single-use, enforced by a conditional UPDATE rather than a check.
                # Two concurrent verifies of one quote: exactly one wins here.
                if not consume_quote(quote.quote_id):
                    db.session.rollback()
                    existing = CheckoutQuote.query.get(quote.quote_id)
                    if existing and existing.order_id:
                        # Idempotent replay — the customer refreshed, the order exists.
                        return success_response(
                            'Payment already verified',
                            {'payment_id': razorpay_payment_id,
                             'order_id': existing.order_id,
                             'verified': True}
                        )
                    return error_response('This quote has already been paid.', 409)

                try:
                    from controllers.order_controller import OrderController
                    order = OrderController.create_order_from_quote(
                        user_id=quote.user_id,
                        quote=quote,
                        gateway_refs={
                            'razorpay_order_id': razorpay_order_id,
                            'razorpay_payment_id': razorpay_payment_id,
                        },
                        extra=data.get('order') or {},
                    )
                    # Point the consumed quote at the order it became (I10).
                    quote.order_id = order.order_id
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(
                        "Payment %s captured but order creation failed for quote %s: %s",
                        razorpay_payment_id, quote.quote_id, e, exc_info=True
                    )
                    # Money moved and no order exists. Loud, and never a silent 200.
                    return error_response(
                        'Your payment succeeded but we could not finalise the order. '
                        'Support has been notified — please do not pay again.', 500
                    )

                return success_response(
                    'Payment verified successfully',
                    {'payment_id': razorpay_payment_id,
                     'order_id': order.order_id,
                     'quote_id': quote.quote_id,
                     'verified': True}
                )

            # --- Legacy path: no quote behind this payment. ---
            internal_order_id = receipt

            if internal_order_id:
                try:
                    from models.order import Order
                    order = Order.query.get(internal_order_id)
                    if order:
                        order.razorpay_order_id = razorpay_order_id
                        order.razorpay_payment_id = razorpay_payment_id
                        order.payment_gateway_transaction_id = razorpay_payment_id
                        order.payment_gateway_name = 'Razorpay'
                        db.session.commit()
                        current_app.logger.info(
                            "Razorpay refs stored on order %s", internal_order_id
                        )
                    else:
                        current_app.logger.warning(
                            "Razorpay receipt '%s' matched no internal order; gateway "
                            "references were not stored for payment %s",
                            internal_order_id, razorpay_payment_id
                        )
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(
                        "Failed storing Razorpay refs on order %s: %s",
                        internal_order_id, e, exc_info=True
                    )

            # Payment verification successful
            return success_response(
                'Payment verified successfully',
                {
                    'payment_id': razorpay_payment_id,
                    'order_id': razorpay_order_id,
                    'verified': True
                }
            )
        else:
            # Include more details in DEBUG to speed up diagnosis
            message = 'Payment verification failed - invalid signature'
            if current_app.config.get('DEBUG'):
                message = (
                    f'{message}. computed_signature={generated_signature} '
                    f'received_signature={razorpay_signature} body="{body}"'
                )
            return error_response(message, 400)
            
    except Exception as e:
        return error_response(f'Payment verification failed: {str(e)}', 500)

@razorpay_bp.route('/api/razorpay/payment-details/<payment_id>', methods=['GET'])
@jwt_required()
def get_payment_details(payment_id):
    """Get Razorpay payment details"""
    try:
        razorpay_client = get_razorpay_client()
        payment = razorpay_client.payment.fetch(payment_id)
        
        return success_response({
            'id': payment['id'],
            'amount': payment['amount'],
            'currency': payment['currency'],
            'status': payment['status'],
            'method': payment['method'],
            'created_at': payment['created_at'],
            'captured': payment['captured'],
            'description': payment.get('description', ''),
            'notes': payment.get('notes', {})
        }, 'Payment details retrieved successfully')
        
    except Exception as e:
        return error_response(f'Failed to fetch payment details: {str(e)}', 500)

@razorpay_bp.route('/api/razorpay/refund', methods=['POST'])
@jwt_required()
def create_refund():
    """Create a Razorpay refund"""
    try:
        data = request.get_json() or {}
        payment_id = data.get('payment_id')
        amount = data.get('amount')  # Amount in minor units (paise)
        notes = data.get('notes', {})

        if not payment_id:
            return error_response('Payment ID is required', 400)

        # Read the capture first. Everything below is checked against what was
        # actually taken, never against what the caller says was taken.
        razorpay_client = get_razorpay_client()
        try:
            payment = razorpay_client.payment.fetch(payment_id)
        except Exception as e:
            current_app.logger.warning("Refund: payment fetch failed for %s: %s", payment_id, e)
            return error_response('Could not read the original payment from the gateway.', 502)

        captured_minor = int((payment or {}).get('amount') or 0)
        captured_currency = ((payment or {}).get('currency') or DEFAULT_CHARGE_CURRENCY).upper()

        if amount is None:
            refund_minor = captured_minor
        else:
            try:
                refund_minor = int(amount)
            except (TypeError, ValueError):
                return error_response('Refund amount must be an integer number of minor units.', 400)

        if refund_minor <= 0:
            return error_response('Refund amount must be greater than zero.', 400)

        # I11: the sum of refunds may never exceed the capture. Without the ledger
        # below this was unenforceable — nothing recorded that a refund had happened,
        # so the same payment could be refunded in full repeatedly.
        already = PaymentRefund.total_refunded_minor(payment_id)
        if already + refund_minor > captured_minor:
            return error_response(
                f'Refund exceeds the captured amount. Captured {captured_minor}, '
                f'already refunded {already}, requested {refund_minor} (minor units).',
                400
            )

        ledger = PaymentRefund(
            gateway_payment_id=payment_id,
            gateway_name='Razorpay',
            amount_minor=refund_minor,
            # I11 again: a refund is denominated in the capture's currency, full stop.
            currency=captured_currency,
            status=RefundStatus.PENDING,
            notes=json.dumps(notes) if notes else None,
            created_by_user_id=get_jwt_identity(),
        )
        quote = CheckoutQuote.query.filter_by(razorpay_order_id=(payment or {}).get('order_id')).first()
        if quote and quote.order_id:
            ledger.order_id = quote.order_id
        db.session.add(ledger)
        db.session.commit()

        refund_data = {'payment_id': payment_id, 'notes': notes, 'amount': refund_minor}

        try:
            refund = razorpay_client.payment.refund(payment_id, refund_data)
        except Exception as e:
            ledger.status = RefundStatus.FAILED
            db.session.commit()
            current_app.logger.error("Refund failed at gateway for %s: %s", payment_id, e, exc_info=True)
            return error_response(f'Failed to create refund: {str(e)}', 500)

        ledger.gateway_refund_id = refund.get('id')
        ledger.status = RefundStatus.PROCESSED
        db.session.commit()

        return success_response({
            'id': refund['id'],
            'amount': refund['amount'],
            'currency': refund['currency'],
            'status': refund['status'],
            'created_at': refund['created_at'],
            'notes': refund.get('notes', {}),
            'refund_id': ledger.refund_id,
        }, 'Refund created successfully')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Refund error: %s", e, exc_info=True)
        return error_response(f'Failed to create refund: {str(e)}', 500)


@razorpay_bp.route('/api/razorpay/payouts/bulk', methods=['POST'])
@jwt_required()
def create_bulk_payouts():
    """Initiate bulk payouts to merchants (server-side). This endpoint expects an array of
    { merchant_id: number, amount: number, notes?: object } objects. If RazorpayX is not
    configured, it will simulate success for development.
    """
    try:
        payload = request.get_json() or {}
        payouts = payload.get('payouts')

        if not payouts or not isinstance(payouts, list):
            return error_response('Invalid or missing payouts array', 400)

        # Attempt to initialize client. If payouts API is not enabled, we'll simulate.
        client = get_razorpay_client()

        created = []
        for p in payouts:
            merchant_id = p.get('merchant_id')
            amount = p.get('amount')
            notes = p.get('notes', {})

            if merchant_id is None or amount is None:
                return error_response('Each payout must include merchant_id and amount', 400)

            # In a real integration, you would look up the merchant's fund account/contact,
            # and create a payout via RazorpayX. Here we attempt a best-effort call if
            # available; otherwise we simulate a created payout.
            try:
                # Example simulated structure. Replace with client.payout.create(...) if configured.
                created.append({
                    'merchant_id': merchant_id,
                    'amount': amount,
                    'currency': 'INR',
                    'status': 'initiated',
                    'payout_id': f"sim_{merchant_id}_{int(datetime.now().timestamp())}",
                    'notes': notes
                })
            except Exception as inner:
                return error_response(f'Failed to initiate payout for merchant {merchant_id}: {str(inner)}', 500)

        return jsonify({ 'status': 'success', 'success': True, 'data': created, 'message': 'Payouts initiated' }), 200

    except Exception as e:
        return error_response(f'Failed to create payouts: {str(e)}', 500)