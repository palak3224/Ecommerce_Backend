from flask import Blueprint, request, jsonify
from controllers.shiprocket_controller import ShipRocketController
from auth.utils import super_admin_role_required , merchant_role_required 
from common.response import success_response, error_response
import traceback
from flask_jwt_extended import jwt_required
from flask import current_app

shiprocket_bp = Blueprint('shiprocket', __name__, url_prefix='/api/shiprocket')

@shiprocket_bp.route('/serviceability', methods=['POST'])
@jwt_required()
def check_serviceability():
    """
    Check courier serviceability and get shipping charges
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - pickup_pincode
              - delivery_pincode
              - weight
            properties:
              pickup_pincode:
                type: string
                description: Pickup location pincode
              delivery_pincode:
                type: string
                description: Delivery location pincode
              weight:
                type: number
                format: float
                description: Package weight in kg
              cod:
                type: boolean
                default: false
                description: Whether this is a COD order (true) or prepaid (false)
              order_id:
                type: string
                description: Order ID for the request (optional, not used for serviceability checks)
              cod_amount:
                type: number
                format: float
                description: COD amount (only if cod is true)
    responses:
      200:
        description: Serviceability check successful
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                available_courier_companies:
                  type: array
                  items:
                    type: object
                    properties:
                      courier_company_id:
                        type: integer
                      courier_name:
                        type: string
                      rate:
                        type: number
                      estimated_delivery_days:
                        type: string
      400:
        description: Invalid request data
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        required_fields = ['pickup_pincode', 'delivery_pincode', 'weight']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}", 400)
        
        pickup_pincode = data['pickup_pincode']
        delivery_pincode = data['delivery_pincode']
        weight = float(data['weight'])
        cod = data.get('cod', False)  # Boolean: true for COD, false for prepaid
        cod_amount = float(data.get('cod_amount', 0))  # COD amount if it's a COD order
        order_id = data.get('order_id')  # Optional order_id
        
        if weight <= 0:
            return error_response("Weight must be greater than 0", 400)
        
        # Convert boolean cod to the format expected by ShipRocket
        # If cod is True, use cod_amount, otherwise use 0
        shiprocket_cod = cod_amount if cod else 0
        
        shiprocket = ShipRocketController()
        response = shiprocket.check_serviceability(
            pickup_pincode=pickup_pincode,
            delivery_pincode=delivery_pincode,
            weight=weight,
            cod=shiprocket_cod  # Pass the calculated COD amount
        )
        
        # Just return the controller's response (may have empty list and/or message)
        return success_response("Serviceability check successful", response)
        
    except ValueError as e:
        return error_response(f"Invalid data format: {str(e)}", 400)
    except Exception as e:
        current_app.logger.error(f"Serviceability check failed: {str(e)}")
        return error_response(f"Serviceability check failed: {str(e)}", 500)

@shiprocket_bp.route('/create-order', methods=['POST'])
@jwt_required()
def create_shiprocket_order():
    """
    Create ShipRocket order from database order
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - order_id
              - merchant_id
              - delivery_address_id
            properties:
              order_id:
                type: string
                description: Internal order ID
              merchant_id:
                type: integer
                description: Merchant ID
              pickup_address_id:
                type: integer
                description: Pickup address ID (optional, will use merchant address if not provided)
              delivery_address_id:
                type: integer
                description: Delivery address ID
              courier_id:
                type: integer
                description: Preferred courier ID (optional)
    responses:
      200:
        description: ShipRocket order created successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                shiprocket_order_id:
                  type: integer
                shipment_id:
                  type: integer
                awb_code:
                  type: string
                courier_name:
                  type: string
                tracking_number:
                  type: string
                serviceability:
                  type: object
                order_response:
                  type: object
                awb_response:
                  type: object
                pickup_response:
                  type: object
                db_shipment:
                  type: object
      400:
        description: Invalid request data
      404:
        description: Order, merchant, or address not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        required_fields = ['order_id', 'merchant_id', 'delivery_address_id']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}", 400)
        
        order_id = data['order_id']
        merchant_id = int(data['merchant_id'])
        delivery_address_id = int(data['delivery_address_id'])
        pickup_address_id = int(data['pickup_address_id']) if data.get('pickup_address_id') else None
        courier_id = int(data.get('courier_id')) if data.get('courier_id') else None
        
        # Validate order_id format
        if not order_id or not isinstance(order_id, str):
            return error_response("Invalid order_id format", 400)
        
        # Validate merchant_id
        if merchant_id <= 0:
            return error_response("Invalid merchant_id", 400)
        
        # Validate delivery_address_id
        if delivery_address_id <= 0:
            return error_response("Invalid delivery_address_id", 400)
        
        # Validate pickup_address_id if provided
        if pickup_address_id is not None and pickup_address_id <= 0:
            return error_response("Invalid pickup_address_id", 400)
        
        # Validate courier_id if provided
        if courier_id is not None and courier_id <= 0:
            return error_response("Invalid courier_id", 400)
        
        shiprocket = ShipRocketController()
        response = shiprocket.create_shiprocket_order_from_db_order(
            order_id=order_id,
            merchant_id=merchant_id,
            pickup_address_id=pickup_address_id,
            delivery_address_id=delivery_address_id,
            courier_id=courier_id
        )
        
        return success_response("ShipRocket order created successfully", response)
        
    except ValueError as e:
        return error_response(f"Invalid data format: {str(e)}", 400)
    except Exception as e:
        return error_response(f"ShipRocket order creation failed: {str(e)}", 500)

