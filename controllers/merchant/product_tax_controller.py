from models.product_tax import ProductTax
from common.database import db

class MerchantProductTaxController:
    @staticmethod
    def get(pid):
        return ProductTax.query.get_or_404(pid)

    @staticmethod
    def upsert(pid, data):
        tax = ProductTax.query.get(pid)
        if not tax:
            tax = ProductTax(product_id=pid, tax_rate=data['tax_rate'])
            db.session.add(tax)
        else:
            tax.tax_rate = data['tax_rate']
        db.session.commit()
        return tax
