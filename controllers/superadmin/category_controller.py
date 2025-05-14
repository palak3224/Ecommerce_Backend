from models.category import Category
from common.database import db
from sqlalchemy.exc import IntegrityError

class CategoryController:
    @staticmethod
    def list_all():
        return Category.query.filter_by(deleted_at=None).all()

    @staticmethod
    def get(category_id):
        return Category.query.get_or_404(category_id)

    @staticmethod
    def create(data):
        cat = Category(
            category_id=data['category_id'],
            name=data['name'],
            slug=data['slug'],
            parent_id=data.get('parent_id'),
            
        )
        cat.save()
        return cat

    @staticmethod
    def update(category_id, data):
        cat = Category.query.get_or_404(category_id)
        cat.name = data.get('name', cat.name)
        cat.slug = data.get('slug', cat.slug)
        cat.parent_id = data.get('parent_id', cat.parent_id)
        db.session.commit()
        return cat

    @staticmethod
    def soft_delete(category_id):
        cat = Category.query.get_or_404(category_id)
        cat.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return cat
