from flask import jsonify, request, current_app
from common.database import db
from auth.models.models import User, UserRole
from common.response import success_response, error_response
from common.decorators import superadmin_required
import bcrypt

def get_superadmin_profile(user_id):
    """Get superadmin profile by user ID."""
    try:
        superadmin = User.query.filter_by(
            id=user_id,
            role=UserRole.SUPER_ADMIN
        ).first()
        
        if not superadmin:
            return error_response("Superadmin not found", 404)
        
        return success_response({
            "id": superadmin.id,
            "email": superadmin.email,
            "first_name": superadmin.first_name,
            "last_name": superadmin.last_name,
            "phone": superadmin.phone,
            "profile_img": superadmin.profile_img,
            "is_active": superadmin.is_active,
            "last_login": superadmin.last_login.isoformat() if superadmin.last_login else None
        })
    except Exception as e:
        current_app.logger.error(f"Error getting superadmin profile: {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def update_superadmin_profile(user_id):
    """Update superadmin profile."""
    try:
        # Get the current user from the request context
        current_user = request.current_user
        
        # Only allow updating own profile or if current user is a superadmin
        if current_user.id != user_id:
            return error_response("You can only update your own profile", 403)
        
        superadmin = User.query.filter_by(
            id=user_id,
            role=UserRole.SUPER_ADMIN
        ).first()
        
        if not superadmin:
            return error_response("Superadmin not found", 404)
        
        data = request.get_json()
        current_app.logger.info(f"Received update data: {data}")
        
        # Update basic info
        if "first_name" in data:
            superadmin.first_name = data["first_name"]
        if "last_name" in data:
            superadmin.last_name = data["last_name"]
        if "phone" in data:
            superadmin.phone = data["phone"]
        if "profile_img" in data:
            superadmin.profile_img = data["profile_img"]
            
        # Update password if provided
        if "password" in data:
            superadmin.set_password(data["password"])
            
        # Update email if provided and not already taken
        if "email" in data and data["email"] != superadmin.email:
            existing_user = User.query.filter_by(email=data["email"]).first()
            if existing_user:
                return error_response("Email already in use", 400)
            superadmin.email = data["email"]
            superadmin.is_email_verified = False  # Require re-verification for new email
        
        try:
            db.session.commit()
            
            # Return the same structure as get_superadmin_profile
            return success_response({
                "id": superadmin.id,
                "email": superadmin.email,
                "first_name": superadmin.first_name,
                "last_name": superadmin.last_name,
                "phone": superadmin.phone,
                "profile_img": superadmin.profile_img,
                "is_active": superadmin.is_active,
                "last_login": superadmin.last_login.isoformat() if superadmin.last_login else None
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database error during update: {str(e)}")
            return error_response("Database error during update", 500)
            
    except Exception as e:
        current_app.logger.error(f"Error updating superadmin profile: {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def update_superadmin(user_id):
    """Update any superadmin user (admin-to-admin edit)."""
    try:
        superadmin = User.query.filter_by(
            id=user_id,
            role=UserRole.SUPER_ADMIN
        ).first()
        
        if not superadmin:
            return error_response("Superadmin not found", 404)
        
        data = request.get_json()
        current_app.logger.info(f"Received update data (admin edit): {data}")
        
        # Update basic info
        if "first_name" in data:
            superadmin.first_name = data["first_name"]
        if "last_name" in data:
            superadmin.last_name = data["last_name"]
        if "phone" in data:
            superadmin.phone = data["phone"]
        if "profile_img" in data:
            superadmin.profile_img = data["profile_img"]
        
        # Update password if provided
        if "password" in data:
            superadmin.set_password(data["password"])
        
        # Update email if provided and not already taken
        if "email" in data and data["email"] != superadmin.email:
            existing_user = User.query.filter_by(email=data["email"]).first()
            if existing_user:
                return error_response("Email already in use", 400)
            superadmin.email = data["email"]
            superadmin.is_email_verified = False  # Require re-verification for new email
        
        try:
            db.session.commit()
            return success_response({
                "id": superadmin.id,
                "email": superadmin.email,
                "first_name": superadmin.first_name,
                "last_name": superadmin.last_name,
                "phone": superadmin.phone,
                "profile_img": superadmin.profile_img,
                "is_active": superadmin.is_active,
                "last_login": superadmin.last_login.isoformat() if superadmin.last_login else None
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database error during update (admin edit): {str(e)}")
            return error_response("Database error during update", 500)
    except Exception as e:
        current_app.logger.error(f"Error updating superadmin (admin edit): {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def create_superadmin():
    """Create a new superadmin user."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["email", "password", "first_name", "last_name"]
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}", 400)
        
        # Check if email already exists
        if User.query.filter_by(email=data["email"]).first():
            return error_response("Email already in use", 400)
        
        # Create new superadmin user
        new_superadmin = User(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=UserRole.SUPER_ADMIN,
            phone=data.get("phone"),
            profile_img=data.get("profile_img"),
            is_active=True,
            is_email_verified=True  # Since created by another superadmin
        )
        new_superadmin.set_password(data["password"])
        
        db.session.add(new_superadmin)
        db.session.commit()
        
        return success_response({
            "message": "Superadmin created successfully",
            "user": {
                "id": new_superadmin.id,
                "email": new_superadmin.email,
                "first_name": new_superadmin.first_name,
                "last_name": new_superadmin.last_name,
                "phone": new_superadmin.phone,
                "profile_img": new_superadmin.profile_img,
                "is_active": new_superadmin.is_active
            }
        }, 201)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating superadmin: {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def get_all_superadmins():
    """Get list of all superadmin users."""
    try:
        superadmins = User.query.filter_by(role=UserRole.SUPER_ADMIN).all()
        
        return success_response({
            "superadmins": [{
                "id": admin.id,
                "email": admin.email,
                "first_name": admin.first_name,
                "last_name": admin.last_name,
                "phone": admin.phone,
                "profile_img": admin.profile_img,
                "is_active": admin.is_active,
                "last_login": admin.last_login.isoformat() if admin.last_login else None
            } for admin in superadmins]
        })
    except Exception as e:
        current_app.logger.error(f"Error getting superadmins list: {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def delete_superadmin(user_id):
    """Delete a superadmin user."""
    try:
        # Get the current user from the request context
        current_user = request.current_user
        
        # Prevent self-deletion
        if current_user.id == user_id:
            return error_response("You cannot delete your own account", 400)
        
        superadmin = User.query.filter_by(
            id=user_id,
            role=UserRole.SUPER_ADMIN
        ).first()
        
        if not superadmin:
            return error_response("Superadmin not found", 404)
        
        # Soft delete by setting is_active to False
        superadmin.is_active = False
        db.session.commit()
        
        return success_response({
            "message": "Superadmin deleted successfully",
            "user": {
                "id": superadmin.id,
                "email": superadmin.email,
                "first_name": superadmin.first_name,
                "last_name": superadmin.last_name
            }
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting superadmin: {str(e)}")
        return error_response("Internal server error", 500)

@superadmin_required
def reactivate_superadmin(user_id):
    """Reactivate a disabled superadmin user."""
    try:
        superadmin = User.query.filter_by(
            id=user_id,
            role=UserRole.SUPER_ADMIN
        ).first()
        
        if not superadmin:
            return error_response("Superadmin not found", 404)
        
        if superadmin.is_active:
            return error_response("Superadmin is already active", 400)
        
        # Reactivate by setting is_active to True
        superadmin.is_active = True
        db.session.commit()
        
        return success_response({
            "message": "Superadmin reactivated successfully",
            "user": {
                "id": superadmin.id,
                "email": superadmin.email,
                "first_name": superadmin.first_name,
                "last_name": superadmin.last_name,
                "is_active": superadmin.is_active
            }
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reactivating superadmin: {str(e)}")
        return error_response("Internal server error", 500)
