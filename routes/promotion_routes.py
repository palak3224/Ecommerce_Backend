# FILE: routes/superadmin/promotion_routes.py
from flask import Blueprint, request, jsonify, current_app
from auth.utils import super_admin_role_required
from http import HTTPStatus
from sqlalchemy.orm import joinedload

from controllers.superadmin.promotion_controller import PromotionController
from models.promotion import Promotion

superadmin_promotion_bp = Blueprint('superadmin_promotion_bp', __name__, url_prefix='/api/superadmin/promotions')

# ── PROMOTIONS ────────────────────────────────────────────────────────────────────
@superadmin_promotion_bp.route('/', methods=['GET'])
@super_admin_role_required
def list_promotions():
    """
    Get a list of all promotions
    ---
    tags:
      - Superadmin - Promotions
    security:
      - Bearer: []
    responses:
      200:
        description: List of promotions retrieved successfully
        schema:
          type: array
          items:
            $ref: '#/definitions/Promotion'
      401:
        description: Unauthorized - Invalid or missing token
      403:
        description: Forbidden - User does not have super admin role
      500:
        description: Internal server error
    definitions:
      Promotion:
        type: object
        properties:
          promotion_id:
            type: integer
          code:
            type: string
          description:
            type: string
          discount_type:
            type: string
            enum: [percentage, fixed]
          discount_value:
            type: number
          start_date:
            type: string
            format: date
          end_date:
            type: string
            format: date
          active_flag:
            type: boolean
          target:
            type: object
            nullable: true
            properties:
              type:
                type: string
                enum: [product, category, brand]
              id:
                type: integer
              name:
                type: string
    """
    try:
        promos = PromotionController.list_all()
        return jsonify([p.serialize() for p in promos]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing promotions: {e}")
        return jsonify({'message': 'Failed to retrieve promotions.'}), HTTPStatus.INTERNAL_SERVER_ERROR


@superadmin_promotion_bp.route('/', methods=['POST'])
@super_admin_role_required
def create_promotion():
    """
    Create a new promotion for a specific brand, category, product, or sitewide.
    ---
    tags:
      - Superadmin - Promotions
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - discount_type
              - discount_value
              - start_date
              - end_date
            properties:
              description:
                type: string
              discount_type:
                type: string
                enum: [percentage, fixed]
              discount_value:
                type: number
              start_date:
                type: string
                format: date-time
                description: "Start date in ISO 8601 format (e.g., 2024-05-20T00:00:00Z)"
              end_date:
                type: string
                format: date-time
                description: "End date in ISO 8601 format (e.g., 2024-06-20T23:59:59Z)"
              code:
                type: string
                description: "Optional. A unique code will be generated if not provided."
              active_flag:
                type: boolean
                default: true
              product_id:
                type: integer
                nullable: true
              category_id:
                type: integer
                nullable: true
              brand_id:
                type: integer
                nullable: true
    responses:
      201:
        description: Promotion created successfully.
        schema:
          $ref: '#/definitions/Promotion'
      400:
        description: Bad request (validation error, e.g., multiple targets).
      409:
        description: Conflict (e.g., code already exists).
      500:
        description: Internal Server Error.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), HTTPStatus.BAD_REQUEST

    try:
        p = PromotionController.create(data)
        # We need to reload the object to get the eager-loaded relationships for serialization
        p_with_rels = Promotion.query.options(
            joinedload(Promotion.product),
            joinedload(Promotion.category),
            joinedload(Promotion.brand)
        ).get(p.promotion_id)
        return jsonify(p_with_rels.serialize()), HTTPStatus.CREATED
    except ValueError as e:
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating promotion: {e}")
        return jsonify({'message': 'Failed to create promotion.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@superadmin_promotion_bp.route('/<int:pid>', methods=['PUT'])
@super_admin_role_required
def update_promotion(pid):
    """
    Update an existing promotion. The target (product/category/brand) cannot be changed.
    ---
    tags:
      - Superadmin - Promotions
    security:
      - Bearer: []
    parameters:
      - in: path
        name: pid
        type: integer
        required: true
        description: ID of the promotion to update
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              description:
                type: string
              discount_type:
                type: string
                enum: [percentage, fixed]
              discount_value:
                type: number
              start_date:
                type: string
                format: date-time
              end_date:
                type: string
                format: date-time
              active_flag:
                type: boolean
              code:
                type: string
    responses:
      200:
        description: Promotion updated successfully
        schema:
          $ref: '#/definitions/Promotion'
      400:
        description: Bad request - Invalid data
      404:
        description: Promotion not found
      500:
        description: Internal server error
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), HTTPStatus.BAD_REQUEST
    try:
        p = PromotionController.update(pid, data)
        p_with_rels = Promotion.query.options(
            joinedload(Promotion.product),
            joinedload(Promotion.category),
            joinedload(Promotion.brand)
        ).get(p.promotion_id)
        return jsonify(p_with_rels.serialize()), HTTPStatus.OK
    except ValueError as e:
         return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating promotion {pid}: {e}")
        return jsonify({'message': 'Failed to update promotion.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@superadmin_promotion_bp.route('/<int:pid>', methods=['DELETE'])
@super_admin_role_required
def delete_promotion(pid):
    """
    Soft delete a promotion
    ---
    tags:
      - Superadmin - Promotions
    security:
      - Bearer: []
    parameters:
      - in: path
        name: pid
        type: integer
        required: true
        description: ID of the promotion to delete
    responses:
      200:
        description: Promotion deleted successfully
        schema:
          $ref: '#/definitions/Promotion'
      404:
        description: Promotion not found
      500:
        description: Internal server error
    """
    try:
        p = PromotionController.soft_delete(pid)
        return jsonify(p.serialize()), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error deleting promotion {pid}: {e}")
        return jsonify({'message': 'Failed to delete promotion.'}), HTTPStatus.INTERNAL_SERVER_ERROR