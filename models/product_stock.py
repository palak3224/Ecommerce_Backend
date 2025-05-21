from common.database import db
from models.product import Product

class ProductStock(db.Model):
    __tablename__ = 'product_stock'

    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), primary_key=True)
    stock_qty = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=0)

    # Relationship
    product = db.relationship('Product', backref=db.backref('stock', uselist=False))

    def serialize(self):
        return {
            'product_id': self.product_id,
            'stock_qty': self.stock_qty,
            'low_stock_threshold': self.low_stock_threshold
        } 