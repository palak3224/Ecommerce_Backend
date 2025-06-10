from datetime import datetime
from sqlalchemy import func, and_, or_
from common.database import db
from models.review import Review
from models.product import Product
from auth.models.models import MerchantProfile

class MerchantReviewController:
    @staticmethod
    def get_merchant_product_reviews(merchant_id, page=1, per_page=10, filters=None):
        """
        Get all reviews for products owned by a merchant with filtering options
        """
        try:
            # Base query to get reviews for merchant's products
            query = Review.query.join(Product).filter(Product.merchant_id == merchant_id)

            # Apply filters if provided
            if filters:
                # Filter by rating
                if 'rating' in filters:
                    query = query.filter(Review.rating == filters['rating'])
                
                # Filter by date range
                if 'start_date' in filters:
                    query = query.filter(Review.created_at >= filters['start_date'])
                if 'end_date' in filters:
                    query = query.filter(Review.created_at <= filters['end_date'])
                
                # Filter by product
                if 'product_id' in filters:
                    query = query.filter(Review.product_id == filters['product_id'])
                
                # Filter by has_images
                if 'has_images' in filters:
                    if filters['has_images']:
                        query = query.filter(Review.images.any())
                    else:
                        query = query.filter(~Review.images.any())

            # Get total count before pagination
            total_reviews = query.count()

            # Apply pagination
            reviews = query.order_by(Review.created_at.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

            # Calculate average rating
            avg_rating = db.session.query(func.avg(Review.rating))\
                .join(Product)\
                .filter(Product.merchant_id == merchant_id)\
                .scalar() or 0

            # Get rating distribution
            rating_distribution = db.session.query(
                Review.rating,
                func.count(Review.review_id)
            ).join(Product)\
            .filter(Product.merchant_id == merchant_id)\
            .group_by(Review.rating)\
            .all()

            # Format rating distribution
            rating_dist = {str(i): 0 for i in range(1, 6)}
            for rating, count in rating_distribution:
                rating_dist[str(rating)] = count

            return {
                'reviews': [review.serialize() for review in reviews],
                'pagination': {
                    'total': total_reviews,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total_reviews + per_page - 1) // per_page
                },
                'stats': {
                    'average_rating': round(float(avg_rating), 1),
                    'total_reviews': total_reviews,
                    'rating_distribution': rating_dist
                }
            }

        except Exception as e:
            raise Exception(f"Error getting merchant product reviews: {str(e)}")

    @staticmethod
    def get_product_review_stats(merchant_id, product_id=None):
        """
        Get review statistics for merchant's products
        """
        try:
            # Base query for merchant's products
            query = Product.query.filter(Product.merchant_id == merchant_id)
            
            if product_id:
                query = query.filter(Product.product_id == product_id)

            # Get all products
            products = query.all()
            
            stats = []
            for product in products:
                # Get review stats for each product
                product_stats = db.session.query(
                    func.avg(Review.rating).label('average_rating'),
                    func.count(Review.review_id).label('total_reviews')
                ).filter(Review.product_id == product.product_id).first()

                # Get rating distribution
                rating_distribution = db.session.query(
                    Review.rating,
                    func.count(Review.review_id)
                ).filter(Review.product_id == product.product_id)\
                .group_by(Review.rating)\
                .all()

                # Format rating distribution
                rating_dist = {str(i): 0 for i in range(1, 6)}
                for rating, count in rating_distribution:
                    rating_dist[str(rating)] = count

                stats.append({
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'average_rating': round(float(product_stats.average_rating or 0), 1),
                    'total_reviews': product_stats.total_reviews,
                    'rating_distribution': rating_dist
                })

            return stats

        except Exception as e:
            raise Exception(f"Error getting product review stats: {str(e)}")

    @staticmethod
    def get_recent_reviews(merchant_id, limit=5):
        """
        Get most recent reviews for merchant's products
        """
        try:
            reviews = Review.query.join(Product)\
                .filter(Product.merchant_id == merchant_id)\
                .order_by(Review.created_at.desc())\
                .limit(limit)\
                .all()

            return [review.serialize() for review in reviews]

        except Exception as e:
            raise Exception(f"Error getting recent reviews: {str(e)}") 