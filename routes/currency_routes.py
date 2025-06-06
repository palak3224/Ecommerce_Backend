from flask import Blueprint, jsonify, request
import requests
from common.cache import cached
from config import get_config

currency_bp = Blueprint('currency', __name__)

# Cache exchange rates for 1 hour to avoid hitting API limits
@currency_bp.route('/api/exchange-rates', methods=['GET'])
@cached(timeout=3600)
def get_exchange_rates():
    try:
        config = get_config()
        api_key = config.EXCHANGE_RATE_API_KEY
        base_currency = request.args.get('base', 'INR')
        
        response = requests.get(
            f'https://api.freecurrencyapi.com/v1/latest?apikey={api_key}&base_currency={base_currency}',
            headers={'Accept': 'application/json'}
        )
        
        if response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch exchange rates',
                'status': response.status_code
            }), response.status_code
            
        data = response.json()
        return jsonify({
            'base_currency': base_currency,
            'conversion_rates': data['data'],
            'last_updated': data.get('meta', {}).get('last_updated_at', '')
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Failed to fetch exchange rates'
        }), 500 