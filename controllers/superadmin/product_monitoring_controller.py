from datetime import datetime
from common.database import db
from models.product import Product
from models.product_media import ProductMedia
from models.product_meta import ProductMeta
from models.brand import Brand
from models.category import Category
from sqlalchemy.orm import joinedload
from sqlalchemy import and_

class ProductMonitoringController:
    @staticmethod
    def get_pending_products():
        """Get all pending parent products with their related data"""
        products = Product.query.filter(
            and_(
                Product.approval_status == 'pending',
                Product.deleted_at.is_(None),
                Product.parent_product_id.is_(None)  # Only get parent products
            )
        ).options(
            joinedload(Product.media),
            joinedload(Product.meta),
            joinedload(Product.brand),
            joinedload(Product.category)
        ).all()
        return products

    @staticmethod
    def get_approved_products():
        """Get all approved parent products with their related data"""
        products = Product.query.filter(
            and_(
                Product.approval_status == 'approved',
                Product.deleted_at.is_(None),
                Product.parent_product_id.is_(None)  # Only get parent products
            )
        ).options(
            joinedload(Product.media),
            joinedload(Product.meta),
            joinedload(Product.brand),
            joinedload(Product.category)
        ).all()
        return products

    @staticmethod
    def get_rejected_products():
        """Get all rejected parent products with their related data"""
        products = Product.query.filter(
            and_(
                Product.approval_status == 'rejected',
                Product.deleted_at.is_(None),
                Product.parent_product_id.is_(None)  # Only get parent products
            )
        ).options(
            joinedload(Product.media),
            joinedload(Product.meta),
            joinedload(Product.brand),
            joinedload(Product.category)
        ).all()
        return products

    @staticmethod
    def approve_product(product_id, admin_id):
        """Approve a parent product and its variants"""
        product = Product.query.get_or_404(product_id)
        
        # Check if this is a parent product
        if product.parent_product_id is not None:
            raise ValueError("Cannot approve a variant product directly. Please approve the parent product.")

        # Approve the parent product
        product.approval_status = 'approved'
        product.approved_at = datetime.utcnow()
        product.approved_by = admin_id
        product.rejection_reason = None

        # Find and approve all variant products
        variants = Product.query.filter_by(parent_product_id=product_id).all()
        for variant in variants:
            variant.approval_status = 'approved'
            variant.approved_at = datetime.utcnow()
            variant.approved_by = admin_id
            variant.rejection_reason = None

        db.session.commit()
        return product

    @staticmethod
    def reject_product(product_id, admin_id, reason):
        """Reject a parent product and its variants"""
        if not reason or not reason.strip():
            raise ValueError("Rejection reason is required")

        product = Product.query.get_or_404(product_id)
        
        # Check if this is a parent product
        if product.parent_product_id is not None:
            raise ValueError("Cannot reject a variant product directly. Please reject the parent product.")

        # Reject the parent product
        product.approval_status = 'rejected'
        product.approved_at = datetime.utcnow()
        product.approved_by = admin_id
        product.rejection_reason = reason.strip()

        # Find and reject all variant products
        variants = Product.query.filter_by(parent_product_id=product_id).all()
        for variant in variants:
            variant.approval_status = 'rejected'
            variant.approved_at = datetime.utcnow()
            variant.approved_by = admin_id
            variant.rejection_reason = reason.strip()

        db.session.commit()
        return product

    @staticmethod
    def get_product_details(product_id):
        """Get detailed information about a specific product and its variants"""
        product = Product.query.options(
            joinedload(Product.media),
            joinedload(Product.meta),
            joinedload(Product.brand),
            joinedload(Product.category)
        ).get_or_404(product_id)

        # Get variants if this is a parent product
        variants = []
        if product.parent_product_id is None:
            variants = Product.query.filter_by(parent_product_id=product_id).all()

        return {
            'product': {
                **product.serialize(),
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price)
            },
            'media': [media.serialize() for media in product.media] if product.media else [],
            'meta': product.meta.serialize() if product.meta else None,
            'brand': product.brand.serialize() if product.brand else None,
            'category': product.category.serialize() if product.category else None,
            'variants': [variant.serialize() for variant in variants] if variants else []
        } 