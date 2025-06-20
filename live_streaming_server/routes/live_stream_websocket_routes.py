from flask import Blueprint, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sys
from datetime import datetime

# Add the parent directory to the path to import from main backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.database import db
from models.live_stream import LiveStream, LiveStreamComment, LiveStreamViewer, StreamStatus
from auth.models.models import User

live_stream_ws_bp = Blueprint('live_stream_websocket', __name__)
socketio = SocketIO(cors_allowed_origins="*")

# Store active connections
active_connections = {}

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")
    active_connections[request.sid] = {
        'user_id': None,
        'stream_id': None,
        'is_merchant': False
    }

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")
    if request.sid in active_connections:
        # Remove from stream room if connected
        connection_data = active_connections[request.sid]
        if connection_data['stream_id']:
            leave_room(f"stream_{connection_data['stream_id']}")
        
        # Update viewer count if user was viewing
        if connection_data['user_id'] and connection_data['stream_id']:
            try:
                viewer = LiveStreamViewer.query.filter_by(
                    stream_id=connection_data['stream_id'],
                    user_id=connection_data['user_id'],
                    left_at=None
                ).first()
                
                if viewer:
                    viewer.left_at = datetime.utcnow()
                    
                    live_stream = LiveStream.get_by_id(connection_data['stream_id'])
                    if live_stream and live_stream.viewers_count > 0:
                        live_stream.viewers_count -= 1
                    
                    db.session.commit()
                    
                    # Emit updated viewer count
                    emit('viewer_count_update', {
                        'stream_id': connection_data['stream_id'],
                        'viewers_count': live_stream.viewers_count
                    }, room=f"stream_{connection_data['stream_id']}")
            except Exception as e:
                print(f"Error updating viewer on disconnect: {e}")
        
        del active_connections[request.sid]

@socketio.on('join_stream')
def handle_join_stream(data):
    """Handle joining a live stream."""
    try:
        user_id = data.get('user_id')
        stream_id = data.get('stream_id')
        is_merchant = data.get('is_merchant', False)
        
        if not user_id or not stream_id:
            emit('error', {'message': 'user_id and stream_id are required'})
            return
        
        # Verify stream exists and is live
        live_stream = LiveStream.get_by_id(stream_id)
        if not live_stream:
            emit('error', {'message': 'Stream not found'})
            return
        
        if not live_stream.is_live:
            emit('error', {'message': 'Stream is not live'})
            return
        
        # Join stream room
        room = f"stream_{stream_id}"
        join_room(room)
        
        # Update connection data
        active_connections[request.sid] = {
            'user_id': user_id,
            'stream_id': stream_id,
            'is_merchant': is_merchant
        }
        
        # Add viewer record if not merchant
        if not is_merchant:
            existing_viewer = LiveStreamViewer.query.filter_by(
                stream_id=stream_id,
                user_id=user_id,
                left_at=None
            ).first()
            
            if not existing_viewer:
                viewer = LiveStreamViewer(
                    stream_id=stream_id,
                    user_id=user_id
                )
                live_stream.viewers_count += 1
                db.session.add(viewer)
                db.session.commit()
        
        # Emit join confirmation
        emit('joined_stream', {
            'stream_id': stream_id,
            'viewers_count': live_stream.viewers_count
        })
        
        # Emit updated viewer count to all viewers
        emit('viewer_count_update', {
            'stream_id': stream_id,
            'viewers_count': live_stream.viewers_count
        }, room=room)
        
        print(f"User {user_id} joined stream {stream_id}")
        
    except Exception as e:
        emit('error', {'message': f'Error joining stream: {str(e)}'})

