from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from controllers import merchant_transaction_controller as txn_ctrl

merchant_transaction_bp = Blueprint('merchant_transaction', __name__)

@merchant_transaction_bp.route('/merchant-transactions/from-order', methods=['POST', 'OPTIONS'])
def create_transaction_from_order():
    """
    Create merchant transaction(s) from an order. Expects JSON: {"order_id": "..."}
    """
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    # Apply JWT requirement only for POST requests
    @jwt_required()
    def _create_transaction():
        data = request.get_json()
        order_id = data.get('order_id')
        if not order_id:
            return jsonify({'status': 'error', 'message': 'order_id is required'}), 400
        try:
            transactions = txn_ctrl.create_merchant_transaction_from_order(order_id)
            return jsonify({'status': 'success', 'transactions': [t.serialize() for t in transactions]}), 201
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return _create_transaction()

@merchant_transaction_bp.route('/merchant-transactions/<int:txn_id>', methods=['GET', 'OPTIONS'])
def get_transaction(txn_id):
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    # Apply JWT requirement only for GET requests
    @jwt_required()
    def _get_transaction():
        txn = txn_ctrl.get_transaction_by_id(txn_id)
        return jsonify({'status': 'success', 'transaction': txn.serialize()})
    
    return _get_transaction()

@merchant_transaction_bp.route('/merchant-transactions', methods=['GET', 'OPTIONS'])
def list_transactions():
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    # Apply JWT requirement only for GET requests
    @jwt_required()
    def _list_transactions():
        filters = {
            'status': request.args.get('status'),
            'merchant_id': request.args.get('merchant_id'),
            'from_date': request.args.get('from_date'),
            'to_date': request.args.get('to_date'),
        }
        txns = txn_ctrl.list_all_transactions(filters)
        return jsonify({'status': 'success', 'transactions': [t.serialize() for t in txns]})
    
    return _list_transactions()
