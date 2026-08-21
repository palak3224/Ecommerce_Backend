# FILE: routes/plinko_routes.py
"""Public endpoints for the storefront lead-capture game.

Unauthenticated by design — the whole point is to capture visitors who have no account.
@rate_limit is the cheap fast path when Redis is up; it degrades to a no-op when Redis
is unavailable, so the real guards (per-IP counts, unique claim indexes, the daily mint
ceiling) are DB-backed inside the controller.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from common.decorators import rate_limit
from controllers import plinko_controller
from controllers.plinko_controller import PlinkoError

plinko_bp = Blueprint('plinko_bp', __name__, url_prefix='/api/plinko')


def _client_ip():
    """First hop in X-Forwarded-For when behind the CDN, else the socket address."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr


def _optional_user_id():
    """Logged-in customers can play too; we just record who they were."""
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:
        return None


def _fail(error):
    return jsonify({'error': error.message}), error.status


@plinko_bp.route('/campaign', methods=['GET'])
def get_campaign():
    """Board configuration for the popup. Never includes the draw weights."""
    try:
        return jsonify(plinko_controller.campaign_config()), 200
    except PlinkoError as e:
        return _fail(e)


@plinko_bp.route('/play', methods=['POST'])
@rate_limit(limit=20, per=3600, key_prefix='plinko_play')
def play():
    """Drop the puck. Returns the slot to animate to — never a coupon code."""
    data = request.get_json(silent=True) or {}
    try:
        result = plinko_controller.play(
            source_page=data.get('source_page'),
            ip=_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            user_id=_optional_user_id(),
        )
        return jsonify(result), 201
    except PlinkoError as e:
        return _fail(e)


@plinko_bp.route('/reveal', methods=['POST'])
@rate_limit(limit=30, per=3600, key_prefix='plinko_reveal')
def reveal():
    """Trade an email for half the code. The other half stays on the server."""
    data = request.get_json(silent=True) or {}
    try:
        result = plinko_controller.capture_email(
            data.get('session_token'), data.get('email')
        )
        return jsonify(result), 200
    except PlinkoError as e:
        return _fail(e)


@plinko_bp.route('/claim', methods=['POST'])
@rate_limit(limit=15, per=3600, key_prefix='plinko_claim')
def claim():
    """Trade a phone number for the full code. This is where the coupon is minted."""
    data = request.get_json(silent=True) or {}
    try:
        result = plinko_controller.claim(
            data.get('session_token'), data.get('phone')
        )
        return jsonify(result), 200
    except PlinkoError as e:
        return _fail(e)
