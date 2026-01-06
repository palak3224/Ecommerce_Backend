# controllers/reels_errors.py
"""
Error codes and messages for Reels module.
"""

# Error code constants
REEL_UPLOAD_FAILED = "REEL_UPLOAD_FAILED"
STORAGE_ERROR = "STORAGE_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"
PRODUCT_VALIDATION_ERROR = "PRODUCT_VALIDATION_ERROR"
FILE_VALIDATION_ERROR = "FILE_VALIDATION_ERROR"
AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
NOT_FOUND_ERROR = "NOT_FOUND_ERROR"
RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
TRANSACTION_ERROR = "TRANSACTION_ERROR"
CACHE_ERROR = "CACHE_ERROR"


def create_error_response(error_code, message, details=None, status_code=400):
    """
    Create a structured error response.
    
    Args:
        error_code: Error code constant
        message: User-friendly error message
        details: Optional additional details dict
        status_code: HTTP status code
        
    Returns:
        tuple: (jsonify response, status_code)
    """
    from flask import jsonify
    
    response = {
        'error': message,
        'code': error_code
    }
    
    if details:
        response['details'] = details
    
    return jsonify(response), status_code

