import re

from flask import Blueprint, jsonify, request, current_app
import requests
from common.cache import cached, get_redis_client
from config import get_config

currency_bp = Blueprint('currency', __name__)

FX_PROVIDER_URL = 'https://api.freecurrencyapi.com/v1/latest'
_CURRENCY_CODE = re.compile(r'^[A-Z]{3}$')

# NOTE: this endpoint is a passthrough and is scheduled for deletion. Phase 2 of
# docs/MULTI_CURRENCY.md replaces it with services/fx_service.py backed by an
# append-only fx_rates table, so historical orders can reference the exact rate row
# they were priced at. Do not build anything new on top of this route.

# Cache exchange rates for 1 hour to avoid hitting API limits
@currency_bp.route('/api/exchange-rates', methods=['GET'])
@cached(timeout=3600, key_prefix='exchange_rates')
def get_exchange_rates():
    """
    Get current exchange rates for all supported currencies
    ---
    tags:
      - Currency
    parameters:
      - in: query
        name: base
        type: string
        required: false
        default: INR
        description: Base currency code (e.g., INR, USD, EUR)
    responses:
      200:
        description: Exchange rates retrieved successfully
        schema:
          type: object
          properties:
            base_currency:
              type: string
              example: INR
            conversion_rates:
              type: object
              additionalProperties:
                type: number
                format: float
              example:
                USD: 0.012
                EUR: 0.011
                GBP: 0.0095
            last_updated:
              type: string
              format: date-time
              example: "2024-03-20T10:30:00Z"
      401:
        description: Invalid API key
        schema:
          type: object
          properties:
            error:
              type: string
              example: Invalid API key
            message:
              type: string
              example: The provided FreeCurrencyAPI key is invalid or expired.
      500:
        description: Internal server error or API request failed
        schema:
          type: object
          properties:
            error:
              type: string
              example: API request failed
            message:
              type: string
    """
    base_currency = (request.args.get('base') or 'INR').upper()
    if not _CURRENCY_CODE.match(base_currency):
        return jsonify({
            'error': 'Invalid base currency',
            'message': 'base must be a three-letter currency code, e.g. INR.'
        }), 400

    api_key = current_app.config.get('FREECURRENCY_API_KEY')
    if not api_key:
        # Deliberately fatal. The previous version fell back to a literal in the
        # source, which is how a live key reached a public repository and stayed
        # the one in use. Better to serve no rates than to serve them off a
        # credential nobody knows is there.
        current_app.logger.error(
            'FREECURRENCY_API_KEY is not configured; /api/exchange-rates disabled'
        )
        return jsonify({
            'error': 'Exchange rates unavailable',
            'message': 'Currency conversion is not configured on this server.'
        }), 503

    try:
        response = requests.get(
            FX_PROVIDER_URL,
            # As params, not interpolated into the URL: the key stays out of any
            # f-string that might later be logged or echoed.
            params={'apikey': api_key, 'base_currency': base_currency},
            headers={'Accept': 'application/json'},
            timeout=10
        )
    except requests.exceptions.Timeout:
        current_app.logger.warning('FX provider timed out for base=%s', base_currency)
        return jsonify({
            'error': 'API request timeout',
            'message': 'The exchange rate provider did not respond in time.'
        }), 504
    except requests.exceptions.RequestException as e:
        current_app.logger.warning('FX provider request failed: %s', e)
        return jsonify({
            'error': 'API request failed',
            'message': 'Could not reach the exchange rate provider.'
        }), 502

    if response.status_code == 401:
        current_app.logger.error('FX provider rejected our API key (401)')
        return jsonify({
            'error': 'Exchange rates unavailable',
            'message': 'Currency conversion is temporarily unavailable.'
        }), 503

    if response.status_code != 200:
        # Log the provider's body, never return it. Upstream error text can carry
        # the request it was made with, which is how a key leaks a second time.
        current_app.logger.warning(
            'FX provider returned %s: %s', response.status_code, response.text[:500]
        )
        return jsonify({
            'error': 'Failed to fetch exchange rates',
            'message': 'The exchange rate provider returned an error.'
        }), 502

    try:
        data = response.json()
        rates = data['data']
    except (ValueError, KeyError, TypeError) as e:
        current_app.logger.warning('FX provider sent an unreadable payload: %s', e)
        return jsonify({
            'error': 'Failed to fetch exchange rates',
            'message': 'The exchange rate provider returned an unreadable response.'
        }), 502

    return jsonify({
        'base_currency': base_currency,
        'conversion_rates': rates,
        'last_updated': data.get('meta', {}).get('last_updated_at', '')
    })


@currency_bp.route('/api/currency/context', methods=['GET'])
def get_currency_context():
    """What currency should this visitor see, and what may they choose?

    Unauthenticated on purpose — a first-time visitor needs this before the
    storefront renders its first price, and it discloses nothing private.

    Country detection reads the CDN/proxy headers rather than doing a GeoIP lookup
    of its own: CloudFront and Cloudflare both stamp the resolved country on the
    request, and they are far more accurate than anything derived from a raw IP.
    """
    from services.currency_context import (
        base_currency, multi_currency_enabled, supported_currencies,
    )

    country = (
        request.headers.get('CloudFront-Viewer-Country')
        or request.headers.get('CF-IPCountry')
        or request.headers.get('X-Country-Code')
        or ''
    ).strip().upper()

    home = (current_app.config.get('HOME_COUNTRY_CODE') or 'IN').upper()
    base = base_currency()
    enabled = multi_currency_enabled()

    # India (or unknown) sees the book currency. "Unknown" resolving to INR is
    # deliberate: an undetected visitor sees the currency they will actually be
    # charged in, which is the safer of the two mistakes.
    if not enabled or not country or country == home:
        suggested = base
    else:
        quotes = [c for c in supported_currencies() if c != base]
        suggested = quotes[0] if quotes else base

    return jsonify({
        'suggested_currency': suggested,
        'base_currency': base,
        'detected_country': country or None,
        'multi_currency_enabled': enabled,
        'supported_currencies': supported_currencies() if enabled else [base],
        # Phase 7: with FEATURE_MULTI_CURRENCY on the customer is charged in the
        # currency they browse in (Razorpay International settles it to INR). With it
        # off, USD is display-only and everyone is charged in the base currency.
        'charge_in_presentment': enabled,
        # Best-effort single value for older clients: the currency we would charge in
        # for the suggested view. Newer clients use charge_in_presentment instead.
        'charge_currency': suggested if enabled else base,
    })