@shiprocket_bp.route('/assign-awb', methods=['POST'])
@merchant_role_required
def assign_awb():
    """
    Assign AWB (Airway Bill) to shipment
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - shipment_id
              - courier_id
            properties:
              shipment_id:
                type: integer
                description: ShipRocket shipment ID
              courier_id:
                type: integer
                description: Courier ID from serviceability response
    responses:
      200:
        description: AWB assigned successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                awb_code:
                  type: string
                courier_name:
                  type: string
      400:
        description: Invalid request data
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        required_fields = ['shipment_id', 'courier_id']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}", 400)
        
        shipment_id = int(data['shipment_id'])
        courier_id = int(data['courier_id'])
        
        shiprocket = ShipRocketController()
        response = shiprocket.assign_awb(shipment_id, courier_id)
        
        return success_response("AWB assigned successfully", response)
        
    except ValueError as e:
        return error_response(f"Invalid data format: {str(e)}", 400)
    except Exception as e:
        return error_response(f"AWB assignment failed: {str(e)}", 500)

@shiprocket_bp.route('/generate-pickup', methods=['POST'])
@merchant_role_required
def generate_pickup():
    """
    Generate pickup request for shipment
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - shipment_id
            properties:
              shipment_id:
                type: integer
                description: ShipRocket shipment ID
    responses:
      200:
        description: Pickup generated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                message:
                  type: string
      400:
        description: Invalid request data
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        if 'shipment_id' not in data:
            return error_response("Missing required field: shipment_id", 400)
        
        shipment_id = int(data['shipment_id'])
        
        shiprocket = ShipRocketController()
        response = shiprocket.generate_pickup(shipment_id)
        
        return success_response("Pickup generated successfully", response)
        
    except ValueError as e:
        return error_response(f"Invalid data format: {str(e)}", 400)
    except Exception as e:
        return error_response(f"Pickup generation failed: {str(e)}", 500)

@shiprocket_bp.route('/tracking/<awb_code>', methods=['GET'])
def get_tracking_details(awb_code):
    """
    Get tracking details for a shipment
    ---
    tags:
      - ShipRocket
    parameters:
      - name: awb_code
        in: path
        type: string
        required: true
        description: AWB code
    responses:
      200:
        description: Tracking details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                tracking_data:
                  type: object
      400:
        description: Invalid AWB code
      500:
        description: Internal server error
    """
    try:
        if not awb_code:
            return error_response("AWB code is required", 400)
        
        shiprocket = ShipRocketController()
        response = shiprocket.get_tracking_details(awb_code)
        
        return success_response("Tracking details retrieved successfully", response)
        
    except Exception as e:
        return error_response(f"Tracking details fetch failed: {str(e)}", 500)

