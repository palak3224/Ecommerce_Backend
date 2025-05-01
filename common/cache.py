import json
import functools
from flask_caching import Cache
import redis

# Initialize Flask-Caching extension
cache = Cache()

def get_redis_client(app=None):
    """Get Redis client based on app config or environment variables."""
    if app and app.config.get('REDIS_URL'):
        redis_url = app.config.get('REDIS_URL')
    else:
        # Fallback to default local Redis
        redis_url = 'redis://localhost:6379/0'
    
    return redis.from_url(redis_url)

def cache_key_prefix(key_prefix):
    """Create a cache key prefix for differentiating cached data types."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cached(timeout=300, key_prefix='default'):
    """Custom caching decorator with prefix support."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate a cache key based on function name and arguments
            key_parts = [key_prefix, f.__name__]
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
            
            # Add kwargs in alphabetical order
            sorted_kwargs = sorted(kwargs.items())
            for k, v in sorted_kwargs:
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}:{v}")
            
            cache_key = ":".join(key_parts)
            
            # Try to get result from cache
            cached_result = cache.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            try:
                cache.set(cache_key, json.dumps(result), timeout=timeout)
            except (TypeError, ValueError):
                # If result can't be JSON serialized, don't cache
                pass
            
            return result
        return decorated_function
    return decorator