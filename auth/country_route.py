from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from http import HTTPStatus

from auth.models.country_config import CountryConfig, CountryCode

country_bp = Blueprint('country', __name__, url_prefix='/api/merchants')

@country_bp.route('/country-config/<country_code>', methods=['GET'])
def get_country_config(country_code):
    """
    Get country-specific configuration including document requirements, validations, and field requirements.
    ---
    tags:
      - Countries
    parameters:
      - in: path
        name: country_code
        type: string
        required: true
        description: Two-letter country code (e.g., 'US', 'IN')
    responses:
      200:
        description: Country configuration retrieved successfully
        schema:
          type: object
          properties:
            country_code:
              type: string
            country_name:
              type: string
            required_documents:
              type: array
              items:
                type: object
                properties:
                  type:
                    type: string
                  name:
                    type: string
                  required:
                    type: boolean
            field_validations:
              type: object
              additionalProperties:
                type: object
            bank_fields:
              type: object
              additionalProperties:
                type: object
            tax_fields:
              type: object
              additionalProperties:
                type: object
      400:
        description: Invalid country code
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """
    try:
        # Validate country code
        if country_code not in [c.value for c in CountryCode]:
            return jsonify({
                'error': 'Invalid country code',
                'message': f"Invalid country code. Supported codes: {[c.value for c in CountryCode]}"
            }), HTTPStatus.BAD_REQUEST
        
        # Get country configuration
        config = {
            'country_code': country_code,
            'country_name': CountryConfig.get_country_name(country_code),
            'required_documents': [
                {
                    'type': doc.value,
                    'name': doc.value.replace('_', ' ').title(),
                    # Only PAN card and Aadhar are required; others optional
                    'required': doc.value in ['pan_card', 'aadhar']
                } for doc in CountryConfig.get_required_documents(country_code)
            ],
            'field_validations': CountryConfig.get_field_validations(country_code),
            'bank_fields': CountryConfig.get_bank_fields(country_code),
            'tax_fields': CountryConfig.get_tax_fields(country_code)
        }
        
        return jsonify(config), HTTPStatus.OK
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@country_bp.route('/supported-countries', methods=['GET'])
def get_supported_countries():
    """
    Get list of all supported countries.
    ---
    tags:
      - Countries
    responses:
      200:
        description: List of supported countries retrieved successfully
        schema:
          type: object
          properties:
            countries:
              type: array
              items:
                type: object
                properties:
                  code:
                    type: string
                  name:
                    type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """
    try:
        countries = [
            {
                'code': country.value,
                'name': CountryConfig.get_country_name(country.value)
            }
            for country in CountryCode
        ]
        
        return jsonify({
            'countries': countries
        }), HTTPStatus.OK
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR 