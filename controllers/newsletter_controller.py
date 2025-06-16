from flask import Blueprint, request, jsonify
from common.database import db
from models.newsletter_subscription import NewsletterSubscription
from datetime import datetime, timezone

newsletter_bp = Blueprint('newsletter_bp', __name__)

@newsletter_bp.route('/api/subscribe', methods=['POST'])
def subscribe_email():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"message": "Email is required"}), 400

    existing = NewsletterSubscription.query.filter_by(email=email).first()
    if existing:
        return jsonify({"message": "Email already subscribed"}), 200

    new_entry = NewsletterSubscription(
        email=email,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"message": "Subscription successful"}), 201
