from models.product_shipping import ProductShipping
from common.database import db

class MerchantProductShippingController:
    @staticmethod
    def get(pid):
        return ProductShipping.query.get_or_404(pid)

    @staticmethod
    def upsert(pid, data):
        # Transform the data to match model field names
        transformed_data = {
            'weight_kg': data.get('weight'),
            'length_cm': data.get('dimensions', {}).get('length'),
            'width_cm': data.get('dimensions', {}).get('width'),
            'height_cm': data.get('dimensions', {}).get('height')
        }
        
        ship = ProductShipping.query.get(pid)
        if not ship:
            ship = ProductShipping(product_id=pid, **transformed_data)
            db.session.add(ship)
        else:
            for k, v in transformed_data.items():
                if v is not None:  # Only update if value is provided
                    setattr(ship, k, v)
        db.session.commit()
        return ship
