from flask import jsonify

def success_response(message, data=None, status_code=200):
    response = {
        "message": message,
        "data": data
    }
    return jsonify(response), status_code

def error_response(message, status_code=400):
    return jsonify({"message": message}), status_code 