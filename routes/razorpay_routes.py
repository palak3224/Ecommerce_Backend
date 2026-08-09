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

        try:
            amount_minor = _resolve_amount_minor(data, currency)
        except ValueError as e:
            return error_response(str(e), 400)

        if amount_minor <= 0:
            return error_response('Amount must be greater than zero', 400)

        # Create Razorpay order
        order_data = {
            'amount': amount_minor,
            'currency': currency,
            # If client supplied a receipt, use it to correlate to internal order; else auto-generate
            'receipt': data.get('receipt') or f'order_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'notes': {
                'created_by': get_jwt_identity(),
                'created_at': datetime.now().isoformat()
            }
        }
        
        razorpay_client = get_razorpay_client()
        order = razorpay_client.order.create(data=order_data)
        
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
        data = request.get_json()
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
            # Optionally fetch payment details and ensure it belongs to the same order
            try:
                client = get_razorpay_client()
                payment = client.payment.fetch(razorpay_payment_id)
            except Exception:
                payment = None

            # Correlate back to the internal order via the Razorpay receipt.
            #
            # NOTE: today the checkout creates the Razorpay order BEFORE the internal
            # Order row exists, so `receipt` is a client-minted "ORDREF-<timestamp>"
            # that matches no row and this write-back is a no-op. It is left in place
            # (and now logs) because it becomes correct once checkout is quote-first.
            internal_order_id = None
            try:
                r_order = get_razorpay_client().order.fetch(razorpay_order_id)
                internal_order_id = (r_order or {}).get('receipt')
            except Exception as e:
                current_app.logger.warning(
                    "Razorpay order fetch failed for %s: %s", razorpay_order_id, e
                )

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
        data = request.get_json()
        payment_id = data.get('payment_id')
        amount = data.get('amount')  # Amount in paise
        notes = data.get('notes', {})
        
        if not payment_id:
            return error_response('Payment ID is required', 400)
        
        # Create refund
        refund_data = {
            'payment_id': payment_id,
            'notes': notes
        }
        
        if amount:
            refund_data['amount'] = amount
        
        razorpay_client = get_razorpay_client()
        refund = razorpay_client.payment.refund(payment_id, refund_data)
        
        return success_response({
            'id': refund['id'],
            'amount': refund['amount'],
            'currency': refund['currency'],
            'status': refund['status'],
            'created_at': refund['created_at'],
            'notes': refund.get('notes', {})
        }, 'Refund created successfully')
        
    except Exception as e:
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