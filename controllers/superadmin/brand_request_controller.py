from models.brand_request import BrandRequest, BrandRequestStatus
from models.brand import Brand
from common.database import db
from datetime import datetime

class BrandRequestController:
    @staticmethod
    def list_pending():
        return BrandRequest.query.filter_by(status=BrandRequestStatus.PENDING).all()

    @staticmethod
    def approve(request_id, reviewer_id):
        br = BrandRequest.query.get_or_404(request_id)
        br.status = BrandRequestStatus.APPROVED
        br.reviewer_id = reviewer_id
        br.reviewed_at = datetime.utcnow()
        br.save()
        # Auto‑create Brand
        Brand(
            name=br.name,
            slug=br.name.lower().replace(" ", "-"),
            approved_by=reviewer_id,
            approved_at=br.reviewed_at
        ).save()
        return br

    @staticmethod
    def reject(request_id, reviewer_id, notes=None):
        br = BrandRequest.query.get_or_404(request_id)
        br.status = BrandRequestStatus.REJECTED
        br.reviewer_id = reviewer_id
        br.reviewed_at = datetime.utcnow()
        br.verification_notes = notes
        br.save()
        return br
