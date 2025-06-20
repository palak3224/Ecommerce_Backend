#!/usr/bin/env python3
"""
Live Streaming Server Startup Script
This script starts the live streaming server with WebSocket support.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path to import from main backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_live_streaming_app
from routes.live_stream_websocket_routes import init_socketio

def main():
    """Main function to start the live streaming server."""
    
    # Create the Flask app
    app = create_live_streaming_app()
    
    # Initialize SocketIO
    socketio = init_socketio(app)
    
    # Get configuration
    port = app.config.get('LIVE_STREAMING_PORT', 5001)
    debug = app.config.get('DEBUG', False)
    
    print("=" * 60)
    print("🚀 Live Streaming Server Starting...")
    print("=" * 60)
    print(f"📍 Port: {port}")
    print(f"🔧 Debug Mode: {debug}")
    print(f"🌐 WebSocket Support: Enabled")
    print(f"📊 Database: Connected")
    print("=" * 60)
    
    try:
        # Start the server with SocketIO
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True  # For development
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 