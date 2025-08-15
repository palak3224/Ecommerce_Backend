from flask import Blueprint, request, jsonify
from controllers.payment_card_controller import PaymentCardController
from models.enums import CardTypeEnum, CardStatusEnum
from auth.utils import role_required
from auth.models.models import UserRole
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger(__name__)

payment_card_bp = Blueprint('payment_card', __name__, url_prefix='/api/payment-cards')

@payment_card_bp.route('', methods=['POST'])
@payment_card_bp.route('/', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def add_card():
    """
    Add a new payment card to the authenticated user's account
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - card_number
              - cvv
              - expiry_month
              - expiry_year
              - card_holder_name
              - card_type
              - billing_address_id
            properties:
              card_number:
                type: string
                description: Card number (will be encrypted)
              cvv:
                type: string
                description: Card security code
              expiry_month:
                type: string
                description: Card expiration month (MM)
              expiry_year:
                type: string
                description: Card expiration year (YYYY)
              card_holder_name:
                type: string
                description: Name on the card
              card_type:
                type: string
                enum: [credit, debit]
                description: Type of card
              billing_address_id:
                type: integer
                description: ID of the billing address
              is_default:
                type: boolean
                description: Whether this should be the default card
    responses:
      200:
        description: Card added successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Card added successfully
            data:
              type: object
              properties:
                card_id:
                  type: integer
                user_id:
                  type: integer
                card_type:
                  type: string
                  enum: [credit, debit]
                last_four_digits:
                  type: string
                card_holder_name:
                  type: string
                card_brand:
                  type: string
                status:
                  type: string
                  enum: [active, inactive, expired]
                is_default:
                  type: boolean
                billing_address:
                  type: object
                last_used_at:
                  type: string
                  format: date-time
                  nullable: true
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid card details
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.add_card(user_id)
    except Exception as e:
        logger.error(f"Error adding card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@payment_card_bp.route('', methods=['GET'])
@payment_card_bp.route('/', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_user_cards():
    """
    Get all payment cards for the authenticated user
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    responses:
      200:
        description: List of user's payment cards retrieved successfully
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
                  card_id:
                    type: integer
                  user_id:
                    type: integer
                  card_type:
                    type: string
                    enum: [credit, debit]
                  last_four_digits:
                    type: string
                  card_holder_name:
                    type: string
                  card_brand:
                    type: string
                  status:
                    type: string
                    enum: [active, inactive, expired]
                  is_default:
                    type: boolean
                  billing_address:
                    type: object
                  last_used_at:
                    type: string
                    format: date-time
                    nullable: true
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have required role
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.get_user_cards(user_id)
    except Exception as e:
        logger.error(f"Error getting user cards: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@payment_card_bp.route('/<int:card_id>', methods=['GET'])
@jwt_required()
@role_required([UserRole.USER.value])
def get_card(card_id):
    """
    Get a specific payment card by ID
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    parameters:
      - in: path
        name: card_id
        type: integer
        required: true
        description: ID of the payment card to retrieve
    responses:
      200:
        description: Payment card retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                card_id:
                  type: integer
                user_id:
                  type: integer
                card_type:
                  type: string
                  enum: [credit, debit]
                last_four_digits:
                  type: string
                card_holder_name:
                  type: string
                card_brand:
                  type: string
                status:
                  type: string
                  enum: [active, inactive, expired]
                is_default:
                  type: boolean
                billing_address:
                  type: object
                last_used_at:
                  type: string
                  format: date-time
                  nullable: true
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have access to this card
      404:
        description: Card not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.get_card(user_id, card_id)
    except Exception as e:
        logger.error(f"Error getting card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@payment_card_bp.route('/<int:card_id>', methods=['PUT'])
@jwt_required()
@role_required([UserRole.USER.value])
def update_card(card_id):
    """
    Update an existing payment card
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    parameters:
      - in: path
        name: card_id
        type: integer
        required: true
        description: ID of the payment card to update
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              card_holder_name:
                type: string
                description: Name on the card
              billing_address_id:
                type: integer
                description: ID of the billing address
              card_number:
                type: string
                description: New card number (will be encrypted)
              cvv:
                type: string
                description: New card security code
              expiry_month:
                type: string
                description: New card expiration month (MM)
              expiry_year:
                type: string
                description: New card expiration year (YYYY)
              is_default:
                type: boolean
                description: Whether this should be the default card
    responses:
      200:
        description: Card updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Card updated successfully
            data:
              type: object
              properties:
                card_id:
                  type: integer
                user_id:
                  type: integer
                card_type:
                  type: string
                  enum: [credit, debit]
                last_four_digits:
                  type: string
                card_holder_name:
                  type: string
                card_brand:
                  type: string
                status:
                  type: string
                  enum: [active, inactive, expired]
                is_default:
                  type: boolean
                billing_address:
                  type: object
                last_used_at:
                  type: string
                  format: date-time
                  nullable: true
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      400:
        description: Invalid request - Missing or invalid card details
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have access to this card
      404:
        description: Card not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.update_card(user_id, card_id)
    except Exception as e:
        logger.error(f"Error updating card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@payment_card_bp.route('/<int:card_id>', methods=['DELETE'])
@jwt_required()
@role_required([UserRole.USER.value])
def delete_card(card_id):
    """
    Delete a payment card
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    parameters:
      - in: path
        name: card_id
        type: integer
        required: true
        description: ID of the payment card to delete
    responses:
      200:
        description: Card deleted successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Card deleted successfully
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have access to this card
      404:
        description: Card not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.delete_card(user_id, card_id)
    except Exception as e:
        logger.error(f"Error deleting card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@payment_card_bp.route('/<int:card_id>/default', methods=['POST'])
@jwt_required()
@role_required([UserRole.USER.value])
def set_default_card(card_id):
    """
    Set a payment card as the default payment method
    ---
    tags:
      - Payment Cards
    security:
      - Bearer: []
    parameters:
      - in: path
        name: card_id
        type: integer
        required: true
        description: ID of the payment card to set as default
    responses:
      200:
        description: Default card updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Default card updated successfully
            data:
              type: object
              properties:
                card_id:
                  type: integer
                user_id:
                  type: integer
                card_type:
                  type: string
                  enum: [credit, debit]
                last_four_digits:
                  type: string
                card_holder_name:
                  type: string
                card_brand:
                  type: string
                status:
                  type: string
                  enum: [active, inactive, expired]
                is_default:
                  type: boolean
                  example: true
                billing_address:
                  type: object
                last_used_at:
                  type: string
                  format: date-time
                  nullable: true
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have access to this card
      404:
        description: Card not found
      500:
        description: Internal server error
    """
    try:
        user_id = get_jwt_identity()
        return PaymentCardController.set_default_card(user_id, card_id)
    except Exception as e:
        logger.error(f"Error setting default card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 