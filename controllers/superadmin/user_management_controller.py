from flask import jsonify, request
from auth.models.models import User, UserRole
from common.database import db
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

def get_all_users():
    try:
        # Get query parameters
        search = request.args.get('search', '')
        role_filter = request.args.get('role', 'All')
        
        # Base query
        query = User.query
        
        # Apply search filter if provided
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone.ilike(search_term)  # Add phone number to search
                )
            )
        
        # Apply role filter if not 'All'
        if role_filter != 'All':
            try:
                role_enum = UserRole[role_filter.upper()]
                query = query.filter(User.role == role_enum)
            except KeyError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid role filter'
                }), 400
        
        # Execute query
        users = query.all()
        
        # Format response
        user_list = []
        for user in users:
            user_data = {
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'phone': user.phone or 'Not provided',  # Add phone directly in main object
                'role': user.role.value,
                'status': 'Active' if user.is_active else 'Inactive',
                'profile': {
                    'is_email_verified': user.is_email_verified,
                    'is_phone_verified': user.is_phone_verified,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            }
            user_list.append(user_data)
        
        return jsonify({
            'status': 'success',
            'data': user_list
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def update_user_status(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        new_status = data.get('status')
        
        if not new_status or new_status not in ['Active', 'Inactive']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid status value'
            }), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        user.is_active = new_status == 'Active'
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'User status updated to {new_status}',
            'data': {
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'phone': user.phone or 'Not provided',
                'status': 'Active' if user.is_active else 'Inactive'
            }
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_user_profile(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        profile_data = {
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'phone': user.phone or 'Not provided',  # Add phone directly in main object
            'role': user.role.value,
            'status': 'Active' if user.is_active else 'Inactive',
            'profile': {
                'is_email_verified': user.is_email_verified,
                'is_phone_verified': user.is_phone_verified,
                'auth_provider': user.auth_provider.value,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': profile_data
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 