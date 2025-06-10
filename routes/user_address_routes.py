from flask import Blueprint, request, jsonify
from controllers.user_address_controller import UserAddressController

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
            required:
              - user_id
            properties:
              user_id:
                type: integer
                description: ID of the user to create address for
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
    user_id = request.json.get('user_id')
    return UserAddressController.create_address(user_id)

# Get all addresses for the current user
@user_address_bp.route('', methods=['GET'])
@user_address_bp.route('/', methods=['GET'])
def get_addresses():
    """
    Get all addresses for a specific user
    ---
    tags:
      - User Addresses
    parameters:
      - name: user_id
        in: query
        type: integer
        required: true
        description: ID of the user to get addresses for
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
        description: Invalid request - Missing user_id
      404:
        description: User not found
      500:
        description: Internal server error
    """
    user_id = request.args.get('user_id')
    return UserAddressController.get_addresses(user_id)

# Get a specific address
@user_address_bp.route('/<int:address_id>', methods=['GET'])
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
      - name: user_id
        in: query
        type: integer
        required: true
        description: ID of the user who owns the address
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
        description: Invalid request - Missing user_id
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    user_id = request.args.get('user_id')
    return UserAddressController.get_address(user_id, address_id)

# Update an address
@user_address_bp.route('/<int:address_id>', methods=['PUT'])
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
            required:
              - user_id
            properties:
              user_id:
                type: integer
                description: ID of the user who owns the address
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
    user_id = request.json.get('user_id')
    return UserAddressController.update_address(user_id, address_id)

# Delete an address
@user_address_bp.route('/<int:address_id>', methods=['DELETE'])
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
      - name: user_id
        in: query
        type: integer
        required: true
        description: ID of the user who owns the address
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
        description: Invalid request - Missing user_id
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    user_id = request.args.get('user_id')
    return UserAddressController.delete_address(user_id, address_id)

# Set default address (shipping or billing)
@user_address_bp.route('/<int:address_id>/default/<string:address_type>', methods=['PUT'])
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
            required:
              - user_id
            properties:
              user_id:
                type: integer
                description: ID of the user who owns the address
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
        description: Invalid request - Missing user_id or invalid address type
      403:
        description: Forbidden - User does not have access to this address
      404:
        description: Address not found
      500:
        description: Internal server error
    """
    if address_type not in ['shipping', 'billing']:
        return {'error': 'Invalid address type. Must be either "shipping" or "billing"'}, 400
    user_id = request.json.get('user_id')
    return UserAddressController.set_default_address(user_id, address_id, address_type) 