@socketio.on('leave_stream')
def handle_leave_stream(data):
    """Handle leaving a live stream."""
    try:
        stream_id = data.get('stream_id')
        user_id = data.get('user_id')
        
        if not stream_id or not user_id:
            emit('error', {'message': 'stream_id and user_id are required'})
            return
        
        room = f"stream_{stream_id}"
        leave_room(room)
        
        # Update viewer record
        viewer = LiveStreamViewer.query.filter_by(
            stream_id=stream_id,
            user_id=user_id,
            left_at=None
        ).first()
        
        if viewer:
            viewer.left_at = datetime.utcnow()
            
            live_stream = LiveStream.get_by_id(stream_id)
            if live_stream and live_stream.viewers_count > 0:
                live_stream.viewers_count -= 1
            
            db.session.commit()
            
            # Emit updated viewer count
            emit('viewer_count_update', {
                'stream_id': stream_id,
                'viewers_count': live_stream.viewers_count
            }, room=room)
        
        # Update connection data
        if request.sid in active_connections:
            active_connections[request.sid]['stream_id'] = None
        
        emit('left_stream', {'stream_id': stream_id})
        print(f"User {user_id} left stream {stream_id}")
        
    except Exception as e:
        emit('error', {'message': f'Error leaving stream: {str(e)}'})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a chat message."""
    try:
        user_id = data.get('user_id')
        stream_id = data.get('stream_id')
        content = data.get('content')
        
        if not user_id or not stream_id or not content:
            emit('error', {'message': 'user_id, stream_id, and content are required'})
            return
        
        # Verify stream exists and is live
        live_stream = LiveStream.get_by_id(stream_id)
        if not live_stream or not live_stream.is_live:
            emit('error', {'message': 'Stream not found or not live'})
            return
        
        # Create comment
        comment = LiveStreamComment(
            stream_id=stream_id,
            user_id=user_id,
            content=content
        )
        
        db.session.add(comment)
        db.session.commit()
        
        # Get user info
        user = User.query.get(user_id)
        user_info = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role.value
        }
        
        # Emit message to all viewers
        message_data = {
            'comment_id': comment.comment_id,
            'stream_id': stream_id,
            'user': user_info,
            'content': content,
            'created_at': comment.created_at.isoformat()
        }
        
        emit('new_message', message_data, room=f"stream_{stream_id}")
        
    except Exception as e:
        emit('error', {'message': f'Error sending message: {str(e)}'})

@socketio.on('like_stream')
def handle_like_stream(data):
    """Handle liking a stream."""
    try:
        stream_id = data.get('stream_id')
        
        if not stream_id:
            emit('error', {'message': 'stream_id is required'})
            return
        
        # Verify stream exists and is live
        live_stream = LiveStream.get_by_id(stream_id)
        if not live_stream or not live_stream.is_live:
            emit('error', {'message': 'Stream not found or not live'})
            return
        
        # Increment likes count
        live_stream.likes_count += 1
        db.session.commit()
        
        # Emit updated likes count
        emit('likes_update', {
            'stream_id': stream_id,
            'likes_count': live_stream.likes_count
        }, room=f"stream_{stream_id}")
        
    except Exception as e:
        emit('error', {'message': f'Error liking stream: {str(e)}'})

@socketio.on('merchant_start_stream')
def handle_merchant_start_stream(data):
    """Handle merchant starting a stream."""
    try:
        user_id = data.get('user_id')
        stream_id = data.get('stream_id')
        
        if not user_id or not stream_id:
            emit('error', {'message': 'user_id and stream_id are required'})
            return
        
        # Verify stream exists and belongs to merchant
        live_stream = LiveStream.get_by_id(stream_id)
        if not live_stream:
            emit('error', {'message': 'Stream not found'})
            return
        
        # Check if user is the merchant
        if live_stream.merchant.user_id != user_id:
            emit('error', {'message': 'Unauthorized to start this stream'})
            return
        
        # Start stream
        live_stream.status = StreamStatus.LIVE
        live_stream.is_live = True
        live_stream.start_time = datetime.utcnow()
        
        db.session.commit()
        
        # Emit stream started event
        emit('stream_started', {
            'stream_id': stream_id,
            'start_time': live_stream.start_time.isoformat()
        }, room=f"stream_{stream_id}")
        
        # Emit to all connected clients
        emit('stream_status_update', {
            'stream_id': stream_id,
            'status': 'live',
            'is_live': True
        }, broadcast=True)
        
    except Exception as e:
        emit('error', {'message': f'Error starting stream: {str(e)}'})

@socketio.on('merchant_end_stream')
def handle_merchant_end_stream(data):
    """Handle merchant ending a stream."""
    try:
        user_id = data.get('user_id')
        stream_id = data.get('stream_id')
        
        if not user_id or not stream_id:
            emit('error', {'message': 'user_id and stream_id are required'})
            return
        
        # Verify stream exists and belongs to merchant
        live_stream = LiveStream.get_by_id(stream_id)
        if not live_stream:
            emit('error', {'message': 'Stream not found'})
            return
        
        # Check if user is the merchant
        if live_stream.merchant.user_id != user_id:
            emit('error', {'message': 'Unauthorized to end this stream'})
            return
        
        # End stream
        live_stream.status = StreamStatus.ENDED
        live_stream.is_live = False
        live_stream.end_time = datetime.utcnow()
        
        # Update all active viewers
        active_viewers = LiveStreamViewer.get_active_viewers(stream_id)
        for viewer in active_viewers:
            viewer.left_at = datetime.utcnow()
        
        db.session.commit()
        
        # Emit stream ended event
        emit('stream_ended', {
            'stream_id': stream_id,
            'end_time': live_stream.end_time.isoformat()
        }, room=f"stream_{stream_id}")
        
        # Emit to all connected clients
        emit('stream_status_update', {
            'stream_id': stream_id,
            'status': 'ended',
            'is_live': False
        }, broadcast=True)
        
    except Exception as e:
        emit('error', {'message': f'Error ending stream: {str(e)}'})

# Initialize socketio with the app
def init_socketio(app):
    """Initialize SocketIO with the Flask app."""
    socketio.init_app(app, cors_allowed_origins="*")
    return socketio 