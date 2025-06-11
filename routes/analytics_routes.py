from flask import Blueprint, request, jsonify
from models.visit_tracking import VisitTracking
from common.database import db
from datetime import datetime, timezone

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/track-visit', methods=['POST'])
def track_visit():
    """
    Track a new website visit.
    ---
    tags:
      - Analytics
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            session_id:
              type: string
              description: Unique session identifier.
            ip_address:
              type: string
              description: Visitor's IP address.
            landing_page:
              type: string
              description: Landing page URL.
            user_agent:
              type: string
              description: User agent string.
            referrer_url:
              type: string
              description: Referrer URL.
            device_type:
              type: string
              description: Device type.
            browser:
              type: string
              description: Browser name.
            os:
              type: string
              description: Operating system.
    responses:
      201:
        description: Visit tracked successfully.
      500:
        description: Internal server error.
    """
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
    """
    Update an existing website visit with exit page and time spent.
    ---
    tags:
      - Analytics
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            session_id:
              type: string
              description: Unique session identifier.
            exited_page:
              type: string
              description: Last page visited before exit.
            time_spent:
              type: number
              description: Time spent on the site (in seconds).
    responses:
      200:
        description: Visit updated successfully.
      404:
        description: Visit not found.
      500:
        description: Internal server error.
    """
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
    """
    Mark a website visit as converted and link it to a user.
    ---
    tags:
      - Analytics
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            session_id:
              type: string
              description: Unique session identifier.
            user_id:
              type: integer
              description: ID of the user who converted.
    responses:
      200:
        description: Visit marked as converted successfully.
      404:
        description: Visit not found.
      500:
        description: Internal server error.
    """
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