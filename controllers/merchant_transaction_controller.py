from models.merchant_transaction import MerchantTransaction
from models.order import Order, OrderItem
from common.database import db
from datetime import datetime, date
from decimal import Decimal

def calculate_platform_fee_percentage(order_amount):
    """
    Calculate platform fee percentage based on order amount (excluding tax)
    """
    if order_amount <= 500:
        return Decimal('5.00')  # 5%
    elif order_amount <= 2000:
        return Decimal('4.00')  # 4%
    elif order_amount <= 10000:
        return Decimal('3.00')  # 3%
    else:
        return Decimal('2.00')  # 2%

def calculate_transaction_fees(order_amount):
    """
    Calculate all transaction fees for a given order amount (excluding tax)
    Returns: dict with platform_fee_percent, platform_fee_amount, payment_gateway_fee, gst_amount, final_payable_amount
    """
    # Platform fee calculation
    platform_fee_percent = calculate_platform_fee_percentage(order_amount)
    platform_fee_amount = (order_amount * platform_fee_percent) / Decimal('100')
    
    # Payment gateway fee (2% flat)
    payment_gateway_fee = (order_amount * Decimal('2.00')) / Decimal('100')
    
    # GST on platform fee (18%)
    gst_on_fee_amount = (platform_fee_amount * Decimal('18.00')) / Decimal('100')
    
    # Final payable amount to merchant
    final_payable_amount = order_amount - platform_fee_amount - payment_gateway_fee - gst_on_fee_amount
    
    return {
        'platform_fee_percent': platform_fee_percent,
        'platform_fee_amount': platform_fee_amount,
        'payment_gateway_fee': payment_gateway_fee,
        'gst_on_fee_amount': gst_on_fee_amount,
        'final_payable_amount': final_payable_amount
    }

def create_merchant_transaction_from_order(order_id, settlement_date=None):
    """
    Create merchant transaction record from an order
    """
    order = Order.query.get_or_404(order_id)
    
    # Get order items grouped by merchant
    merchant_items = {}
    for item in order.items:
        if item.merchant_id not in merchant_items:
            merchant_items[item.merchant_id] = []
        merchant_items[item.merchant_id].append(item)
    
    transactions = []
    
    for merchant_id, items in merchant_items.items():
        # Calculate total amount for this merchant (excluding tax)
        merchant_order_amount = sum(item.line_item_total_inclusive_gst for item in items)
        
        # Calculate fees
        fees = calculate_transaction_fees(merchant_order_amount)
        
        # Set settlement date (default to 7 days from order date)
        if settlement_date is None:
            settlement_date = date.today()
        
        # Create transaction record
        transaction = MerchantTransaction(
            order_id=order.order_id,
            merchant_id=merchant_id,
            order_amount=merchant_order_amount,
            platform_fee_percent=fees['platform_fee_percent'],
            platform_fee_amount=fees['platform_fee_amount'],
            gst_on_fee_amount=fees['gst_on_fee_amount'],
            payment_gateway_fee=fees['payment_gateway_fee'],
            final_payable_amount=fees['final_payable_amount'],
            payment_status='pending',
            settlement_date=settlement_date
        )
        
        db.session.add(transaction)
        transactions.append(transaction)
    
    db.session.commit()
    return transactions

def bulk_create_transactions_for_orders(order_ids, settlement_date=None):
    """
    Create merchant transactions for multiple orders
    """
    transactions = []
    for order_id in order_ids:
        try:
            order_transactions = create_merchant_transaction_from_order(order_id, settlement_date)
            transactions.extend(order_transactions)
        except Exception as e:
            # Log error and continue with other orders
            print(f"Error creating transaction for order {order_id}: {str(e)}")
            continue
    
    return transactions

def get_merchant_transaction_summary(merchant_id=None, from_date=None, to_date=None):
    """
    Get summary of merchant transactions
    """
    query = MerchantTransaction.query
    
    if merchant_id:
        query = query.filter_by(merchant_id=merchant_id)
    if from_date:
        query = query.filter(MerchantTransaction.settlement_date >= from_date)
    if to_date:
        query = query.filter(MerchantTransaction.settlement_date <= to_date)
    
    transactions = query.all()
    
    total_order_amount = sum(t.order_amount for t in transactions)
    total_platform_fees = sum(t.platform_fee_amount for t in transactions)
    total_payment_gateway_fees = sum(t.payment_gateway_fee for t in transactions)
    total_gst = sum(t.gst_on_fee_amount for t in transactions)
    total_payable = sum(t.final_payable_amount for t in transactions)
    
    pending_transactions = [t for t in transactions if t.payment_status == 'pending']
    paid_transactions = [t for t in transactions if t.payment_status == 'paid']
    
    return {
        'total_transactions': len(transactions),
        'pending_transactions': len(pending_transactions),
        'paid_transactions': len(paid_transactions),
        'total_order_amount': float(total_order_amount),
        'total_platform_fees': float(total_platform_fees),
        'total_payment_gateway_fees': float(total_payment_gateway_fees),
        'total_gst': float(total_gst),
        'total_payable_to_merchants': float(total_payable),
        'pending_amount': float(sum(t.final_payable_amount for t in pending_transactions)),
        'paid_amount': float(sum(t.final_payable_amount for t in paid_transactions))
    }

def list_all_transactions(filters):
    query = MerchantTransaction.query

    if filters.get("status"):
        query = query.filter_by(payment_status=filters["status"])
    if filters.get("merchant_id"):
        query = query.filter_by(merchant_id=filters["merchant_id"])
    if filters.get("from_date"):
        query = query.filter(MerchantTransaction.settlement_date >= filters["from_date"])
    if filters.get("to_date"):
        query = query.filter(MerchantTransaction.settlement_date <= filters["to_date"])

    return query.order_by(MerchantTransaction.settlement_date.desc()).all()

