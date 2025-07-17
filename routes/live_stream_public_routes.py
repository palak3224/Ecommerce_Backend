from flask import Blueprint, request, jsonify
from controllers.live_stream_public_controller import LiveStreamPublicController
from flask_cors import cross_origin

live_stream_public_bp = Blueprint('live_stream_public_bp', __name__, url_prefix='/api/live-streams')

@live_stream_public_bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_public_live_streams():
    """
    Get all public live streams (optionally filter by status: LIVE, SCHEDULED)
    ---
    tags:
      - Live Streams
    parameters:
      - in: query
        name: status
        type: string
        required: false
        enum: [LIVE, SCHEDULED]
        description: Filter by stream status
    responses:
      200:
        description: List of live streams
    """
    status = request.args.get('status')
    streams = LiveStreamPublicController.list_public_streams(status)
    return jsonify(streams), 200

@live_stream_public_bp.route('/<int:stream_id>', methods=['GET'])
@cross_origin()
def get_public_live_stream_by_id(stream_id):
    """
    Get a public live stream by ID, including minimal product info.
    ---
    tags:
      - Live Streams
    parameters:
      - in: path
        name: stream_id
        type: integer
        required: true
        description: ID of the live stream
    responses:
      200:
        description: Live stream with minimal product info (image, name, selectable attributes, small description)
        schema:
          type: object
          properties:
            stream_id:
              type: integer
            product:
              type: object
              properties:
                product_id:
                  type: integer
                name:
                  type: string
                image:
                  type: string
                  nullable: true
                attributes:
                  type: array
                  items:
                    type: object
                    properties:
                      attribute_id:
                        type: integer
                      attribute_name:
                        type: string
                      value_code:
                        type: string
                        nullable: true
                      value_text:
                        type: string
                        nullable: true
                      value_label:
                        type: string
                        nullable: true
                      input_type:
                        type: string
                description:
                  type: string
                  nullable: true
      404:
        description: Live stream not found
    """
    stream = LiveStreamPublicController.get_public_stream_by_id(stream_id)
    if not stream:
        return jsonify({'error': 'Live stream not found'}), 404
    return jsonify(stream), 200 