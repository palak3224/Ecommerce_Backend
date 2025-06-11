from flask import Blueprint, request, jsonify
from models.visit_tracking import VisitTracking
from common.database import db
from datetime import datetime, timezone

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/track-visit', methods=['POST'])
def track_visit():
    try:
        data = request.get_json()
        
        # Create new visit record
        visit = VisitTracking.create_visit(
            session_id=data['session_id'],
            ip_address=data['ip_address'],
            landing_page=data['landing_page'],
            user_agent=data['user_agent']
        )
        
        # Set additional fields
        visit.referrer_url = data.get('referrer_url')
        visit.device_type = data.get('device_type')
        visit.browser = data.get('browser')
        visit.os = data.get('os')
        
        db.session.add(visit)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Visit tracked successfully',
            'visit_id': visit.visit_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@analytics_bp.route('/update-visit', methods=['POST'])
def update_visit():
    try:
        data = request.get_json()
        session_id = data['session_id']
        
        # Find the visit record
        visit = VisitTracking.query.filter_by(session_id=session_id).first()
        if not visit:
            return jsonify({
                'status': 'error',
                'message': 'Visit not found'
            }), 404
        
        # Update visit data
        visit.update_exit(
            exited_page=data['exited_page'],
            time_spent=data['time_spent']
        )
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Visit updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@analytics_bp.route('/mark-converted', methods=['POST'])
def mark_converted():
    try:
        data = request.get_json()
        session_id = data['session_id']
        user_id = data['user_id']
        
        # Find the visit record
        visit = VisitTracking.query.filter_by(session_id=session_id).first()
        if not visit:
            return jsonify({
                'status': 'error',
                'message': 'Visit not found'
            }), 404
        
        # Mark as converted and link to user
        visit.mark_converted()
        visit.user_id = user_id
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Visit marked as converted'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 