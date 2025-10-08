"""
Celery Application Configuration
Handles background task processing for AI product descriptions
"""
from celery import Celery
from core.config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_TRACK_STARTED,
    CELERY_TASK_TIME_LIMIT,
    CELERY_TASK_SOFT_TIME_LIMIT
)

# Initialize Celery app
celery_app = Celery(
    'ai_product_description',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['celery_tasks']  # Import tasks module
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=CELERY_TASK_TRACK_STARTED,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    task_acks_late=True,  # Acknowledge task after completion
    worker_prefetch_multiplier=1,  # Fetch one task at a time for better distribution
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
    result_expires=86400,  # Results expire after 24 hours
    task_default_queue='ai_descriptions',  # Default queue name
    task_default_exchange='ai_descriptions',
    task_default_routing_key='ai_descriptions',
)

# Optional: Define task routes for different priorities
celery_app.conf.task_routes = {
    'celery_tasks.generate_product_description_task': {
        'queue': 'ai_descriptions',
        'routing_key': 'ai_descriptions'
    },
}

if __name__ == '__main__':
    celery_app.start()

