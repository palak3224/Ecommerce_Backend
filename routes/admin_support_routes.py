# routes/admin_support_routes.py 
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound
from marshmallow import Schema, fields, validate, ValidationError


from controllers.superadmin.admin_support_controller import AdminSupportTicketController 
from auth.utils import admin_role_required 
from models.enums import TicketStatus, TicketPriority, TicketCreatorRole

admin_support_bp = Blueprint('admin_support_bp', __name__, url_prefix='/api/superadmin/support')

# --- Schemas for Admin Actions ---
class AdminReplySchema(Schema):
    message_text = fields.Str(validate=validate.Length(min=1))
    # attachment_file handled as form-data

class AssignTicketSchema(Schema):
    admin_id = fields.Int(required=True, )

class UpdateStatusSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf([s.value for s in TicketStatus]))
    notes = fields.Str(required=False, allow_none=True)

class UpdatePrioritySchema(Schema):
    priority = fields.Str(required=True, validate=validate.OneOf([p.value for p in TicketPriority]))


# --- Admin Support Ticket Routes ---

@admin_support_bp.route('/tickets', methods=['GET'])
@admin_role_required
def list_all_tickets_route():
    """
    List all support tickets for admins.
    Supports filtering and pagination.
    ---
    tags:
      - Admin Support
    security:
      - Bearer: []
    parameters:
      - name: status
        in: query
        type: string
        required: false
        enum: ['all', 'open', 'in_progress', 'awaiting_customer_reply', 'awaiting_merchant_reply', 'resolved', 'closed']
      - name: priority
        in: query
        type: string
        required: false
        enum: ['all', 'low', 'medium', 'high']
      - name: creator_role 
        in: query
        type: string
        required: false
        enum: ['all', 'customer', 'merchant']
      - name: assigned_to
        in: query
        type: string 
        required: false
        description: Admin user ID or 'unassigned'.
      - name: search
        in: query
        type: string
        required: false
        description: Search by ticket UID, title, description, creator email/name, or merchant business name.
      - name: sort_by
        in: query
        type: string
        required: false
        description: Field to sort by (e.g., 'updated_at', '-priority', 'creator_name'). Default is '-updated_at'.
      - name: page
        in: query
        type: integer
        required: false
        default: 1
      - name: per_page
        in: query
        type: integer
        required: false
        default: 10
    responses:
      200:
        description: List of support tickets.
      401:
        description: Unauthorized.
      500:
        description: Internal server error.
    """
    admin_user_id = get_jwt_identity() # For logging or if needed by controller
    
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    creator_role_filter = request.args.get('creator_role')
    assigned_to_filter = request.args.get('assigned_to')
    sort_by = request.args.get('sort_by', '-updated_at')
    search_query = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        paginated_tickets = AdminSupportTicketController.list_all_tickets(
            status_filter=status_filter,
            priority_filter=priority_filter,
            creator_role_filter=creator_role_filter,
            assigned_to_filter=assigned_to_filter,
            sort_by=sort_by,
            search_query=search_query,
            page=page,
            per_page=per_page
        )
        return jsonify({
            "tickets": [ticket.serialize(user_role='ADMIN') for ticket in paginated_tickets.items], # Pass user_role
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
        current_app.logger.error(f"Admin: Error listing all tickets: {e}")
        return jsonify({"error": "Failed to retrieve tickets"}), 500

@admin_support_bp.route('/tickets/<string:ticket_uid>', methods=['GET'])
@admin_role_required
def get_admin_ticket_route(ticket_uid):
    """
    Get details of a specific support ticket by UID for admins.
    ---
    tags:
      - Admin Support
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
    try:
        ticket = AdminSupportTicketController.get_ticket_details_for_admin(ticket_uid)
        return jsonify(ticket.serialize(include_messages=True, user_role='ADMIN')), 200
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Admin: Error getting ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to retrieve ticket details"}), 500

@admin_support_bp.route('/tickets/<string:ticket_uid>/assign', methods=['PUT'])
@admin_role_required
def assign_ticket_route(ticket_uid):
    """
    Assign a support ticket to an admin.
    ---
    tags:
      - Admin Support
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
      - name: admin_id
        in: body
        required: true
        schema:
          type: object
          properties:
            admin_id:
              type: integer
              description: ID of the admin to assign the ticket to.
    responses:
      200:
        description: Ticket assigned successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    admin_acting_id = get_jwt_identity() # The admin performing the action
    try:
        schema = AssignTicketSchema()
        data = schema.load(request.json)
        admin_id_to_assign = data['admin_id']
        
        ticket = AdminSupportTicketController.assign_ticket_to_admin(ticket_uid, admin_id_to_assign)
        # Log who assigned it if needed
        return jsonify(ticket.serialize(user_role='ADMIN')), 200
    except (ValidationError, BadRequest) as e:
        msg = e.messages if isinstance(e, ValidationError) else e.description
        return jsonify({"error": "Validation failed or bad request", "details": msg}), 400
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Admin: Error assigning ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to assign ticket"}), 500

@admin_support_bp.route('/tickets/<string:ticket_uid>/messages', methods=['POST'])
@admin_role_required
def admin_reply_route(ticket_uid):
    """
    Add a reply to a support ticket as an admin (with optional attachment).
    ---
    tags:
      - Admin Support
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
        description: The reply message text.
      - name: attachment_file
        in: formData
        type: file
        required: false
        description: Optional file attachment.
    responses:
      201:
        description: Reply added successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    admin_user_id = get_jwt_identity()
    
    form_data = request.form.to_dict()
    attachment_file = request.files.get('attachment_file')
    
    try:
        schema = AdminReplySchema()
        validated_data = schema.load(form_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400
        
    message_text = validated_data.get('message_text')
    if not message_text and not attachment_file:
        return jsonify({"error": "Message text or attachment is required."}), 400

    try:
        message = AdminSupportTicketController.admin_reply_to_ticket(
            ticket_uid=ticket_uid,
            admin_user_id=admin_user_id,
            message_text=message_text,
            attachment_file=attachment_file
        )
        return jsonify(message.serialize()), 201
    except (BadRequest, NotFound) as e:
        return jsonify({"error": e.description}), e.code
    except Exception as e:
        current_app.logger.error(f"Admin: Error replying to ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to add reply"}), 500

@admin_support_bp.route('/tickets/<string:ticket_uid>/status', methods=['PUT'])
@admin_role_required
def update_ticket_status_route(ticket_uid):
    """
    Update the status of a support ticket as an admin.
    ---
    tags:
      - Admin Support
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
      - name: status
        in: body
        required: true
        schema:
          type: object
          properties:
            status:
              type: string
              description: New status for the ticket.
            notes:
              type: string
              description: Optional notes for the status update.
    responses:
      200:
        description: Ticket status updated successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    admin_user_id = get_jwt_identity()
    try:
        schema = UpdateStatusSchema()
        data = schema.load(request.json)
        new_status = data['status']
        notes = data.get('notes')
        
        ticket = AdminSupportTicketController.update_ticket_status(ticket_uid, new_status, admin_user_id, notes)
        return jsonify(ticket.serialize(user_role='ADMIN')), 200
    except (ValidationError, BadRequest) as e:
        msg = e.messages if isinstance(e, ValidationError) else e.description
        return jsonify({"error": "Validation failed or bad request", "details": msg}), 400
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Admin: Error updating status for ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to update ticket status"}), 500

@admin_support_bp.route('/tickets/<string:ticket_uid>/priority', methods=['PUT'])
@admin_role_required
def update_ticket_priority_route(ticket_uid):
    """
    Update the priority of a support ticket as an admin.
    ---
    tags:
      - Admin Support
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_uid
        type: string
        required: true
        description: Unique identifier of the support ticket.
      - name: priority
        in: body
        required: true
        schema:
          type: object
          properties:
            priority:
              type: string
              description: New priority for the ticket.
    responses:
      200:
        description: Ticket priority updated successfully.
      400:
        description: Validation failed or bad request.
      401:
        description: Unauthorized.
      404:
        description: Ticket not found.
      500:
        description: Internal server error.
    """
    admin_user_id = get_jwt_identity()
    try:
        schema = UpdatePrioritySchema()
        data = schema.load(request.json)
        new_priority = data['priority']
        
        ticket = AdminSupportTicketController.update_ticket_priority(ticket_uid, new_priority, admin_user_id)
        return jsonify(ticket.serialize(user_role='ADMIN')), 200
    except (ValidationError, BadRequest) as e:
        msg = e.messages if isinstance(e, ValidationError) else e.description
        return jsonify({"error": "Validation failed or bad request", "details": msg}), 400
    except NotFound as e:
        return jsonify({"error": e.description}), 404
    except Exception as e:
        current_app.logger.error(f"Admin: Error updating priority for ticket {ticket_uid}: {e}")
        return jsonify({"error": "Failed to update ticket priority"}), 500