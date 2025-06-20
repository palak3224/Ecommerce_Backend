# Live Streaming Server

This is a separate server for handling live streaming functionality while reusing the main e-commerce backend's database, models, and common utilities.

## Architecture

The live streaming server is designed as a separate service that:

- **Shares the same database** with the main e-commerce backend
- **Reuses existing models** (LiveStream, Product, User, etc.)
- **Uses the same authentication** system
- **Provides real-time WebSocket** functionality for live streaming
- **Runs on a separate port** (default: 5001)

## Directory Structure

```
live_streaming_server/
├── app.py                          # Main Flask application
├── run_server.py                   # Server startup script
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── routes/
│   ├── live_stream_routes.py       # REST API routes
│   └── live_stream_websocket_routes.py  # WebSocket routes
└── controllers/
    └── live_stream_controller.py   # Business logic
```

## Features

### REST API Endpoints

- `POST /api/live-streams/` - Create a new live stream
- `GET /api/live-streams/` - Get all live streams with filtering
- `GET /api/live-streams/<id>` - Get specific live stream
- `PUT /api/live-streams/<id>` - Update live stream
- `DELETE /api/live-streams/<id>` - Delete live stream
- `POST /api/live-streams/<id>/start` - Start live stream
- `POST /api/live-streams/<id>/end` - End live stream
- `GET /api/live-streams/available-slots` - Get available time slots
- `POST /api/live-streams/<id>/join` - Join stream as viewer
- `POST /api/live-streams/<id>/leave` - Leave stream

### WebSocket Events

- `connect` - Client connects to server
- `disconnect` - Client disconnects from server
- `join_stream` - Join a live stream room
- `leave_stream` - Leave a live stream room
- `send_message` - Send chat message
- `like_stream` - Like a stream
- `merchant_start_stream` - Merchant starts stream
- `merchant_end_stream` - Merchant ends stream

## Setup Instructions

### 1. Install Dependencies

```bash
cd live_streaming_server
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the `live_streaming_server` directory:

```env
# Server Configuration
LIVE_STREAMING_PORT=5001
FLASK_ENV=development

# Database (same as main backend)
DATABASE_URI=mysql+pymysql://root:nihalsql@localhost:3306/ecommerce_db

# JWT (same as main backend)
JWT_SECRET_KEY=your_jwt_secret_key

# Redis Cache (same as main backend)
REDIS_URL=redis://localhost:6379/0

# Other configurations (inherit from main backend)
SECRET_KEY=your_secret_key
```

### 3. Start the Server

```bash
# Option 1: Using the startup script
python run_server.py

# Option 2: Direct execution
python app.py
```

The server will start on port 5001 (or the port specified in LIVE_STREAMING_PORT).

## Integration with Frontend

### Update Frontend Configuration

Update your frontend environment variables to include the live streaming server URL:

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_LIVE_STREAMING_URL=http://localhost:5001
```

### WebSocket Connection

In your frontend, connect to the WebSocket server:

```javascript
import io from 'socket.io-client';

const socket = io('http://localhost:5001');

// Join a stream
socket.emit('join_stream', {
  user_id: currentUser.id,
  stream_id: streamId,
  is_merchant: currentUser.role === 'merchant'
});

// Listen for messages
socket.on('new_message', (message) => {
  console.log('New message:', message);
});

// Send a message
socket.emit('send_message', {
  user_id: currentUser.id,
  stream_id: streamId,
  content: 'Hello everyone!'
});
```

## API Usage Examples

### Create a Live Stream

```bash
curl -X POST http://localhost:5001/api/live-streams/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Launch Live",
    "product_id": 123,
    "description": "Join us for the launch of our new product!",
    "scheduled_time": "2024-01-15T14:00:00Z"
  }'
```

### Get Available Time Slots

```bash
curl -X GET "http://localhost:5001/api/live-streams/available-slots?product_id=123&date=2024-01-15" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Start a Stream

```bash
curl -X POST http://localhost:5001/api/live-streams/456/start \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
python run_server.py
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-flask

# Run tests
pytest tests/
```

## Production Deployment

### Using Gunicorn

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5001 app:create_live_streaming_app()
```

### Using Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "run_server.py"]
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure the main backend directory is in the Python path
2. **Database Connection**: Verify the database URI is correct and accessible
3. **WebSocket Issues**: Ensure eventlet is installed for production WebSocket support
4. **Port Conflicts**: Change the LIVE_STREAMING_PORT if 5001 is already in use

### Logs

The server logs will show:
- Connection/disconnection events
- Stream start/end events
- Error messages
- WebSocket events

## Security Considerations

- All endpoints require JWT authentication
- Merchant endpoints require merchant role verification
- WebSocket connections are validated
- CORS is configured for specific origins
- Input validation is implemented for all endpoints

## Performance

- Redis caching for frequently accessed data
- Database connection pooling
- WebSocket connection management
- Efficient viewer count tracking

## Monitoring

The server includes health check endpoints:

- `GET /health` - Basic health check
- Database connection status
- Service status information 