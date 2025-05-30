# controllers/merchant/product_controller.py

from flask_jwt_extended import get_jwt_identity
from flask import abort
from common.database import db
from models.product import Product
from auth.models.models import MerchantProfile
from datetime import datetime, timezone

class MerchantProductController:
    @staticmethod
    def list_all():
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")
        return Product.query.filter_by(
            merchant_id=merchant.id,
            deleted_at=None
        ).all()

    @staticmethod
    def get(pid):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")
        return Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

    @staticmethod
    def create(data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        p = Product(
            merchant_id=merchant.id,
            category_id=data['category_id'],
            brand_id=data['brand_id'],
            sku=data['sku'],
            product_name=data['product_name'],
            product_description=data['product_description'],
            cost_price=data['cost_price'],
            selling_price=data['selling_price'],
            discount_pct=data.get('discount_pct', 0),
            special_price=data.get('special_price'),
            special_start=data.get('special_start'),
            special_end=data.get('special_end'),
            approval_status='pending'  # Set initial approval status
        )
        p.save()
        return p

    @staticmethod
    def update(pid, data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        p = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        # If product is approved, changing certain fields will require re-approval
        if p.approval_status == 'approved':
            fields_requiring_reapproval = {
                'product_name', 'product_description', 'cost_price', 
                'selling_price', 'special_price', 'special_start', 'special_end'
            }
            if any(field in data for field in fields_requiring_reapproval):
                p.approval_status = 'pending'
                p.approved_at = None
                p.approved_by = None
                p.rejection_reason = None

        for field in (
            'category_id','brand_id','sku','product_name','product_description',
            'cost_price','selling_price','discount_pct','special_price',
            'special_start','special_end','active_flag'
        ):
            if field in data:
                setattr(p, field, data[field])
        db.session.commit()
        return p

    @staticmethod
    def delete(pid):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        p = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        p.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return p

    @staticmethod
    def approve(pid, admin_id):
        """Approve a product by superadmin."""
        p = Product.query.get_or_404(pid)
        p.approval_status = 'approved'
        p.approved_at = datetime.now(timezone.utc)
        p.approved_by = admin_id
        p.rejection_reason = None
        db.session.commit()
        return p

    @staticmethod
    def reject(pid, admin_id, reason):
        """Reject a product by superadmin."""
        p = Product.query.get_or_404(pid)
        p.approval_status = 'rejected'
        p.approved_at = None
        p.approved_by = None
        p.rejection_reason = reason
        db.session.commit()
        return p

    @staticmethod
    def get_pending_products():
        """Get all products pending approval."""
        return Product.query.filter_by(
            approval_status='pending',
            deleted_at=None
        ).all()

    @staticmethod
    def get_approved_products():
        """Get all approved products."""
        return Product.query.filter_by(
            approval_status='approved',
            deleted_at=None
        ).all()

    @staticmethod
    def get_rejected_products():
        """Get all rejected products."""
        return Product.query.filter_by(
            approval_status='rejected',
            deleted_at=None
        ).all()
