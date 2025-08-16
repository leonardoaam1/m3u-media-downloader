import time
import json
from functools import wraps
from flask import request, jsonify, current_app, g
from datetime import datetime, timedelta
import hashlib
import redis
from typing import Dict, Optional, Tuple

class RateLimiter:
    """
    Advanced rate limiting system with multiple strategies:
    - Fixed window
    - Sliding window
    - Token bucket
    - IP-based and API key-based limiting
    """
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or self._get_redis_client()
        self.default_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'requests_per_day': 10000,
            'burst_limit': 10  # Additional requests allowed in burst
        }
    
    def _get_redis_client(self):
        """Get Redis client for storing rate limit data"""
        try:
            import redis
            return redis.Redis(
                host=current_app.config.get('REDIS_HOST', 'localhost'),
                port=current_app.config.get('REDIS_PORT', 6379),
                db=current_app.config.get('REDIS_DB', 1),
                decode_responses=True
            )
        except:
            return None
    
    def _get_client_id(self) -> str:
        """Get unique client identifier (API key or IP)"""
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"api_key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        
        # Fallback to IP address
        ip = request.remote_addr
        if request.headers.get('X-Forwarded-For'):
            ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        
        return f"ip:{ip}"
    
    def _get_rate_limits(self, client_id: str) -> Dict[str, int]:
        """Get rate limits for specific client"""
        # Check if client has custom limits (e.g., premium API key)
        if client_id.startswith('api_key:'):
            # Could check database for custom limits based on API key
            # For now, use default limits
            return self.default_limits
        
        # IP-based clients get more restrictive limits
        return {
            'requests_per_minute': 30,
            'requests_per_hour': 500,
            'requests_per_day': 5000,
            'burst_limit': 5
        }
    
    def _create_rate_limit_key(self, client_id: str, window: str) -> str:
        """Create Redis key for rate limiting"""
        endpoint = request.endpoint or 'unknown'
        return f"rate_limit:{client_id}:{endpoint}:{window}"
    
    def _sliding_window_check(self, client_id: str, limit: int, window_seconds: int) -> Tuple[bool, Dict]:
        """Implement sliding window rate limiting"""
        if not self.redis_client:
            return True, {}
        
        now = time.time()
        window_start = now - window_seconds
        key = f"sliding:{self._create_rate_limit_key(client_id, str(window_seconds))}"
        
        # Clean old entries and count current requests
        pipe = self.redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        current_requests = results[1]
        
        allowed = current_requests < limit
        reset_time = now + window_seconds
        
        return allowed, {
            'limit': limit,
            'remaining': max(0, limit - current_requests - 1),
            'reset': int(reset_time),
            'window': window_seconds
        }
    
    def _token_bucket_check(self, client_id: str, rate: float, capacity: int) -> Tuple[bool, Dict]:
        """Implement token bucket rate limiting"""
        if not self.redis_client:
            return True, {}
        
        now = time.time()
        key = f"bucket:{self._create_rate_limit_key(client_id, 'bucket')}"
        
        # Get current bucket state
        bucket_data = self.redis_client.get(key)
        if bucket_data:
            bucket = json.loads(bucket_data)
            last_refill = bucket['last_refill']
            tokens = bucket['tokens']
        else:
            last_refill = now
            tokens = capacity
        
        # Calculate tokens to add
        time_passed = now - last_refill
        tokens_to_add = time_passed * rate
        tokens = min(capacity, tokens + tokens_to_add)
        
        # Check if request can be served
        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False
        
        # Save bucket state
        bucket_data = {
            'tokens': tokens,
            'last_refill': now
        }
        self.redis_client.setex(key, 3600, json.dumps(bucket_data))
        
        return allowed, {
            'limit': capacity,
            'remaining': int(tokens),
            'reset': int(now + (capacity - tokens) / rate) if rate > 0 else int(now + 3600),
            'type': 'token_bucket'
        }
    
    def check_rate_limit(self, 
                        requests_per_minute: Optional[int] = None,
                        requests_per_hour: Optional[int] = None,
                        requests_per_day: Optional[int] = None,
                        burst_limit: Optional[int] = None,
                        use_token_bucket: bool = False) -> Tuple[bool, Dict, int]:
        """
        Check if request is within rate limits
        
        Returns:
            Tuple of (allowed, headers, status_code)
        """
        client_id = self._get_client_id()
        limits = self._get_rate_limits(client_id)
        
        # Override with provided limits
        if requests_per_minute is not None:
            limits['requests_per_minute'] = requests_per_minute
        if requests_per_hour is not None:
            limits['requests_per_hour'] = requests_per_hour
        if requests_per_day is not None:
            limits['requests_per_day'] = requests_per_day
        if burst_limit is not None:
            limits['burst_limit'] = burst_limit
        
        headers = {}
        
        # Check different time windows
        checks = [
            ('minute', limits['requests_per_minute'], 60),
            ('hour', limits['requests_per_hour'], 3600),
            ('day', limits['requests_per_day'], 86400)
        ]
        
        if use_token_bucket:
            # Use token bucket for burst handling
            rate = limits['requests_per_minute'] / 60.0  # tokens per second
            capacity = limits['burst_limit']
            allowed, bucket_info = self._token_bucket_check(client_id, rate, capacity)
            
            if not allowed:
                headers.update({
                    'X-RateLimit-Limit': str(capacity),
                    'X-RateLimit-Remaining': str(bucket_info['remaining']),
                    'X-RateLimit-Reset': str(bucket_info['reset']),
                    'X-RateLimit-Type': 'token_bucket',
                    'Retry-After': str(max(1, bucket_info['reset'] - int(time.time())))
                })
                return False, headers, 429
        else:
            # Use sliding window for each time period
            for window_name, limit, window_seconds in checks:
                allowed, window_info = self._sliding_window_check(client_id, limit, window_seconds)
                
                # Add headers for the most restrictive window (minute)
                if window_name == 'minute':
                    headers.update({
                        'X-RateLimit-Limit': str(limit),
                        'X-RateLimit-Remaining': str(window_info['remaining']),
                        'X-RateLimit-Reset': str(window_info['reset']),
                        'X-RateLimit-Window': str(window_seconds)
                    })
                
                if not allowed:
                    headers['Retry-After'] = str(window_seconds)
                    return False, headers, 429
        
        return True, headers, 200
    
    def get_client_stats(self, client_id: Optional[str] = None) -> Dict:
        """Get rate limiting statistics for a client"""
        if not client_id:
            client_id = self._get_client_id()
        
        if not self.redis_client:
            return {}
        
        stats = {}
        windows = [('minute', 60), ('hour', 3600), ('day', 86400)]
        
        for window_name, window_seconds in windows:
            key = f"sliding:{self._create_rate_limit_key(client_id, str(window_seconds))}"
            current_requests = self.redis_client.zcard(key)
            
            stats[window_name] = {
                'requests': current_requests,
                'window_seconds': window_seconds
            }
        
        return stats
    
    def reset_client_limits(self, client_id: Optional[str] = None) -> bool:
        """Reset rate limits for a client (admin function)"""
        if not client_id:
            client_id = self._get_client_id()
        
        if not self.redis_client:
            return False
        
        # Find all keys for this client
        pattern = f"*rate_limit:{client_id}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            self.redis_client.delete(*keys)
        
        # Also reset token bucket
        bucket_pattern = f"*bucket:{client_id}:*"
        bucket_keys = self.redis_client.keys(bucket_pattern)
        if bucket_keys:
            self.redis_client.delete(*bucket_keys)
        
        return True

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(requests_per_minute: int = 60,
               requests_per_hour: int = 1000,
               requests_per_day: int = 10000,
               burst_limit: int = 10,
               use_token_bucket: bool = False,
               key_func=None):
    """
    Decorator for rate limiting endpoints
    
    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
        requests_per_day: Maximum requests per day
        burst_limit: Additional burst capacity for token bucket
        use_token_bucket: Use token bucket instead of sliding window
        key_func: Custom function to generate rate limit key
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting in development if configured
            if current_app.config.get('RATE_LIMITING_ENABLED', True) == False:
                return f(*args, **kwargs)
            
            # Check rate limits
            allowed, headers, status_code = rate_limiter.check_rate_limit(
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
                requests_per_day=requests_per_day,
                burst_limit=burst_limit,
                use_token_bucket=use_token_bucket
            )
            
            if not allowed:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': 'Too many requests. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED'
                })
                response.status_code = status_code
                
                # Add rate limit headers
                for header, value in headers.items():
                    response.headers[header] = value
                
                return response
            
            # Execute the function
            response = f(*args, **kwargs)
            
            # Add rate limit headers to successful responses
            if hasattr(response, 'headers'):
                for header, value in headers.items():
                    response.headers[header] = value
            
            return response
        
        return decorated_function
    return decorator

def strict_rate_limit(requests_per_minute: int = 10,
                     requests_per_hour: int = 100,
                     requests_per_day: int = 1000):
    """Strict rate limiting for sensitive endpoints"""
    return rate_limit(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        requests_per_day=requests_per_day,
        burst_limit=5,
        use_token_bucket=True
    )

def lenient_rate_limit(requests_per_minute: int = 120,
                      requests_per_hour: int = 5000,
                      requests_per_day: int = 50000):
    """Lenient rate limiting for read-only endpoints"""
    return rate_limit(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        requests_per_day=requests_per_day,
        burst_limit=20,
        use_token_bucket=False
    )

# Middleware to add rate limit info to all API responses
def add_rate_limit_headers():
    """Add rate limit information to response headers"""
    if request.path.startswith('/api/'):
        client_id = rate_limiter._get_client_id()
        stats = rate_limiter.get_client_stats(client_id)
        
        # Add current usage info to response
        g.rate_limit_stats = stats
