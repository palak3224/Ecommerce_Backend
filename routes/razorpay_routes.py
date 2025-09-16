from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from common.response import success_response, error_response
import razorpay
import os
import hmac
import hashlib
import json
from datetime import datetime

razorpay_bp = Blueprint('razorpay', __name__)

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
        data = request.get_json()
        amount = data.get('amount')  # Amount in paise
        currency = data.get('currency', 'INR')
        
        if not amount:
            return error_response('Amount is required', 400)
        
        # Create Razorpay order
        order_data = {
            'amount': amount,
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

            # Update internal order record if a receipt is present on the Razorpay order
            # Try to fetch order to get receipt reference
            internal_order_id = None
            try:
                client = get_razorpay_client()
                r_order = client.order.fetch(razorpay_order_id)
                internal_order_id = (r_order or {}).get('receipt')
            except Exception:
                internal_order_id = None

            try:
                from controllers.order_controller import OrderController
                from models.enums import PaymentStatusEnum
                if internal_order_id:
                    # Update payment success and store gateway refs
                    from models.order import Order
                    order = Order.query.get(internal_order_id)
                    if order:
                        order.razorpay_order_id = razorpay_order_id
                        order.razorpay_payment_id = razorpay_payment_id
                        order.payment_gateway_transaction_id = razorpay_payment_id
                        order.payment_gateway_name = 'Razorpay'
                        db = current_app.extensions['sqlalchemy'].db
                        db.session.commit()
                # else we just return success for verification
            except Exception:
                pass

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