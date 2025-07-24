from flask import Blueprint, request
from controllers.newsletter_public_controller import subscribe_newsletter

newsletter_public_routes_bp = Blueprint('newsletter_public_routes', __name__)

@newsletter_public_routes_bp.route('/newsletter/subscribe', methods=['POST'])
def subscribe():
    return subscribe_newsletter() 