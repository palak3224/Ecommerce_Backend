
from models.brand import Brand
from common.database import db
from datetime import datetime, timezone 

class BrandController:
    @staticmethod
    def list_all():
        return Brand.query.filter_by(deleted_at=None).all()

    @staticmethod
    def get(brand_pk_id): 
       
        brand = Brand.query.filter_by(brand_id=brand_pk_id, deleted_at=None).first_or_404(
            description=f"Brand with ID {brand_pk_id} not found or has been deleted."
        )
        return brand

    @staticmethod
    def create(data):
        brand = Brand(
            name=data['name'],
            slug=data['slug'],
            icon_url=data.get('icon_url'),
            approved_by=data.get('approved_by'),
            approved_at=data.get('approved_at')
        )
        db.session.add(brand)
        db.session.commit()
        return brand

    @staticmethod
    def update(brand_pk_id, data): 
       
        brand = Brand.query.filter_by(brand_id=brand_pk_id, deleted_at=None).first_or_404(
            description=f"Brand with ID {brand_pk_id} not found or has been deleted for update."
        )

        brand.name = data.get('name', brand.name)
        brand.slug = data.get('slug', brand.slug)
        brand.icon_url = data.get('icon_url', brand.icon_url)
        
      
        if 'approved_by' in data: 
            brand.approved_by = data.get('approved_by')
        if 'approved_at' in data:
            brand.approved_at = data.get('approved_at')
        
       
        db.session.commit()
        return brand

    @staticmethod
    def delete(brand_pk_id): 
       
        b = Brand.query.filter_by(brand_id=brand_pk_id, deleted_at=None).first_or_404(
            description=f"Brand with ID {brand_pk_id} not found or has been deleted."
        )
        b.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return b
    @staticmethod
    def undelete(brand_pk_id):
        
        brand = Brand.query.filter_by(brand_id=brand_pk_id).first_or_404(
            description=f"Brand with ID {brand_pk_id} not found (cannot undelete)."
        )
        if brand.deleted_at is None:
            pass 
        brand.deleted_at = None
        brand.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return brand