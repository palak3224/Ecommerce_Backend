# controllers/merchant/variant_controller.py
from models.variant import Variant
from common.database import db
from flask import current_app
from sqlalchemy.exc import IntegrityError 

class MerchantVariantController:
    @staticmethod
    def list(pid):
        return Variant.query.filter_by(product_id=pid, deleted_at=None).all()

    @staticmethod
    def create(pid, data):
        if not data.get('attribute') or not data.get('sku'):
            raise ValueError("Attribute and SKU are required for a variant.")
        
        try:
            v = Variant(product_id=pid, **data) 
            db.session.add(v)
            db.session.commit()
            return v
        except IntegrityError as e:
            db.session.rollback()
            if "UNIQUE constraint failed: variants.sku" in str(e.orig) or \
               (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'): 
                raise ValueError(f"SKU '{data.get('sku')}' already exists.")
            raise 

    @staticmethod
    def update(vid, data):
        v = Variant.query.filter_by(variant_id=vid, deleted_at=None).first_or_404(
             description=f"Variant with ID {vid} not found or has been deleted."
        )

        for key, value in data.items():
            if hasattr(v, key):
                setattr(v, key, value)
            else:
                current_app.logger.warning(f"Unexpected key '{key}' in variant update data for variant ID {vid}")
        
        try:
            db.session.commit()
            return v
        except IntegrityError as e: 
            db.session.rollback()
            if "UNIQUE constraint failed: variants.sku" in str(e.orig) or \
               (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'):
                raise ValueError(f"Update failed: SKU '{data.get('sku')}' already exists.")
            raise

    @staticmethod
    def delete(vid):
        v = Variant.query.filter_by(variant_id=vid, deleted_at=None).first_or_404(
             description=f"Variant with ID {vid} not found or has been deleted."
        )
       
        from datetime import datetime, timezone 
        v.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return v