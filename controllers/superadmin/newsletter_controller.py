from flask import request, jsonify
from datetime import datetime, timezone
from models.newsletter_subscription import NewsletterSubscription
from common.database import db

def subscribe_email():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    existing = NewsletterSubscription.query.filter_by(email=email).first()
    if existing:
        return jsonify({'message': 'Email already subscribed'}), 200

    new_sub = NewsletterSubscription(
        email=email,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(new_sub)
    db.session.commit()

    return jsonify({'message': 'Subscription successful'}), 201

def list_subscribers():
    subs = NewsletterSubscription.query.order_by(NewsletterSubscription.created_at.desc()).all()
    return jsonify([{
        "id": sub.id,
        "email": sub.email,
        "subscribed_at": sub.created_at.isoformat()
    } for sub in subs])
