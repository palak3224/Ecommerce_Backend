import logging
from flask import current_app
from common.database import db
from werkzeug.exceptions import BadRequest
import cloudinary
import cloudinary.uploader

from models.enums import OrderStatusEnum
from models.shop.shop_order import ShopOrder, ShopOrderItem
from models.shop.shop_product import ShopProduct
from models.shop.shop_review import ShopReview, ShopReviewImage

logger = logging.getLogger(__name__)


class ShopReviewController:
    @staticmethod
    def create_review(user_id: int, review_data: dict):
        try:
            required = ['shop_order_id', 'shop_product_id', 'rating', 'title', 'body']
            missing = [f for f in required if f not in review_data]
            if missing:
                raise BadRequest(f"Missing required fields: {', '.join(missing)}")

            rating = review_data.get('rating')
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                raise BadRequest('Rating must be an integer between 1 and 5')

            # Validate order belongs to user
            order: ShopOrder | None = ShopOrder.query.filter_by(order_id=review_data['shop_order_id'], user_id=user_id).first()
            if not order:
                raise BadRequest('Shop order not found or does not belong to user')
            # Delivery gating: allow if order delivered OR the specific item is delivered

            # Validate product exists and is in the order
            product: ShopProduct | None = ShopProduct.query.filter_by(product_id=review_data['shop_product_id']).first()
            if not product:
                raise BadRequest('Shop product not found')

            order_item = ShopOrderItem.query.filter_by(order_id=order.order_id, product_id=product.product_id).first()
            if not order_item:
                raise BadRequest('Product not found in this order')

            if order.order_status != OrderStatusEnum.DELIVERED:
                raise BadRequest('You can only review after delivery')

            # Prevent duplicate review per order/product
            dup = ShopReview.query.filter_by(shop_order_id=order.order_id, shop_product_id=product.product_id, user_id=user_id).first()
            if dup:
                raise BadRequest('You have already reviewed this product for this order')

            review = ShopReview(
                user_id=user_id,
                shop_product_id=product.product_id,
                shop_order_id=order.order_id,
                rating=rating,
                title=review_data.get('title', ''),
                body=review_data.get('body', ''),
            )
            review.save()

            # Images
            images = review_data.get('images')
            if images:
                if not isinstance(images, list):
                    raise BadRequest('Images must be a list')
                if len(images) > 5:
                    raise BadRequest('Maximum 5 images allowed per review')
                for idx, img_data in enumerate(images):
                    try:
                        upload = cloudinary.uploader.upload(
                            img_data,
                            folder=f"shop-reviews/{review.review_id}",
                            public_id=f"review_image_{idx}",
                            resource_type="image",
                        )
                        if upload:
                            ri = ShopReviewImage(
                                review_id=review.review_id,
                                image_url=upload['secure_url'],
                                public_id=upload['public_id'],
                                sort_order=idx,
                            )
                            db.session.add(ri)
                    except Exception as e:
                        current_app.logger.error(f"Failed to upload shop review image: {e}")
                        continue

            db.session.commit()
            data = review.serialize(include_images=True)
            return data
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating shop review: {e}")
            raise

    @staticmethod
    def get_product_reviews(shop_product_id: int, page: int = 1, per_page: int = 10):
        try:
            pagination = ShopReview.query.filter_by(shop_product_id=shop_product_id).order_by(ShopReview.created_at.desc()).paginate(page=page, per_page=per_page)
            total = ShopReview.query.filter_by(shop_product_id=shop_product_id).count()

            reviews = []
            for r in pagination.items:
                d = r.serialize(include_images=True)
                reviews.append(d)

            return {
                'reviews': reviews,
                'total': total,
                'pages': pagination.pages,
                'current_page': pagination.page,
            }
        except Exception as e:
            logger.error(f"Error getting shop product reviews: {e}")
            raise

    @staticmethod
    def get_user_reviews(user_id: int, page: int = 1, per_page: int = 10):
        try:
            pagination = ShopReview.query.filter_by(user_id=user_id).order_by(ShopReview.created_at.desc()).paginate(page=page, per_page=per_page)
            total = ShopReview.query.filter_by(user_id=user_id).count()

            return {
                'reviews': [r.serialize(include_images=True) for r in pagination.items],
                'total': total,
                'pages': pagination.pages,
                'current_page': pagination.page,
            }
        except Exception as e:
            logger.error(f"Error getting user shop reviews: {e}")
            raise

    @staticmethod
    def delete_review(review_id: int, user_id: int):
        try:
            review = ShopReview.query.filter_by(review_id=review_id, user_id=user_id).first()
            if not review:
                raise BadRequest('Review not found or does not belong to user')

            for image in review.images:
                if getattr(image, 'public_id', None):
                    try:
                        cloudinary.uploader.destroy(image.public_id, resource_type="image")
                    except Exception as e:
                        current_app.logger.error(f"Failed to delete image {image.public_id} from Cloudinary: {e}")

            db.session.delete(review)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting shop review: {e}")
            raise
