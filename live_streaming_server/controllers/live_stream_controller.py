import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add the parent directory to the path to import from main backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.database import db
from models.live_stream import LiveStream, LiveStreamComment, LiveStreamViewer, StreamStatus
from models.product import Product
from auth.models.models import MerchantProfile, User

class LiveStreamController:
    """Controller for live streaming operations."""
    
    @staticmethod
    def create_stream(merchant_id: int, product_id: int, title: str, 
                     description: str, scheduled_time: datetime) -> Dict:
        """Create a new live stream."""
        try:
            # Validate product exists and belongs to merchant
            product = Product.query.filter_by(
                product_id=product_id,
                merchant_id=merchant_id
            ).first()
            
            if not product:
                raise ValueError("Product not found or not owned by merchant")
            
            # Check if slot is available
            if not LiveStream.is_slot_available(product_id, scheduled_time):
                raise ValueError("Time slot is not available for this product")
            
            # Generate unique stream key
            stream_key = str(uuid.uuid4())
            
            # Create live stream
            live_stream = LiveStream(
                merchant_id=merchant_id,
                product_id=product_id,
                title=title,
                description=description,
                scheduled_time=scheduled_time,
                stream_key=stream_key,
                status=StreamStatus.SCHEDULED
            )
            
            db.session.add(live_stream)
            db.session.commit()
            
            return live_stream.serialize()
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def get_streams(filters: Dict = None, page: int = 1, per_page: int = 10) -> Dict:
        """Get live streams with optional filtering and pagination."""
        try:
            query = LiveStream.query.filter_by(deleted_at=None)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    query = query.filter_by(status=StreamStatus(filters['status']))
                
                if 'merchant_id' in filters:
                    query = query.filter_by(merchant_id=filters['merchant_id'])
                
                if 'product_id' in filters:
                    query = query.filter_by(product_id=filters['product_id'])
                
                if 'is_live' in filters:
                    query = query.filter_by(is_live=filters['is_live'])
            
            # Order by scheduled time
            query = query.order_by(LiveStream.scheduled_time.desc())
            
            # Paginate
            pagination = query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            streams = [stream.serialize() for stream in pagination.items]
            
            return {
                'streams': streams,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
            
        except Exception as e:
            raise e
    
    @staticmethod
    def get_stream_by_id(stream_id: int) -> Optional[Dict]:
        """Get a specific live stream by ID."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            return live_stream.serialize() if live_stream else None
            
        except Exception as e:
            raise e
    
    @staticmethod
    def update_stream(stream_id: int, merchant_id: int, updates: Dict) -> Dict:
        """Update a live stream."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Check ownership
            if live_stream.merchant_id != merchant_id:
                raise ValueError("Unauthorized to update this stream")
            
            # Update fields
            if 'title' in updates:
                live_stream.title = updates['title']
            
            if 'description' in updates:
                live_stream.description = updates['description']
            
            if 'scheduled_time' in updates:
                scheduled_time = updates['scheduled_time']
                if isinstance(scheduled_time, str):
                    scheduled_time = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                
                # Check if slot is available (excluding current stream)
                if not LiveStream.is_slot_available(live_stream.product_id, scheduled_time):
                    raise ValueError("Time slot is not available")
                
                live_stream.scheduled_time = scheduled_time
            
            db.session.commit()
            return live_stream.serialize()
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def delete_stream(stream_id: int, merchant_id: int) -> bool:
        """Delete a live stream (soft delete)."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Check ownership
            if live_stream.merchant_id != merchant_id:
                raise ValueError("Unauthorized to delete this stream")
            
            # Soft delete
            live_stream.deleted_at = datetime.utcnow()
            live_stream.status = StreamStatus.CANCELLED
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def start_stream(stream_id: int, merchant_id: int) -> Dict:
        """Start a live stream."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Check ownership
            if live_stream.merchant_id != merchant_id:
                raise ValueError("Unauthorized to start this stream")
            
            # Check if stream can be started
            if live_stream.status != StreamStatus.SCHEDULED:
                raise ValueError("Stream cannot be started. Invalid status.")
            
            # Start stream
            live_stream.status = StreamStatus.LIVE
            live_stream.is_live = True
            live_stream.start_time = datetime.utcnow()
            
            db.session.commit()
            return live_stream.serialize()
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def end_stream(stream_id: int, merchant_id: int) -> Dict:
        """End a live stream."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Check ownership
            if live_stream.merchant_id != merchant_id:
                raise ValueError("Unauthorized to end this stream")
            
            # End stream
            live_stream.status = StreamStatus.ENDED
            live_stream.is_live = False
            live_stream.end_time = datetime.utcnow()
            
            # Update viewer records
            active_viewers = LiveStreamViewer.get_active_viewers(stream_id)
            for viewer in active_viewers:
                viewer.left_at = datetime.utcnow()
            
            db.session.commit()
            return live_stream.serialize()
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def get_available_slots(product_id: int, date: datetime.date) -> List[str]:
        """Get available time slots for a product on a specific date."""
        try:
            available_slots = []
            
            # Generate available slots (9 AM to 9 PM, hourly slots)
            for hour in range(9, 21):  # 9 AM to 8 PM
                slot_time = datetime.combine(date, datetime.min.time().replace(hour=hour))
                
                # Check if slot is available
                if LiveStream.is_slot_available(product_id, slot_time):
                    available_slots.append(f"{hour:02d}:00")
            
            return available_slots
            
        except Exception as e:
            raise e
    
    @staticmethod
    def join_stream(stream_id: int, user_id: int) -> bool:
        """Join a live stream as a viewer."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Check if stream is live
            if not live_stream.is_live:
                raise ValueError("Stream is not live")
            
            # Check if user is already viewing
            existing_viewer = LiveStreamViewer.query.filter_by(
                stream_id=stream_id,
                user_id=user_id,
                left_at=None
            ).first()
            
            if existing_viewer:
                return True  # Already viewing
            
            # Create viewer record
            viewer = LiveStreamViewer(
                stream_id=stream_id,
                user_id=user_id
            )
            
            # Update viewer count
            live_stream.viewers_count += 1
            
            db.session.add(viewer)
            db.session.commit()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def leave_stream(stream_id: int, user_id: int) -> bool:
        """Leave a live stream."""
        try:
            # Get viewer record
            viewer = LiveStreamViewer.query.filter_by(
                stream_id=stream_id,
                user_id=user_id,
                left_at=None
            ).first()
            
            if not viewer:
                return True  # Not currently viewing
            
            # Update viewer record
            viewer.left_at = datetime.utcnow()
            
            # Update viewer count
            live_stream = LiveStream.get_by_id(stream_id)
            if live_stream and live_stream.viewers_count > 0:
                live_stream.viewers_count -= 1
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def add_comment(stream_id: int, user_id: int, content: str) -> Dict:
        """Add a comment to a live stream."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream or not live_stream.is_live:
                raise ValueError("Stream not found or not live")
            
            # Create comment
            comment = LiveStreamComment(
                stream_id=stream_id,
                user_id=user_id,
                content=content
            )
            
            db.session.add(comment)
            db.session.commit()
            
            return comment.serialize()
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def like_stream(stream_id: int) -> int:
        """Like a stream and return updated likes count."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream or not live_stream.is_live:
                raise ValueError("Stream not found or not live")
            
            # Increment likes count
            live_stream.likes_count += 1
            db.session.commit()
            
            return live_stream.likes_count
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def get_stream_stats(stream_id: int) -> Dict:
        """Get statistics for a live stream."""
        try:
            live_stream = LiveStream.get_by_id(stream_id)
            if not live_stream:
                raise ValueError("Live stream not found")
            
            # Get viewer history
            viewer_history = LiveStreamViewer.get_viewer_history(stream_id)
            
            # Calculate unique viewers
            unique_viewers = len(set(viewer.user_id for viewer in viewer_history))
            
            # Calculate average watch time
            total_watch_time = 0
            completed_watches = 0
            
            for viewer in viewer_history:
                if viewer.left_at:
                    watch_time = (viewer.left_at - viewer.joined_at).total_seconds()
                    total_watch_time += watch_time
                    completed_watches += 1
            
            avg_watch_time = total_watch_time / completed_watches if completed_watches > 0 else 0
            
            return {
                'stream_id': stream_id,
                'total_viewers': unique_viewers,
                'current_viewers': live_stream.viewers_count,
                'total_likes': live_stream.likes_count,
                'average_watch_time_minutes': round(avg_watch_time / 60, 2),
                'total_comments': live_stream.comments.count(),
                'stream_duration_minutes': 0  # Calculate if stream has ended
            }
            
        except Exception as e:
            raise e 