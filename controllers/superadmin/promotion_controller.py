from models.promotion import Promotion
from common.database import db

class PromotionController:
    @staticmethod
    def list_all():
        return Promotion.query.filter_by(deleted_at=None).all()

    @staticmethod
    def create(data):
        promo = Promotion(
            code=data['code'],
            description=data.get('description'),
            discount_type=data['discount_type'],
            discount_value=data['discount_value'],
            start_date=data['start_date'],
            end_date=data['end_date']
        )
        promo.save()
        return promo

    @staticmethod
    def update(promo_id, data):
        p = Promotion.query.get_or_404(promo_id)
        for field in ('description','discount_type','discount_value','start_date','end_date'):
            if field in data:
                setattr(p, field, data[field])
        db.session.commit()
        return p

    @staticmethod
    def soft_delete(promo_id):
        p = Promotion.query.get_or_404(promo_id)
        p.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return p
