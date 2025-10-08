"""
Redis-based Rate Limiter for API endpoints
Uses sliding window algorithm for accurate rate limiting
"""
import redis
import time
from typing import Tuple, Optional
from fastapi import Request, HTTPException
from core.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD,
    RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW,
    RATE_LIMIT_PREMIUM_REQUESTS, RATE_LIMIT_PREMIUM_WINDOW
)

class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm"""
    
    def __init__(self):
        """Initialize Redis connection for rate limiting"""
        self.enabled = RATE_LIMIT_ENABLED
        if not self.enabled:
            print("⚠️  Rate limiting is disabled")
            return
            
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=False,  # Use bytes for atomic operations
                socket_connect_timeout=5
            )
            # Test connection
            self.redis.ping()
            print(f"✅ Rate limiter connected to Redis: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"❌ Rate limiter Redis connection failed: {str(e)}")
            self.enabled = False
    
    def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting
        Priority: User ID > API Key > IP Address
        """
        # Check for user ID in headers (if your system has user authentication)
        user_id = request.headers.get('X-User-ID')
        if user_id:
            return f"user:{user_id}"
        
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"apikey:{api_key}"
        
        # Fallback to IP address
        # Check for forwarded IP (if behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            ip = forwarded_for.split(',')[0].strip()
        else:
            ip = request.client.host if request.client else 'unknown'
        
        return f"ip:{ip}"
    
    def _is_premium_user(self, request: Request) -> bool:
        """
        Check if user has premium access
        You can customize this based on your auth system
        """
        # Check for premium header
        is_premium = request.headers.get('X-Premium-User', 'false').lower() == 'true'
        
        # Or check for specific API key prefix
        api_key = request.headers.get('X-API-Key', '')
        if api_key.startswith('premium_'):
            is_premium = True
        
        return is_premium
    
    def _get_limits(self, is_premium: bool) -> Tuple[int, int]:
        """Get rate limit configuration based on user tier"""
        if is_premium:
            return RATE_LIMIT_PREMIUM_REQUESTS, RATE_LIMIT_PREMIUM_WINDOW
        return RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW
    
    def check_rate_limit(self, request: Request) -> Tuple[bool, dict]:
        """
        Check if request is within rate limits using sliding window
        
        Returns:
            Tuple of (is_allowed: bool, info: dict)
        """
        if not self.enabled:
            return True, {"rate_limiting": "disabled"}
        
        try:
            # Get identifier and limits
            identifier = self._get_identifier(request)
            is_premium = self._is_premium_user(request)
            max_requests, window_seconds = self._get_limits(is_premium)
            
            # Redis key for this identifier
            key = f"ratelimit:{identifier}"
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiry on key
            pipe.expire(key, window_seconds + 1)
            
            # Execute pipeline
            results = pipe.execute()
            request_count = results[1]  # Count after removing old entries
            
            # Check if limit exceeded
            is_allowed = request_count < max_requests
            
            # Calculate reset time
            if not is_allowed:
                # Get oldest request in window
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    reset_time = int(oldest[0][1] + window_seconds)
                else:
                    reset_time = int(current_time + window_seconds)
            else:
                reset_time = int(current_time + window_seconds)
            
            info = {
                "identifier": identifier,
                "is_premium": is_premium,
                "requests_made": request_count + 1,  # Including current request
                "requests_limit": max_requests,
                "window_seconds": window_seconds,
                "reset_at": reset_time,
                "retry_after": reset_time - int(current_time) if not is_allowed else 0
            }
            
            return is_allowed, info
            
        except Exception as e:
            # On error, allow the request (fail open)
            print(f"⚠️  Rate limiter error: {str(e)}")
            return True, {"error": str(e), "rate_limiting": "failed_open"}
    
    def get_rate_limit_headers(self, info: dict) -> dict:
        """Generate rate limit headers for response"""
        return {
            "X-RateLimit-Limit": str(info.get("requests_limit", 0)),
            "X-RateLimit-Remaining": str(max(0, info.get("requests_limit", 0) - info.get("requests_made", 0))),
            "X-RateLimit-Reset": str(info.get("reset_at", 0)),
            "X-RateLimit-Window": str(info.get("window_seconds", 0))
        }
    
    async def __call__(self, request: Request):
        """Middleware callable for FastAPI"""
        is_allowed, info = self.check_rate_limit(request)
        
        if not is_allowed:
            headers = self.get_rate_limit_headers(info)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {info['retry_after']} seconds.",
                    "retry_after": info['retry_after'],
                    "limit": info['requests_limit'],
                    "window": info['window_seconds']
                },
                headers=headers
            )
        
        # Store rate limit info in request state for later use
        request.state.rate_limit_info = info
        return info

# Global rate limiter instance
rate_limiter = RateLimiter()

