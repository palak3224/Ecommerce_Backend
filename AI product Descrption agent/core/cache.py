"""
Redis Cache Layer for AI Product Description Generator
Provides caching for:
- Complete product descriptions
- Image analysis results
- Job statuses
"""
import redis
import json
import hashlib
from typing import Optional, Dict, List
from datetime import timedelta
from core.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD,
    CACHE_ENABLED, CACHE_TTL_DESCRIPTIONS, CACHE_TTL_IMAGE_ANALYSIS, CACHE_TTL_JOBS
)

class RedisCache:
    """Redis cache manager with type-specific TTLs"""
    
    def __init__(self):
        """Initialize Redis connection"""
        self.enabled = CACHE_ENABLED
        if not self.enabled:
            print("⚠️  Cache is disabled")
            return
            
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            # Test connection
            self.redis.ping()
            print(f"✅ Redis connected: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"❌ Redis connection failed: {str(e)}")
            self.enabled = False
    
    def _generate_cache_key(self, prefix: str, *args) -> str:
        """Generate a consistent cache key from arguments"""
        # Create a hash of the arguments for a clean key
        key_data = "|".join(str(arg) for arg in args)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def _generate_product_key(self, product_name: str, image_urls: List[str], tone: str) -> str:
        """Generate cache key for product descriptions"""
        # Sort URLs for consistency
        sorted_urls = sorted(image_urls)
        return self._generate_cache_key("product_desc", product_name, "|".join(sorted_urls), tone)
    
    def _generate_image_key(self, image_url: str, analysis_type: str = "detailed") -> str:
        """Generate cache key for image analysis"""
        return self._generate_cache_key("image_analysis", image_url, analysis_type)
    
    def get_product_description(self, product_name: str, image_urls: List[str], tone: str) -> Optional[Dict]:
        """
        Get cached product description
        
        Args:
            product_name: Name of the product
            image_urls: List of image URLs
            tone: Description tone
            
        Returns:
            Cached description dict or None
        """
        if not self.enabled:
            return None
            
        try:
            key = self._generate_product_key(product_name, image_urls, tone)
            cached = self.redis.get(key)
            if cached:
                print(f"✅ Cache HIT: Product description for '{product_name}'")
                return json.loads(cached)
            else:
                print(f"❌ Cache MISS: Product description for '{product_name}'")
                return None
        except Exception as e:
            print(f"⚠️  Cache get error: {str(e)}")
            return None
    
    def set_product_description(self, product_name: str, image_urls: List[str], 
                                tone: str, description: Dict, ttl: Optional[int] = None):
        """
        Cache product description
        
        Args:
            product_name: Name of the product
            image_urls: List of image URLs
            tone: Description tone
            description: Description data to cache
            ttl: Time to live in seconds (default: CACHE_TTL_DESCRIPTIONS)
        """
        if not self.enabled:
            return
            
        try:
            key = self._generate_product_key(product_name, image_urls, tone)
            ttl = ttl or CACHE_TTL_DESCRIPTIONS
            self.redis.setex(
                key,
                ttl,
                json.dumps(description)
            )
            print(f"💾 Cached product description for '{product_name}' (TTL: {ttl}s)")
        except Exception as e:
            print(f"⚠️  Cache set error: {str(e)}")
    
    def get_image_analysis(self, image_url: str, analysis_type: str = "detailed") -> Optional[str]:
        """
        Get cached image analysis
        
        Args:
            image_url: URL of the image
            analysis_type: Type of analysis (detailed, attributes, caption)
            
        Returns:
            Cached analysis text or None
        """
        if not self.enabled:
            return None
            
        try:
            key = self._generate_image_key(image_url, analysis_type)
            cached = self.redis.get(key)
            if cached:
                print(f"✅ Cache HIT: Image analysis for {image_url[:50]}...")
                return cached
            else:
                print(f"❌ Cache MISS: Image analysis for {image_url[:50]}...")
                return None
        except Exception as e:
            print(f"⚠️  Cache get error: {str(e)}")
            return None
    
    def set_image_analysis(self, image_url: str, analysis_type: str, 
                          analysis_result: str, ttl: Optional[int] = None):
        """
        Cache image analysis result
        
        Args:
            image_url: URL of the image
            analysis_type: Type of analysis
            analysis_result: Analysis text to cache
            ttl: Time to live in seconds (default: CACHE_TTL_IMAGE_ANALYSIS)
        """
        if not self.enabled:
            return
            
        try:
            key = self._generate_image_key(image_url, analysis_type)
            ttl = ttl or CACHE_TTL_IMAGE_ANALYSIS
            self.redis.setex(key, ttl, analysis_result)
            print(f"💾 Cached image analysis (TTL: {ttl}s)")
        except Exception as e:
            print(f"⚠️  Cache set error: {str(e)}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get cached job status"""
        if not self.enabled:
            return None
            
        try:
            key = f"job:{job_id}"
            cached = self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            print(f"⚠️  Cache get error: {str(e)}")
            return None
    
    def set_job_status(self, job_id: str, status: Dict, ttl: Optional[int] = None):
        """Cache job status"""
        if not self.enabled:
            return
            
        try:
            key = f"job:{job_id}"
            ttl = ttl or CACHE_TTL_JOBS
            self.redis.setex(key, ttl, json.dumps(status))
        except Exception as e:
            print(f"⚠️  Cache set error: {str(e)}")
    
    def delete_job_status(self, job_id: str):
        """Delete job status from cache"""
        if not self.enabled:
            return
            
        try:
            key = f"job:{job_id}"
            self.redis.delete(key)
        except Exception as e:
            print(f"⚠️  Cache delete error: {str(e)}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if not self.enabled:
            return {"enabled": False}
            
        try:
            info = self.redis.info('stats')
            return {
                "enabled": True,
                "total_connections": info.get('total_connections_received', 0),
                "total_commands": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "hit_rate": round(
                    info.get('keyspace_hits', 0) / 
                    max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100,
                    2
                )
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}
    
    def clear_all(self):
        """Clear all cached data (use with caution!)"""
        if not self.enabled:
            return
            
        try:
            self.redis.flushdb()
            print("🗑️  Cache cleared")
        except Exception as e:
            print(f"⚠️  Cache clear error: {str(e)}")

# Global cache instance
cache = RedisCache()

