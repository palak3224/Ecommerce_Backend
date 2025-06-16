from auth.models.models import User
from sqlalchemy.exc import SQLAlchemyError
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash
from common.database import db
import logging

logger = logging.getLogger(__name__)

class MerchantSettingsController:
    @staticmethod
    def change_password(current_password, new_password):
        """
        Change the password for the currently logged-in user.
        """
        try:
            user = User.query.get(current_user.id)

            if not user:
                raise FileNotFoundError("User not found")

            if not check_password_hash(user.password, current_password):
                return {"message": "Current password is incorrect"}, 401

            user.password = generate_password_hash(new_password)
            db.session.commit()

            return {"message": "Password changed successfully"}, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while changing password: {str(e)}")
            return {"message": "Database error"}, 500
