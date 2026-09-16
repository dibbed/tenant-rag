"""
Rate Limiting Middleware
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed to make a request
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request is allowed, False otherwise
        """
        async with self._lock:
            current_time = time.time()
            user_requests = self.requests[user_id]
            
            # Remove old requests outside the window
            while user_requests and user_requests[0] < current_time - self.window_seconds:
                user_requests.popleft()
            
            # Check if under limit
            if len(user_requests) < self.max_requests:
                user_requests.append(current_time)
                return True
            
            return False
    
    async def get_remaining_requests(self, user_id: int) -> int:
        """Get remaining requests for user"""
        async with self._lock:
            current_time = time.time()
            user_requests = self.requests[user_id]
            
            # Remove old requests
            while user_requests and user_requests[0] < current_time - self.window_seconds:
                user_requests.popleft()
            
            return max(0, self.max_requests - len(user_requests))
    
    async def get_reset_time(self, user_id: int) -> Optional[float]:
        """Get time when rate limit resets for user"""
        async with self._lock:
            user_requests = self.requests[user_id]
            if not user_requests:
                return None
            
            return user_requests[0] + self.window_seconds
