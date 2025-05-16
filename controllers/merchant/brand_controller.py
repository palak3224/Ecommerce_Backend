from models.brand import Brand

class MerchantBrandController:
    @staticmethod
    def list_all():
       
        return Brand.query.filter_by(deleted_at=None).all()
