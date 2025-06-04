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
            f'https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}',
            headers={'Accept': 'application/json'}
        )
        
        if response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch exchange rates',
                'status': response.status_code
            }), response.status_code
            
        data = response.json()
        return jsonify({
            'base_currency': data['base_code'],
            'conversion_rates': data['conversion_rates'],
            'last_updated': data['time_last_update_utc']
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Failed to fetch exchange rates'
        }), 500 