from flask import Blueprint, jsonify, request
import requests
from common.cache import cached, get_redis_client
from config import get_config

currency_bp = Blueprint('currency', __name__)

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
    try:
        base_currency = request.args.get('base', 'INR')
        api_key = 'fca_live_aFAdTe4CWvzK9T5gYKYaujiesHUctsg7caoBWZ3J'
        
        response = requests.get(
            f'https://api.freecurrencyapi.com/v1/latest?apikey={api_key}&base_currency={base_currency}',
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 401:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided FreeCurrencyAPI key is invalid or expired.'
            }), 401
        elif response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch exchange rates',
                'status': response.status_code,
                'message': response.text
            }), response.status_code
            
        data = response.json()
        return jsonify({
            'base_currency': base_currency,
            'conversion_rates': data['data'],
            'last_updated': data.get('meta', {}).get('last_updated_at', '')
        })
        
    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'API request timeout',
            'message': 'External API request timed out after 10 seconds'
        }), 500
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': 'API request failed',
            'message': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500 