def get_transaction_by_id(txn_id):
    return MerchantTransaction.query.get_or_404(txn_id)

def mark_as_paid(txn_id):
    txn = MerchantTransaction.query.get_or_404(txn_id)
    if txn.payment_status == 'paid':
        return None  # Already paid
    txn.payment_status = 'paid'
    txn.updated_at = datetime.utcnow()
    db.session.commit()
    return txn

def calculate_fee_preview(order_amount):
    """
    Calculate and return a detailed fee breakdown for preview purposes
    """
    fees = calculate_transaction_fees(order_amount)
    
    return {
        'order_amount': float(order_amount),
        'platform_fee_percentage': float(fees['platform_fee_percent']),
        'platform_fee_amount': float(fees['platform_fee_amount']),
        'payment_gateway_fee_percentage': 2.0,  # Fixed 2%
        'payment_gateway_fee_amount': float(fees['payment_gateway_fee']),
        'gst_percentage': 18.0,  # Fixed 18%
        'gst_amount': float(fees['gst_on_fee_amount']),
        'total_deductions': float(fees['platform_fee_amount'] + fees['payment_gateway_fee'] + fees['gst_on_fee_amount']),
        'final_payable_amount': float(fees['final_payable_amount']),
        'fee_breakdown': {
            'platform_fee': {
                'percentage': float(fees['platform_fee_percent']),
                'amount': float(fees['platform_fee_amount']),
                'description': f"Platform fee ({fees['platform_fee_percent']}%)"
            },
            'payment_gateway_fee': {
                'percentage': 2.0,
                'amount': float(fees['payment_gateway_fee']),
                'description': "Payment gateway fee (2%)"
            },
            'gst': {
                'percentage': 18.0,
                'amount': float(fees['gst_on_fee_amount']),
                'description': f"GST on platform fee (18%)"
            }
        }
    }

def get_merchant_pending_payments(merchant_id):
    """
    Get all pending payments for a specific merchant
    """
    transactions = MerchantTransaction.query.filter_by(
        merchant_id=merchant_id,
        payment_status='pending'
    ).order_by(MerchantTransaction.settlement_date.asc()).all()
    
    total_pending = sum(t.final_payable_amount for t in transactions)
    
    return {
        'transactions': [t.serialize() for t in transactions],
        'total_pending_amount': float(total_pending),
        'transaction_count': len(transactions)
    }

def bulk_mark_as_paid(transaction_ids):
    """
    Mark multiple transactions as paid
    """
    transactions = MerchantTransaction.query.filter(
        MerchantTransaction.id.in_(transaction_ids)
    ).all()
    
    updated_count = 0
    for transaction in transactions:
        if transaction.payment_status != 'paid':
            transaction.payment_status = 'paid'
            transaction.updated_at = datetime.utcnow()
            updated_count += 1
    
    db.session.commit()
    return {
        'total_transactions': len(transactions),
        'updated_count': updated_count,
        'already_paid_count': len(transactions) - updated_count
    }

def get_transaction_statistics(from_date=None, to_date=None):
    """
    Get comprehensive transaction statistics
    """
    query = MerchantTransaction.query
    
    if from_date:
        query = query.filter(MerchantTransaction.settlement_date >= from_date)
    if to_date:
        query = query.filter(MerchantTransaction.settlement_date <= to_date)
    
    transactions = query.all()
    
    if not transactions:
        return {
            'total_transactions': 0,
            'total_order_amount': 0,
            'total_platform_fees': 0,
            'total_payment_gateway_fees': 0,
            'total_gst': 0,
            'total_payable': 0,
            'pending_amount': 0,
            'paid_amount': 0,
            'fee_distribution': {},
            'status_distribution': {}
        }
    
    # Calculate totals
    total_order_amount = sum(t.order_amount for t in transactions)
    total_platform_fees = sum(t.platform_fee_amount for t in transactions)
    total_payment_gateway_fees = sum(t.payment_gateway_fee for t in transactions)
    total_gst = sum(t.gst_on_fee_amount for t in transactions)
    total_payable = sum(t.final_payable_amount for t in transactions)
    
    # Status distribution
    pending_transactions = [t for t in transactions if t.payment_status == 'pending']
    paid_transactions = [t for t in transactions if t.payment_status == 'paid']
    
    # Fee distribution by tier
    fee_distribution = {
        '5%': {'count': 0, 'amount': Decimal('0')},
        '4%': {'count': 0, 'amount': Decimal('0')},
        '3%': {'count': 0, 'amount': Decimal('0')},
        '2%': {'count': 0, 'amount': Decimal('0')}
    }
    
    for transaction in transactions:
        fee_percent = str(transaction.platform_fee_percent) + '%'
        if fee_percent in fee_distribution:
            fee_distribution[fee_percent]['count'] += 1
            fee_distribution[fee_percent]['amount'] += transaction.platform_fee_amount
    
    return {
        'total_transactions': len(transactions),
        'total_order_amount': float(total_order_amount),
        'total_platform_fees': float(total_platform_fees),
        'total_payment_gateway_fees': float(total_payment_gateway_fees),
        'total_gst': float(total_gst),
        'total_payable': float(total_payable),
        'pending_amount': float(sum(t.final_payable_amount for t in pending_transactions)),
        'paid_amount': float(sum(t.final_payable_amount for t in paid_transactions)),
        'fee_distribution': {
            tier: {
                'count': data['count'],
                'amount': float(data['amount'])
            } for tier, data in fee_distribution.items()
        },
        'status_distribution': {
            'pending': len(pending_transactions),
            'paid': len(paid_transactions)
        }
    }
