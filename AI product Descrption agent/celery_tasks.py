"""
Celery Tasks for AI Product Description Generation
Handles asynchronous processing of product descriptions
"""
from celery import Task
from celery_app import celery_app
from main import generate_product_description
from core.cache import cache
import time
import traceback

class CallbackTask(Task):
    """Custom task class with callbacks"""
    def on_success(self, retval, task_id, args, kwargs):
        """Success callback"""
        print(f"✅ Task {task_id} completed successfully")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure callback"""
        print(f"❌ Task {task_id} failed: {str(exc)}")

@celery_app.task(
    name='celery_tasks.generate_product_description_task',
    base=CallbackTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Retry after 60 seconds
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True
)
def generate_product_description_task(
    self,
    product_id: str,
    product_name: str,
    image_urls: list,
    tone: str = "professional and informative"
):
    """
    Celery task for generating product descriptions
    
    Args:
        self: Task instance (bound)
        product_id: Unique product identifier
        product_name: Name of the product
        image_urls: List of product image URLs
        tone: Desired tone/style
    
    Returns:
        Dictionary with generated content
    """
    try:
        # Update task state to 'PROCESSING'
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'processing',
                'product_id': product_id,
                'product_name': product_name,
                'stage': 'Starting AI generation...'
            }
        )
        
        # Check cache first
        cached_result = cache.get_product_description(product_name, image_urls, tone)
        if cached_result:
            return {
                'success': True,
                'cached': True,
                'result': cached_result,
                'product_id': product_id,
                'product_name': product_name
            }
        
        # Update state: Image processing
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'processing',
                'product_id': product_id,
                'stage': 'Analyzing product images...',
                'progress': 25
            }
        )
        
        # Generate description
        start_time = time.time()
        result = generate_product_description(
            product_id=product_id,
            product_name=product_name,
            image_urls=image_urls,
            optional_prompt=tone
        )
        processing_time = time.time() - start_time
        
        # Check for errors in generation
        if "error" in result.get("generated_content", {}):
            raise Exception(f"AI generation error: {result['generated_content'].get('error')}")
        
        # Cache the successful result
        cache.set_product_description(
            product_name=product_name,
            image_urls=image_urls,
            tone=tone,
            description=result
        )
        
        # Return success
        return {
            'success': True,
            'cached': False,
            'result': result,
            'product_id': product_id,
            'product_name': product_name,
            'processing_time': round(processing_time, 2),
            'timestamp': time.time()
        }
        
    except Exception as e:
        # Log the error
        error_trace = traceback.format_exc()
        print(f"❌ Task failed for product '{product_name}': {str(e)}")
        print(error_trace)
        
        # Update task state to FAILURE with details
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'failed',
                'error': str(e),
                'product_id': product_id,
                'product_name': product_name
            }
        )
        
        # Re-raise for Celery to handle retries
        raise

@celery_app.task(name='celery_tasks.batch_generate_descriptions')
def batch_generate_descriptions(products: list):
    """
    Generate descriptions for multiple products in batch
    
    Args:
        products: List of dicts with product_id, product_name, image_urls, tone
    
    Returns:
        List of task IDs
    """
    task_ids = []
    for product in products:
        task = generate_product_description_task.delay(
            product_id=product['product_id'],
            product_name=product['product_name'],
            image_urls=product['image_urls'],
            tone=product.get('tone', 'professional and informative')
        )
        task_ids.append({
            'product_id': product['product_id'],
            'task_id': task.id
        })
    
    return task_ids

@celery_app.task(name='celery_tasks.clear_cache')
def clear_cache_task():
    """Background task to clear cache"""
    try:
        cache.clear_all()
        return {'success': True, 'message': 'Cache cleared successfully'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

