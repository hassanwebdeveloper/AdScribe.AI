import logging
import time
from datetime import datetime, timedelta
import asyncio
import random
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database

logger = logging.getLogger(__name__)

class FacebookQuotaManager:
    """
    Manages Facebook API quota to prevent rate limit errors.
    Uses a global tracking system to keep track of API usage across all services.
    """
    # Singleton instance
    _instance = None
    
    # Rate limits for Facebook API
    HOURLY_LIMIT = 200
    DAILY_LIMIT = 1000
    
    # Quota tracking
    _requests_this_hour = 0
    _requests_today = 0
    _last_reset_hour = 0
    _last_reset_day = 0
    
    # Request timing
    _request_intervals = []  # Track time between requests
    _last_request_time = 0
    
    # Lock for synchronization
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FacebookQuotaManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the quota manager."""
        self._requests_this_hour = 0
        self._requests_today = 0
        self._last_reset_hour = int(time.time() // 3600)
        self._last_reset_day = int(time.time() // 86400)
        self._request_intervals = []
        self._last_request_time = 0
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance lazily when needed."""
        return get_database()
    
    async def _load_usage_stats(self):
        """Load usage statistics from database."""
        try:
            # Get the current hour and day
            current_hour = int(time.time() // 3600)
            current_day = int(time.time() // 86400)
            
            # Check if we need to reset counters
            if current_hour > self._last_reset_hour:
                self._requests_this_hour = 0
                self._last_reset_hour = current_hour
            
            if current_day > self._last_reset_day:
                self._requests_today = 0
                self._last_reset_day = current_day
            
            # Calculate usage from database
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            
            # Count API calls in the last hour and day
            # Each metric typically requires 2-3 API calls
            hour_metrics = await self.db.api_requests.count_documents({
                "service": "facebook",
                "timestamp": {"$gte": one_hour_ago}
            })
            
            day_metrics = await self.db.api_requests.count_documents({
                "service": "facebook",
                "timestamp": {"$gte": one_day_ago}
            })
            
            # Update counters
            self._requests_this_hour = max(self._requests_this_hour, hour_metrics)
            self._requests_today = max(self._requests_today, day_metrics)
            
            logger.debug(f"Loaded usage stats: {self._requests_this_hour}/hour, {self._requests_today}/day")
        except Exception as e:
            logger.error(f"Error loading usage stats: {str(e)}")
    
    async def _record_request(self):
        """Record a request to the database."""
        try:
            await self.db.api_requests.insert_one({
                "service": "facebook",
                "timestamp": datetime.utcnow(),
                "endpoint": "graph_api"
            })
        except Exception as e:
            logger.error(f"Error recording API request: {str(e)}")
    
    async def check_quota(self, user_id: str) -> bool:
        """
        Check if we have enough quota to make a request.
        Returns True if the request can proceed, False otherwise.
        """
        async with self._lock:
            await self._load_usage_stats()
            
            # Check hourly quota (95% to be safe)
            if self._requests_this_hour >= self.HOURLY_LIMIT * 0.95:
                logger.warning(f"Hourly quota exceeded: {self._requests_this_hour}/{self.HOURLY_LIMIT}")
                return False
            
            # Check daily quota (95% to be safe)
            if self._requests_today >= self.DAILY_LIMIT * 0.95:
                logger.warning(f"Daily quota exceeded: {self._requests_today}/{self.DAILY_LIMIT}")
                return False
            
            # Check request timing
            current_time = time.time()
            if self._last_request_time > 0:
                interval = current_time - self._last_request_time
                self._request_intervals.append(interval)
                
                # Keep only the last 100 intervals
                if len(self._request_intervals) > 100:
                    self._request_intervals = self._request_intervals[-100:]
                
                # Calculate average interval
                avg_interval = sum(self._request_intervals) / len(self._request_intervals)
                
                # If requests are too frequent, delay
                if avg_interval < 1.0 and len(self._request_intervals) > 5:
                    logger.warning(f"Requests too frequent (avg {avg_interval:.2f}s), delaying for user {user_id}")
                    return False
            
            # Update tracking
            self._last_request_time = current_time
            self._requests_this_hour += 1
            self._requests_today += 1
            
            # Record the request
            await self._record_request()
            
            return True
    
    async def check_and_reserve_quota(self, user_id: str, request_count: int = 1) -> bool:
        """
        Check if we have enough quota for multiple requests and reserve it.
        
        Args:
            user_id: The user ID making the request
            request_count: Number of API requests to reserve quota for
            
        Returns:
            True if quota is available and reserved, False otherwise
        """
        async with self._lock:
            await self._load_usage_stats()
            
            # Check if we have enough quota for all requests
            if self._requests_this_hour + request_count >= self.HOURLY_LIMIT * 0.95:
                logger.warning(f"Hourly quota would be exceeded: {self._requests_this_hour}/{self.HOURLY_LIMIT}, requested: {request_count}")
                return False
            
            if self._requests_today + request_count >= self.DAILY_LIMIT * 0.95:
                logger.warning(f"Daily quota would be exceeded: {self._requests_today}/{self.DAILY_LIMIT}, requested: {request_count}")
                return False
            
            # Reserve quota by updating counters
            self._requests_this_hour += request_count
            self._requests_today += request_count
            
            # Record the requests
            for _ in range(request_count):
                await self._record_request()
            
            logger.info(f"Reserved quota for {request_count} requests for user {user_id}")
            return True
    
    async def wait_for_quota(self, user_id: str, max_wait_seconds: int = 300) -> bool:
        """
        Wait until quota is available.
        Returns True if quota became available, False if max wait time was exceeded.
        """
        wait_time = 0
        while wait_time < max_wait_seconds:
            if await self.check_quota(user_id):
                return True
            
            # Exponential backoff with jitter
            delay = min(5 * (2 ** (wait_time // 30)), 60) + random.uniform(0, 2)
            logger.info(f"Waiting {delay:.1f}s for quota to become available for user {user_id}")
            await asyncio.sleep(delay)
            wait_time += delay
        
        logger.error(f"Quota wait timeout ({max_wait_seconds}s) exceeded for user {user_id}")
        return False
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota status for monitoring."""
        async with self._lock:
            await self._load_usage_stats()
            
            return {
                "hourly_usage": self._requests_this_hour,
                "hourly_limit": self.HOURLY_LIMIT,
                "hourly_percent": (self._requests_this_hour / self.HOURLY_LIMIT) * 100,
                "daily_usage": self._requests_today,
                "daily_limit": self.DAILY_LIMIT,
                "daily_percent": (self._requests_today / self.DAILY_LIMIT) * 100,
                "avg_interval": sum(self._request_intervals) / len(self._request_intervals) if self._request_intervals else 0
            } 