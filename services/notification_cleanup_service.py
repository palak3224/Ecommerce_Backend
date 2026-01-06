# services/notification_cleanup_service.py
"""
Incremental notification cleanup service.
Processes read notifications in small batches to avoid heavy database load.
"""
from datetime import datetime, timezone, timedelta
from common.database import db
from models.merchant_notification import MerchantNotification
from flask import current_app


class NotificationCleanupService:
    """Service for incremental cleanup of old read notifications."""
    
    # Configuration
    DEFAULT_DAYS_OLD = 90  # Delete read notifications older than 90 days
    BATCH_SIZE = 100  # Process 100 notifications at a time
    MAX_BATCHES_PER_RUN = 10  # Maximum batches to process per run
    
    @classmethod
    def cleanup_incremental(cls, days_old=None, batch_size=None, max_batches=None):
        """
        Incrementally clean up old read notifications in small batches.
        This prevents heavy database load by processing notifications gradually.
        
        Args:
            days_old: Number of days old (default: 90)
            batch_size: Number of notifications to process per batch (default: 100)
            max_batches: Maximum batches to process per run (default: 10)
            
        Returns:
            dict: Cleanup statistics
        """
        days_old = days_old or cls.DEFAULT_DAYS_OLD
        batch_size = batch_size or cls.BATCH_SIZE
        max_batches = max_batches or cls.MAX_BATCHES_PER_RUN
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        total_deleted = 0
        batches_processed = 0
        
        try:
            while batches_processed < max_batches:
                # Get a batch of old read notifications
                old_notifications = MerchantNotification.query.filter(
                    MerchantNotification.is_read == True,
                    MerchantNotification.created_at < cutoff_date
                ).order_by(MerchantNotification.created_at.asc()).limit(batch_size).all()
                
                if not old_notifications:
                    # No more notifications to clean
                    break
                
                # Delete this batch
                batch_count = len(old_notifications)
                for notification in old_notifications:
                    db.session.delete(notification)
                
                # Commit this batch
                try:
                    db.session.commit()
                    total_deleted += batch_count
                    batches_processed += 1
                    
                    current_app.logger.info(
                        f"Notification cleanup: Deleted batch of {batch_count} notifications "
                        f"(Total: {total_deleted}, Batches: {batches_processed})"
                    )
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error committing notification cleanup batch: {str(e)}")
                    break
                
                # If this batch was smaller than batch_size, we're done
                if batch_count < batch_size:
                    break
            
            return {
                'success': True,
                'total_deleted': total_deleted,
                'batches_processed': batches_processed,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in incremental notification cleanup: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'total_deleted': total_deleted,
                'batches_processed': batches_processed
            }
    
    @classmethod
    def get_cleanup_stats(cls, days_old=None):
        """
        Get statistics about notifications that would be cleaned up.
        
        Args:
            days_old: Number of days old (default: 90)
            
        Returns:
            dict: Statistics about old read notifications
        """
        days_old = days_old or cls.DEFAULT_DAYS_OLD
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        count = MerchantNotification.query.filter(
            MerchantNotification.is_read == True,
            MerchantNotification.created_at < cutoff_date
        ).count()
        
        return {
            'old_read_notifications_count': count,
            'cutoff_date': cutoff_date.isoformat(),
            'days_old': days_old
        }