@shiprocket_bp.route('/tracking/order/<order_id>', methods=['GET'])
@jwt_required()
def get_tracking_by_order_id(order_id):
    """
    Get tracking details for a shipment using order ID
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    parameters:
      - name: order_id
        in: path
        type: string
        required: true
        description: Order ID from your store
      - name: channel_id
        in: query
        type: integer
        required: false
        description: Channel ID corresponding to the store
    responses:
      200:
        description: Tracking details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                tracking_data:
                  type: object
      400:
        description: Invalid order ID
      500:
        description: Internal server error
    """
    try:
        if not order_id:
            return error_response("Order ID is required", 400)
        
        # Get channel_id from query parameters
        channel_id = request.args.get('channel_id', type=int)
        
        shiprocket = ShipRocketController()
        response = shiprocket.get_tracking_by_order_id(order_id, channel_id)
        
        return success_response("Tracking details retrieved successfully", response)
        
    except Exception as e:
        return error_response(f"Tracking details fetch failed: {str(e)}", 500)

@shiprocket_bp.route('/tracking/shipment/<int:shipment_id>', methods=['GET'])
@jwt_required()
def get_shipment_tracking(shipment_id):
    """
    Get tracking details for a shipment using shipment ID from database
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    parameters:
      - name: shipment_id
        in: path
        type: integer
        required: true
        description: Shipment ID from database
    responses:
      200:
        description: Tracking details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                tracking_data:
                  type: object
      400:
        description: Invalid shipment ID
      404:
        description: Shipment not found
      500:
        description: Internal server error
    """
    try:
        if not shipment_id:
            return error_response("Shipment ID is required", 400)
        
        shiprocket = ShipRocketController()
        response = shiprocket.get_shipment_tracking(shipment_id)
        
        return success_response("Tracking details retrieved successfully", response)
        
    except Exception as e:
        return error_response(f"Tracking details fetch failed: {str(e)}", 500)

@shiprocket_bp.route('/tracking/db-order/<order_id>', methods=['GET'])
@jwt_required()
def get_tracking_by_db_order_id(order_id):
    """
    Get tracking details using order_id from your database Order model
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    parameters:
      - name: order_id
        in: path
        type: string
        required: true
        description: Order ID from your database (e.g., "ORD-20250728114812-8D8759")
    responses:
      200:
        description: Tracking details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                order_id:
                  type: string
                shipments:
                  type: object
                  additionalProperties:
                    type: object
                    properties:
                      shipment_id:
                        type: integer
                      merchant_id:
                        type: integer
                      carrier_name:
                        type: string
                      tracking_number:
                        type: string
                      shiprocket_order_id:
                        type: integer
                      tracking_data:
                        type: object
                      error:
                        type: string
      400:
        description: Invalid order ID
      404:
        description: Order not found
      500:
        description: Internal server error
    """
    try:
        if not order_id:
            return error_response("Order ID is required", 400)
        
        shiprocket = ShipRocketController()
        response = shiprocket.get_tracking_by_db_order_id(order_id)
        
        return success_response("Tracking details retrieved successfully", response)
        
    except Exception as e:
        return error_response(f"Tracking details fetch failed: {str(e)}", 500)

