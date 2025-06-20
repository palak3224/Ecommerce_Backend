from models.merchant_transaction import MerchantTransaction
from common.database import db
from datetime import datetime

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
