from flask import Blueprint, request, jsonify
from controllers.user_address_controller import UserAddressController
from flask_jwt_extended import jwt_required, get_jwt_identity

user_address_bp = Blueprint('user_address', __name__, url_prefix='/api/user-address')

# Handle OPTIONS requests for all routes
@user_address_bp.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({'status': 'ok'})
        return response

# Create a new address
@user_address_bp.route('', methods=['POST'])
@user_address_bp.route('/', methods=['POST'])
@jwt_required()
def create_address():
    """
    Create a new address for a user
    ---
    tags:
      - User Addresses
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              address_line1:
                type: string
                description: First line of the address
              address_line2:
                type: string
                description: Second line of the address (optional)
              city:
                type: string
                description: City name
              state:
                type: string
                description: State or province
              postal_code:
                type: string
                description: Postal or ZIP code
              country:
                type: string
                description: Country name
              address_type:
                type: string
                enum: [shipping, billing]
                description: Type of address
              is_default:
                type: boolean
                description: Whether this should be the default address
    responses:
      200:
        description: Address created successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                address_id:
                  type: integer
                user_id:
                  type: integer
                address_line1:
                  type: string
                address_line2:
                  type: string
                  nullable: true
                city:
                  type: string
                state:
                  type: string
                postal_code:
                  type: string
                country:
                  type: string
                address_type:
                  type: string
                  enum: [shipping, billing]
                is_default:
                  type: boolean
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid address details
      500:
        description: Internal server error
    """
    # Derive user from JWT; ignore any client-sent user_id
    current_user_id = get_jwt_identity()
    return UserAddressController.create_address(current_user_id)

# Get all addresses for the current user
@user_address_bp.route('', methods=['GET'])
@user_address_bp.route('/', methods=['GET'])
@jwt_required()
def get_addresses():
    """
    Get all addresses for a specific user
    ---
    tags:
      - User Addresses
    security:
      - bearerAuth: []
    responses:
      200:
        description: List of addresses retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: array
              items:
                type: object
                properties:
                  address_id:
                    type: integer
                  user_id:
                    type: integer
                  address_line1:
                    type: string
                  address_line2:
                    type: string
                    nullable: true
                  city:
                    type: string
                  state:
                    type: string
                  postal_code:
                    type: string
                  country:
                    type: string
                  address_type:
                    type: string
                    enum: [shipping, billing]
                  is_default:
                    type: boolean
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
      400:
        description: Invalid request
      404:
        description: User not found
      500:
        description: Internal server error
    """
    current_user_id = get_jwt_identity()
    return UserAddressController.get_addresses(current_user_id)

# Get a specific address
@user_address_bp.route('/<int:address_id>', methods=['GET'])
@jwt_required()
def get_address(address_id):
    """
    Get a specific address by ID
    ---
    tags:
      - User Addresses
    parameters:
      - name: address_id
        in: path
        type: integer
        required: true
        description: ID of the address to retrieve
    security:
      - bearerAuth: []
    responses:
      200:
        description: Address retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                address_id:
                  type: integer
                user_id:
                  type: integer
                address_line1:
                  type: string
                address_line2:
                  type: string
                  nullable: true
                city:
                  type: string
                state:
                  type: string
                postal_code:
                  type: string
                country:
                  type: string
                address_type:
                  type: string
                  enum: [shipping, billing]
                is_default:
                  type: boolean
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    current_user_id = get_jwt_identity()
    return UserAddressController.get_address(current_user_id, address_id)

# Update an address
@user_address_bp.route('/<int:address_id>', methods=['PUT'])
@jwt_required()
def update_address(address_id):
    """
    Update an existing address
    ---
    tags:
      - User Addresses
    parameters:
      - name: address_id
        in: path
        type: integer
        required: true
        description: ID of the address to update
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              address_line1:
                type: string
                description: First line of the address
              address_line2:
                type: string
                description: Second line of the address (optional)
              city:
                type: string
                description: City name
              state:
                type: string
                description: State or province
              postal_code:
                type: string
                description: Postal or ZIP code
              country:
                type: string
                description: Country name
              address_type:
                type: string
                enum: [shipping, billing]
                description: Type of address
              is_default:
                type: boolean
                description: Whether this should be the default address
    responses:
      200:
        description: Address updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                address_id:
                  type: integer
                user_id:
                  type: integer
                address_line1:
                  type: string
                address_line2:
                  type: string
                  nullable: true
                city:
                  type: string
                state:
                  type: string
                postal_code:
                  type: string
                country:
                  type: string
                address_type:
                  type: string
                  enum: [shipping, billing]
                is_default:
                  type: boolean
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid address details
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    current_user_id = get_jwt_identity()
    return UserAddressController.update_address(current_user_id, address_id)

# Delete an address
@user_address_bp.route('/<int:address_id>', methods=['DELETE'])
@jwt_required()
def delete_address(address_id):
    """
    Delete an existing address
    ---
    tags:
      - User Addresses
    parameters:
      - name: address_id
        in: path
        type: integer
        required: true
        description: ID of the address to delete
    security:
      - bearerAuth: []
    responses:
      200:
        description: Address deleted successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Address deleted successfully
      400:
        description: Invalid request
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    current_user_id = get_jwt_identity()
    return UserAddressController.delete_address(current_user_id, address_id)

# Set default address (shipping or billing)
@user_address_bp.route('/<int:address_id>/default/<string:address_type>', methods=['PUT'])
@jwt_required()
def set_default_address(address_id, address_type):
    """
    Set an address as the default shipping or billing address
    ---
    tags:
      - User Addresses
    parameters:
      - name: address_id
        in: path
        type: integer
        required: true
        description: ID of the address to set as default
      - name: address_type
        in: path
        type: string
        required: true
        enum: [shipping, billing]
        description: Type of address to set as default
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              # No body required; identity is taken from JWT
              note:
                type: string
                description: Identity is derived from the access token
    responses:
      200:
        description: Default address updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Default address updated successfully
            data:
              type: object
              properties:
                address_id:
                  type: integer
                user_id:
                  type: integer
                address_type:
                  type: string
                  enum: [shipping, billing]
                is_default:
                  type: boolean
                  example: true
      400:
        description: Invalid request - Invalid address type
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    if address_type not in ['shipping', 'billing']:
        return {'error': 'Invalid address type. Must be either "shipping" or "billing"'}, 400
    current_user_id = get_jwt_identity()
    return UserAddressController.set_default_address(current_user_id, address_id, address_type)