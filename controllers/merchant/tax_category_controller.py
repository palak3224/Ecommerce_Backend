from flask import current_app
from models.tax_category import TaxCategory

class MerchantTaxCategoryController:
    @staticmethod
    def list_all():
        """Lists all tax categories available to merchants."""
        try:
            categories = TaxCategory.query.order_by(TaxCategory.name).all()
            return [category.serialize() for category in categories]
        except Exception as e:
            current_app.logger.error(f"Error listing tax categories: {e}")
            raise 