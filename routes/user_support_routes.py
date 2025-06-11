# routes/user_support_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound
from marshmallow import Schema, fields, validate, ValidationError

from controllers.user_support_controller import UserSupportTicketController
from auth.models import User 
from models.enums import TicketPriority, TicketStatus

# Using /api/support for general user support tickets
user_support_bp = Blueprint('user_support_bp', __name__, url_prefix='/api/user/support') 

# --- Schemas for Request Validation ---
class CreateUserTicketSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=3, max=255))
    description = fields.Str(required=True, validate=validate.Length(min=10))
    priority = fields.Str(
        validate=validate.OneOf([p.value for p in TicketPriority]), 
        load_default=TicketPriority.MEDIUM.value
    )
    related_order_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    related_product_id = fields.Int(required=False, allow_none=True)
    # image_file will be handled as form-data, not in JSON schema

class AddUserMessageSchema(Schema):
    message_text = fields.Str(validate=validate.Length(min=1))
    # attachment_file will be handled as form-data

# --- User Support Ticket Routes ---

@user_support_bp.route('/tickets', methods=['POST'])
@jwt_required() # General authenticated users (customers or merchants acting as customers)
def create_user_ticket_route():
    """
    Create a new support ticket for the authenticated user.
    Accepts multipart/form-data for image upload.
    ---
    tags:
      - User Support
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - name: title
        in: formData
        type: string
        required: true
      - name: description
        in: formData
        type: string
        required: true
      - name: priority
        in: formData
        type: string
        enum: ['low', 'medium', 'high']
        default: 'medium'
      - name: related_order_id
        in: formData
        type: string
        required: false
      - name: related_product_id
        in: formData
        type: integer
        required: false
      - name: image_file
        in: formData
        type: file
        required: false
    responses:
      201:
        description: Support ticket created successfully.
      400:
        description: Bad request (validation error, missing fields).
      401:
        description: Unauthorized.
      500:
        description: Internal server error.
    """
    current_user_id = get_jwt_identity()
    if not User.query.get(current_user_id): 
        return jsonify({"error": "User not found"}), 404
    
    form_data = request.form.to_dict()
    image_file = request.files.get('image_file')

    try:
        schema = CreateUserTicketSchema()
        # Marshmallow loads default for missing optional fields if load_default is set
        validated_data = schema.load(form_data) 
    except ValidationError as err:
        current_app.logger.warning(f"User ticket creation validation failed: {err.messages}")
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400

    try:
        ticket = UserSupportTicketController.create_ticket(
            data=validated_data, 
            creator_user_id=current_user_id,
            image_file=image_file
        )
        return jsonify(ticket.serialize(user_role='CUSTOMER')), 201
    except BadRequest as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error creating user support ticket: {e}")
        return jsonify({"error": "Failed to create support ticket"}), 500

@user_support_bp.route('/tickets', methods=['GET'])
@jwt_required()
def list_user_tickets_route():
    current_user_id = get_jwt_identity()

    status_filter = request.args.get('status')
    sort_by = request.args.get('sort_by', '-updated_at') # Default sort by most recently updated
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        paginated_tickets = UserSupportTicketController.list_user_tickets(
            creator_user_id=current_user_id,
            status_filter=status_filter,
            sort_by=sort_by,
            page=page,
            per_page=per_page
        )
        return jsonify({
            "tickets": [ticket.serialize(user_role='CUSTOMER') for ticket in paginated_tickets.items],
            "pagination": {
                "total_items": paginated_tickets.total,
                "total_pages": paginated_tickets.pages,
                "current_page": paginated_tickets.page,
                "per_page": paginated_tickets.per_page,
                "has_next": paginated_tickets.has_next,
                "has_prev": paginated_tickets.has_prev
            }
        }), 200
    except BadRequest as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error listing user tickets for user {current_user_id}: {e}")
        return jsonify({"error": "Failed to retrieve tickets"}), 500

@user_support_bp.route('/tickets/<string:ticket_uid>', methods=['GET'])
@jwt_required()
def get_user_ticket_route(ticket_uid):
    current_user_id = get_jwt_identity()
    try:
        ticket = UserSupportTicketController.get_user_ticket_details(ticket_uid, current_user_id)
        return jsonify(ticket.serialize(include_messages=True, user_role='CUSTOMER')), 200
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting user ticket {ticket_uid} for user {current_user_id}: {e}")
        return jsonify({"error": "Failed to retrieve ticket details"}), 500

@user_support_bp.route('/tickets/<string:ticket_uid>/messages', methods=['POST'])
@jwt_required()
def add_user_message_route(ticket_uid):
    current_user_id = get_jwt_identity()
    
    form_data = request.form.to_dict()
    attachment_file = request.files.get('attachment_file')
    
    try:
        schema = AddUserMessageSchema()
        validated_data = schema.load(form_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400

    message_text = validated_data.get('message_text')

    if not message_text and not attachment_file: # Check if at least one is present
        return jsonify({"error": "Message text or an attachment is required."}), 400
        
    try:
        message = UserSupportTicketController.add_message_to_ticket_by_user(
            ticket_uid=ticket_uid,
            creator_user_id=current_user_id, 
            message_text=message_text,
            attachment_file=attachment_file
        )
        return jsonify(message.serialize()), 201
    except (BadRequest, NotFound) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error adding message to user ticket {ticket_uid} by user {current_user_id}: {e}")
        return jsonify({"error": "Failed to add message"}), 500

@user_support_bp.route('/tickets/<string:ticket_uid>/close', methods=['PUT'])
@jwt_required()
def close_user_ticket_route(ticket_uid):
    current_user_id = get_jwt_identity()
    try:
        ticket = UserSupportTicketController.close_resolved_ticket_by_user(ticket_uid, current_user_id)
        return jsonify(ticket.serialize(user_role='CUSTOMER')), 200
    except (BadRequest, NotFound) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Error closing ticket {ticket_uid} by user {current_user_id}: {e}")
        return jsonify({"error": "Failed to close ticket"}), 500