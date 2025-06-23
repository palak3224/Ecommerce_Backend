from auth.models.models import User, MerchantProfile
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
            logger.debug("Starting password change process")
            user_id = get_jwt_identity()
            logger.debug(f"User ID from JWT: {user_id}")
            
            user = User.query.get(user_id)
            logger.debug(f"Found user: {user is not None}")

            if not user:
                logger.error("User not found")
                return {"message": "User not found"}, 404

            logger.debug("Checking current password")
            if not user.check_password(current_password):
                logger.error("Current password is incorrect")
                return {"message": "Current password is incorrect"}, 401

            logger.debug("Setting new password")
            user.set_password(new_password)
            
            logger.debug("Committing changes to database")
            db.session.commit()
            logger.debug("Password change successful")

            return {"message": "Password changed successfully"}, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while changing password: {str(e)}")
            db.session.rollback()
            return {"message": "Database error"}, 500
        except Exception as e:
            logger.error(f"Unexpected error while changing password: {str(e)}")
            db.session.rollback()
            return {"message": f"Unexpected error: {str(e)}"}, 500
        

    @staticmethod
    def get_account_settings():
        """
        Fetch account and bank details for the currently logged-in merchant.
        """
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            merchant = MerchantProfile.get_by_user_id(user_id)

            if not user:
                return {"message": "User not found"}, 404

            if not merchant:
                return {"message": "Merchant profile not found"}, 404

            return {
                "account_details": {
                    "email": user.email,
                    "phone": user.phone
                },
                "bank_details": {
                    "account_name": merchant.business_name,
                    "account_number": merchant.bank_account_number,
                    "ifsc_code": merchant.bank_ifsc_code,
                    "bank_name": merchant.bank_name,
                    "branch_name": merchant.bank_branch
                }
            }, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while fetching account settings: {str(e)}")
            return {"message": "Error fetching account data"}, 500

    @staticmethod
    def update_account_settings(account_data):
        """
        Update account details for the currently logged-in merchant.
        
        Args:
            account_data (dict): Dictionary containing account details to update
                - email (str): New email address
                - phone (str): New phone number
                - account_name (str): Business name
                - account_number (str): Bank account number
                - ifsc_code (str): IFSC code
                - bank_name (str): Bank name
                - branch_name (str): Bank branch name
        """
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            merchant = MerchantProfile.get_by_user_id(user_id)

            if not user:
                return {"message": "User not found"}, 404

            if not merchant:
                return {"message": "Merchant profile not found"}, 404

            # Update user details
            if 'email' in account_data and account_data['email']:
                # Check if email is already taken by another user
                existing_user = User.get_by_email(account_data['email'])
                if existing_user and existing_user.id != user_id:
                    return {"message": "Email already exists"}, 400
                user.email = account_data['email']

            if 'phone' in account_data and account_data['phone']:
                user.phone = account_data['phone']

            # Update merchant profile details
            if 'account_name' in account_data and account_data['account_name']:
                merchant.business_name = account_data['account_name']

            if 'account_number' in account_data and account_data['account_number']:
                merchant.bank_account_number = account_data['account_number']

            if 'ifsc_code' in account_data and account_data['ifsc_code']:
                merchant.bank_ifsc_code = account_data['ifsc_code']

            if 'bank_name' in account_data and account_data['bank_name']:
                merchant.bank_name = account_data['bank_name']

            if 'branch_name' in account_data and account_data['branch_name']:
                merchant.bank_branch = account_data['branch_name']

            db.session.commit()

            return {"message": "Account settings updated successfully"}, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while updating account settings: {str(e)}")
            db.session.rollback()
            return {"message": "Error updating account data"}, 500

    @staticmethod
    def get_user_info():
        """
        Get basic user information for the currently logged-in user.
        """
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            if not user:
                return {"message": "User not found"}, 404

            return {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "role": user.role.value,
                "is_email_verified": user.is_email_verified,
                "is_phone_verified": user.is_phone_verified,
                "is_active": user.is_active
            }, 200

        except SQLAlchemyError as e:
            logger.error(f"Database error while fetching user info: {str(e)}")
            return {"message": "Error fetching user data"}, 500