@shiprocket_bp.route('/bulk-create-orders', methods=['POST'])
@super_admin_role_required
def bulk_create_shiprocket_orders():
    """
    Create multiple ShipRocket orders for pending shipments
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              order_ids:
                type: array
                items:
                  type: string
                description: List of order IDs to process
              merchant_id:
                type: integer
                description: Merchant ID (if processing for specific merchant)
    responses:
      200:
        description: Bulk order creation completed
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                successful:
                  type: array
                failed:
                  type: array
      400:
        description: Invalid request data
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        order_ids = data.get('order_ids', [])
        merchant_id = data.get('merchant_id')
        
        if not order_ids:
            return error_response("At least one order ID is required", 400)
        
        shiprocket = ShipRocketController()
        successful = []
        failed = []
        
        for order_id in order_ids:
            try:
                # This would need to be implemented based on your business logic
                # For now, we'll just track the attempt
                response = shiprocket.create_shiprocket_order_from_db_order(
                    order_id=order_id,
                    merchant_id=merchant_id,
                    pickup_address_id=None,  # Would need to be determined
                    delivery_address_id=None,  # Would need to be determined
                    courier_id=None
                )
                successful.append({
                    'order_id': order_id,
                    'response': response
                })
            except Exception as e:
                failed.append({
                    'order_id': order_id,
                    'error': str(e)
                })
        
        result = {
            'successful': successful,
            'failed': failed,
            'total_processed': len(order_ids),
            'successful_count': len(successful),
            'failed_count': len(failed)
        }
        
        return success_response("Bulk order creation completed", result)
        
    except Exception as e:
        return error_response(f"Bulk order creation failed: {str(e)}", 500)

@shiprocket_bp.route('/create-orders-for-all-merchants', methods=['POST'])
@jwt_required()
def create_shiprocket_orders_for_all_merchants():
    """
    Create ShipRocket orders for all merchants involved in a single order
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - order_id
              - delivery_address_id
            properties:
              order_id:
                type: string
                description: Internal order ID
              delivery_address_id:
                type: integer
                description: Delivery address ID
              courier_id:
                type: integer
                description: Preferred courier ID for all shipments (optional)
    responses:
      200:
        description: ShipRocket orders created successfully for all merchants
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                total_merchants:
                  type: integer
                successful_merchants:
                  type: array
                  items:
                    type: integer
                failed_merchants:
                  type: array
                  items:
                    type: integer
                merchant_responses:
                  type: object
      400:
        description: Invalid request data
      404:
        description: Order or delivery address not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Request data is required", 400)
        
        required_fields = ['order_id', 'delivery_address_id']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}", 400)
        
        order_id = data['order_id']
        delivery_address_id = int(data['delivery_address_id'])
        courier_id = int(data.get('courier_id')) if data.get('courier_id') else None
        
        # Validate order_id format
        if not order_id or not isinstance(order_id, str):
            return error_response("Invalid order_id format", 400)
        
        # Validate delivery_address_id
        if delivery_address_id <= 0:
            return error_response("Invalid delivery_address_id", 400)
        
        # Validate courier_id if provided
        if courier_id is not None and courier_id <= 0:
            return error_response("Invalid courier_id", 400)
        
        shiprocket = ShipRocketController()
        response = shiprocket.create_shiprocket_orders_for_all_merchants(
            order_id=order_id,
            delivery_address_id=delivery_address_id,
            courier_id=courier_id
        )
        
        return success_response("ShipRocket orders created successfully for all merchants", response)
        
    except ValueError as e:
        return error_response(f"Invalid data format: {str(e)}", 400)
    except Exception as e:
        return error_response(f"ShipRocket order creation failed: {str(e)}", 500)

@shiprocket_bp.route('/pickup-locations', methods=['GET'])
@jwt_required()
def get_pickup_locations():
    """
    Get all pickup locations from ShipRocket
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    responses:
      200:
        description: Pickup locations retrieved successfully
      500:
        description: Internal server error
    """
    try:
        shiprocket = ShipRocketController()
        response = shiprocket.get_pickup_locations()
        return success_response("Pickup locations retrieved successfully", response)
        
    except Exception as e:
        return error_response(f"Failed to get pickup locations: {str(e)}", 500)

@shiprocket_bp.route('/merchant/<int:merchant_id>/pickup-location', methods=['POST'])
@jwt_required()
def create_merchant_pickup_location(merchant_id):
    """
    Create pickup location for a merchant in ShipRocket
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    parameters:
      - name: merchant_id
        in: path
        required: true
        type: integer
        description: Merchant ID
    responses:
      200:
        description: Pickup location created successfully
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
    try:
        shiprocket = ShipRocketController()
        pickup_location_name = shiprocket.create_merchant_pickup_location(merchant_id)
        return success_response("Pickup location created successfully", {
            "pickup_location_name": pickup_location_name,
            "merchant_id": merchant_id
        })
        
    except Exception as e:
        return error_response(f"Failed to create pickup location: {str(e)}", 500)

@shiprocket_bp.route('/merchant/<int:merchant_id>/pickup-location', methods=['GET'])
@jwt_required()
def get_merchant_pickup_location(merchant_id):
    """
    Get or create pickup location for a merchant
    ---
    tags:
      - ShipRocket
    security:
      - Bearer: []
    parameters:
      - name: merchant_id
        in: path
        required: true
        type: integer
        description: Merchant ID
    responses:
      200:
        description: Pickup location retrieved/created successfully
      404:
        description: Merchant not found
      500:
        description: Internal server error
    """
    try:
        shiprocket = ShipRocketController()
        pickup_location_name = shiprocket.get_or_create_merchant_pickup_location(merchant_id)
        return success_response("Pickup location retrieved/created successfully", {
            "pickup_location_name": pickup_location_name,
            "merchant_id": merchant_id
        })
        
    except Exception as e:
        return error_response(f"Failed to get pickup location: {str(e)}", 500) 