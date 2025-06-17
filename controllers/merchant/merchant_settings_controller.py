from auth.models.models import User
from sqlalchemy.exc import SQLAlchemyError
from flask_jwt_extended import get_jwt_identity
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
            user_id = get_jwt_identity()  # Get user ID from JWT token
            user = User.query.get(user_id)

            if not user:
                return {"message": "User not found"}, 404

            if not check_password_hash(user.password, current_password):
                return {"message": "Current password is incorrect"}, 401

            user.password = generate_password_hash(new_password)
            db.session.commit()

            return {"message": "Password changed successfully"}, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while changing password: {str(e)}")
            return {"message": "Database error"}, 500
