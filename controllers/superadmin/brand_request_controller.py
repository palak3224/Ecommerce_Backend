# controllers/superadmin/brand_request_controller.py
from models.brand_request import BrandRequest, BrandRequestStatus
from models.brand import Brand
from common.database import db
from datetime import datetime, timezone
import re
from sqlalchemy.exc import IntegrityError

class BrandRequestController:
    @staticmethod
    def list_pending():
        return BrandRequest.query.filter_by(status=BrandRequestStatus.PENDING, deleted_at=None).all()

    @staticmethod
    def approve(request_id_from_route, reviewer_id, icon_url=None): 
        br = BrandRequest.query.filter_by(
            request_id=request_id_from_route,  
            status=BrandRequestStatus.PENDING,
            deleted_at=None
        ).first_or_404(description=f"Brand request ID {request_id_from_route} not found or not pending.")

        br.status = BrandRequestStatus.APPROVED
        br.reviewer_id = reviewer_id
        br.reviewed_at = datetime.now(timezone.utc)
        db.session.add(br)

        base_slug = br.name.lower()
        base_slug = re.sub(r'\s+', '-', base_slug)
        base_slug = re.sub(r'[^a-z0-9-]', '', base_slug)
        base_slug = re.sub(r'-+', '-', base_slug).strip('-')

        if not base_slug:
           
            base_slug = f"brand-{br.request_id}" 
        
        slug = base_slug
        counter = 1
        while Brand.query.filter_by(slug=slug, deleted_at=None).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                raise Exception(f"Could not generate a unique slug for brand name: {br.name} after 100 attempts.")

        new_brand = Brand(
            name=br.name,
            slug=slug,
            icon_url=icon_url,
            approved_by=reviewer_id,
            approved_at=br.reviewed_at
        )
        db.session.add(new_brand)

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            raise IntegrityError(f"Failed to approve brand request due to a data conflict (e.g., slug '{slug}' already exists).", e.params, e.orig) from e
            
        return br

    @staticmethod
    def reject(request_id_from_route, reviewer_id, notes=None): 
        br = BrandRequest.query.filter_by(
            request_id=request_id_from_route,  
            status=BrandRequestStatus.PENDING,
            deleted_at=None
        ).first_or_404(description=f"Brand request ID {request_id_from_route} not found or not pending.")

        br.status = BrandRequestStatus.REJECTED
        br.reviewer_id = reviewer_id
        br.reviewed_at = datetime.now(timezone.utc)
        br.verification_notes = notes
        db.session.add(br)
        db.session.commit()
        return br