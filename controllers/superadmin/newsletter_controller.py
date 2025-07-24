from models.newsletter_subscription import NewsletterSubscription
from common.database import db

class NewsletterController:
    @staticmethod
    def list_all():
        """
        Return all newsletter subscriptions (all subscribers).
        """
        print("[DEBUG] NewsletterController.list_all called")
        try:
            result = NewsletterSubscription.query.order_by(NewsletterSubscription.created_at.desc()).all()
            print(f"[DEBUG] Retrieved {len(result)} newsletter subscriptions")
            return result
        except Exception as e:
            import traceback
            print("[ERROR] Exception in NewsletterController.list_all:")
            print(traceback.format_exc())
            raise
