from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound, Forbidden
from marshmallow import Schema, fields, validate, ValidationError

from controllers.merchant.merchant_support_controller import MerchantSupportTicketController
from auth.utils import merchant_role_required 
from auth.models import User, MerchantProfile 
from models.enums import TicketPriority, TicketStatus  

merchant_support_bp = Blueprint('merchant_support_bp', __name__, url_prefix='/api/merchant-dashboard/support') # Changed prefix for clarity

# --- Schemas for Request Validation ---
class CreateMerchantTicketSchema(Schema): # Renamed for clarity
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(required=True, validate=validate.Length(min=1))
    priority = fields.Str(validate=validate.OneOf([p.value for p in TicketPriority]), load_default=TicketPriority.MEDIUM.value)
    related_order_id = fields.Str(required=False, allow_none=True)
    related_product_id = fields.Int(required=False, allow_none=True)
    # image_file will be handled as form-data

class AddMerchantMessageSchema(Schema): # Renamed for clarity
    message_text = fields.Str(validate=validate.Length(min=1))
    # attachment_file will be handled as form-data

# --- Merchant Support Ticket Routes ---

@merchant_support_bp.route('/tickets', methods=['POST'])
@merchant_role_required 
def create_merchant_ticket_route():
    """
    Create a new support ticket as a merchant.
    ---
    tags:
      - Merchant Support
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - name: title
        in: formData
        type: string
        required: true
        description: Title of the support ticket.
      - name: description
        in: formData
        type: string
        required: true
        description: Description of the issue.
      - name: priority
        in: formData
        type: string
        required: false
        description: Priority of the ticket (low, medium, high).
      - name: related_order_id
        in: formData
        type: string
        required: false
        description: Related order ID, if applicable.
      - name: related_product_id
        in: formData
        type: integer
        required: false
        description: Related product ID, if applicable.
      - name: image_file
        in: formData
        type: file
        required: false
        description: Optional image attachment.
    responses:
      201:
        description: Support ticket created successfully.
      400:
        description: Validation failed.
      401:
        description: Unauthorized.
      404:
        description: Merchant profile not found.
      500:
        description: Internal server error.
    """
    current_user_id_from_jwt = get_jwt_identity() # This is the User.id
    
    # Find the MerchantProfile associated with this User
    merchant_profile = MerchantProfile.query.filter_by(user_id=current_user_id_from_jwt).first_or_404(
        description="Merchant profile not found for the logged-in user."
    )
    
    form_data = request.form.to_dict()
    image_file = request.files.get('image_file')

    try:
        schema = CreateMerchantTicketSchema()
        validated_data = schema.load(form_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400

    try:
        ticket = MerchantSupportTicketController.create_ticket(
            data=validated_data, 
            merchant_id=merchant_profile.id, # Pass the MerchantProfile.id
            creator_user_id=current_user_id_from_jwt, # Pass the User.id as creator
            image_file=image_file
        )
        return jsonify(ticket.serialize(user_role='MERCHANT')), 201 # Pass user_role to serialize if needed
    except (BadRequest, NotFound, Forbidden) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error creating merchant support ticket: {e}")
        return jsonify({"error": "Failed to create support ticket"}), 500

@merchant_support_bp.route('/tickets', methods=['GET'])
@merchant_role_required
def list_merchant_tickets_route():
    """
    List all support tickets for the current merchant.
    ---
    tags:
      - Merchant Support
    security:
      - Bearer: []
    parameters:
      - name: status
        in: query
        type: string
        required: false
        description: Filter tickets by status.
      - name: sort_by
        in: query
        type: string
        required: false
        description: "Sort order (default: -updated_at)."
      - name: page
        in: query
        type: integer
        required: false
        description: Page number for pagination.
      - name: per_page
        in: query
        type: integer
        required: false
        description: Number of tickets per page.
    responses:
      200:
        description: List of merchant support tickets retrieved successfully.
      400:
        description: Validation failed.
      401:
        description: Unauthorized.
      404:
        description: Merchant profile not found.
      500:
        description: Internal server error.
    """
    current_user_id = get_jwt_identity()
    merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first_or_404(
        description="Merchant profile not found for current user."
    )

    status_filter = request.args.get('status')
    sort_by = request.args.get('sort_by', '-updated_at')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        paginated_tickets = MerchantSupportTicketController.list_merchant_tickets(
            merchant_id=merchant.id,
            status_filter=status_filter,
            sort_by=sort_by,
            page=page,
            per_page=per_page
        )
        return jsonify({
            "tickets": [ticket.serialize(user_role='MERCHANT') for ticket in paginated_tickets.items],
            "total": paginated_tickets.total,
            "pages": paginated_tickets.pages,
            "current_page": paginated_tickets.page,
            "per_page": paginated_tickets.per_page
        }), 200
    except (BadRequest) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error listing merchant tickets: {e}")
        return jsonify({"error": "Failed to retrieve tickets"}), 500

@merchant_support_bp.route('/tickets/<string:ticket_uid>', methods=['GET'])
@merchant_role_required
def get_merchant_ticket_route(ticket_uid):
    """
    Get details of a specific support ticket for the current merchant.
    ---
    tags:
      - Merchant Support
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
    responses:
      200:
        description: Ticket details retrieved successfully.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    current_user_id = get_jwt_identity()
    merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first_or_404()

    try:
        ticket = MerchantSupportTicketController.get_merchant_ticket_details(ticket_uid, merchant.id)
        return jsonify(ticket.serialize(include_messages=True, user_role='MERCHANT')), 200
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting merchant ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to retrieve ticket details"}), 500

@merchant_support_bp.route('/tickets/<string:ticket_uid>/messages', methods=['POST'])
@merchant_role_required
def add_merchant_message_route(ticket_uid):
    """
    Add a message to a specific support ticket as a merchant (with optional attachment).
    ---
    tags:
      - Merchant Support
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
      - name: message_text
        in: formData
        type: string
        required: false
        description: The message text.
      - name: attachment_file
        in: formData
        type: file
        required: false
        description: Optional file attachment.
    responses:
      201:
        description: Message added successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    current_user_id_from_jwt = get_jwt_identity() # This is User.id
    
    # Ensure this user is associated with a merchant profile to get merchant_id
    merchant_profile = MerchantProfile.query.filter_by(user_id=current_user_id_from_jwt).first_or_404(
        description="Merchant profile not found for the user adding the message."
    )

    form_data = request.form.to_dict()
    attachment_file = request.files.get('attachment_file')
    
    try:
        schema = AddMerchantMessageSchema()
        validated_data = schema.load(form_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400

    message_text = validated_data.get('message_text')
    
    if not message_text and not attachment_file:
        return jsonify({"error": "Message text or attachment is required."}), 400

    try:
        message = MerchantSupportTicketController.add_message_to_ticket(
            ticket_uid=ticket_uid,
            merchant_id=merchant_profile.id, # Pass merchant_id for ownership check
            sender_user_id=current_user_id_from_jwt, # The sender is the merchant's user
            message_text=message_text,
            attachment_file=attachment_file
        )
        return jsonify(message.serialize()), 201
    except (BadRequest, NotFound) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error adding message to merchant ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to add message"}), 500

@merchant_support_bp.route('/tickets/<string:ticket_uid>/close', methods=['PUT'])
@merchant_role_required
def close_merchant_ticket_route(ticket_uid):
    """
    Close a resolved support ticket as a merchant.
    ---
    tags:
      - Merchant Support
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
    responses:
      200:
        description: Ticket closed successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    current_user_id = get_jwt_identity()
    merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first_or_404()
    try:
        ticket = MerchantSupportTicketController.close_resolved_ticket(ticket_uid, merchant.id)
        return jsonify(ticket.serialize(user_role='MERCHANT')), 200
    except (BadRequest, NotFound) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error closing ticket {ticket_uid} by merchant: {e}")
        return jsonify({"error": "Failed to close ticket"}), 500