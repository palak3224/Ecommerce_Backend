from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from models.holi_giveaway_registration import HoliGiveawayRegistration
from common.database import db

holi_giveaway_bp = Blueprint('holi_giveaway', __name__)


@holi_giveaway_bp.route('/register', methods=['POST', 'OPTIONS'])
@cross_origin()
def register():
    """Register a participant for the Holi giveaway (name + phone)."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip().replace(' ', '')

    if not name:
        return jsonify({'success': False, 'message': 'Name is required.'}), 400
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number is required.'}), 400
    if len(phone) != 10 or not phone.isdigit():
        return jsonify({'success': False, 'message': 'Enter a valid 10-digit phone number.'}), 400

    try:
        registration = HoliGiveawayRegistration(name=name, phone=phone)
        db.session.add(registration)
        db.session.commit()
        db.session.refresh(registration)  # load created_at from DB
        return jsonify({
            'success': True,
            'message': "You're registered!",
            'registration': registration.to_dict(),
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500


@holi_giveaway_bp.route('/registrations', methods=['GET', 'OPTIONS'])
@cross_origin()
def list_registrations():
    """List all Holi giveaway registrations (newest first)."""
    if request.method == 'OPTIONS':
        return '', 200

    try:
        rows = HoliGiveawayRegistration.query.order_by(
            HoliGiveawayRegistration.created_at.desc()
        ).all()
        return jsonify([r.to_dict() for r in rows]), 200
    except Exception as e:
        return jsonify({'message': 'Failed to fetch registrations.'}), 500
