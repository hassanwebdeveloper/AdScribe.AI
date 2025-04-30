import logging
from typing import Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from bson import ObjectId
from app.core.database import get_database
from app.core.config import settings
from app.services.metrics_service import MetricsService
import asyncio
import time
import random

logger = logging.getLogger(__name__)

class SchedulerService:
    # Class-level variables to track rate limits across all instances
    _last_collection_time = {}  # Track last collection time per user
    _collection_in_progress = set()  # Track users with collection in progress
    _global_request_count = 0  # Track total requests made
    _global_last_request_time = 0  # Track time of last request
    _GLOBAL_RATE_LIMIT = 100  # Maximum requests per day to Facebook API per app
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.metrics_service = MetricsService()
        # Don't initialize db in constructor
    
    @property
    def db(self):
        """Get database instance lazily when needed."""
        return get_database()
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")
    
    async def get_user_fb_credentials(self, user_id: str) -> Dict[str, str]:
        """Get Facebook credentials for a user from the database."""
        try:
            # Convert string ID to ObjectId
            user_object_id = ObjectId(user_id)
            user = await self.db.users.find_one({"_id": user_object_id})
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Check if user has metrics collection enabled
            if not user.get("is_collecting_metrics", False):
                raise ValueError(f"Metrics collection is not enabled for user {user_id}")
            
            # Check for OAuth credentials first
            if "facebook_credentials" in user and user["facebook_credentials"].get("access_token"):
                return {
                    "access_token": user["facebook_credentials"]["access_token"],
                    "account_id": user["facebook_credentials"].get("account_id", "")
                }
            
            # Fall back to manual API key if OAuth not available
            if "fb_graph_api_key" in user and user["fb_graph_api_key"]:
                return {
                    "access_token": user["fb_graph_api_key"],
                    "account_id": user.get("fb_ad_account_id", "")
                }
            
            raise ValueError(f"No valid Facebook credentials found for user {user_id}")
        except Exception as e:
            logger.error(f"Error getting user credentials: {str(e)}")
            raise
    
    async def get_all_users_with_fb_credentials(self) -> List[Dict[str, Any]]:
        """Get all users with either OAuth or manual Facebook credentials and metrics collection enabled."""
        cursor = self.db.users.find({
            "$and": [
                {
                    "$or": [
                        {"facebook_credentials": {"$exists": True}},
                        {"fb_graph_api_key": {"$exists": True, "$ne": ""}}
                    ]
                },
                {"is_collecting_metrics": True}
            ]
        })
        users = await cursor.to_list(length=100)  # Limit to 100 users for now
        return users
    
    async def schedule_metrics_collection_for_all_users(self):
        """Schedule metrics collection for all users with Facebook credentials and metrics collection enabled."""
        users = await self.get_all_users_with_fb_credentials()
        
        # Sort users to distribute collections more evenly
        random.shuffle(users)
        
        # Schedule collections with staggered start times to avoid rate limits
        for i, user in enumerate(users):
            user_id = str(user["_id"])
            # Stagger initial scheduling by adding delay
            delay = i * 60  # Delay each user by 1 minute
            await asyncio.sleep(0.1)  # Small delay between scheduling operations
            await self.schedule_metrics_collection_for_user(user_id, initial_delay=delay)
    
    async def schedule_metrics_collection_for_user(self, user_id: str, initial_delay: int = 0):
        """Schedule metrics collection for a specific user."""
        try:
            # Make sure scheduler is running
            if not self.scheduler.running:
                self.start()
                logger.info("Started scheduler for metrics collection")
            
            # Remove any existing job for this user
            self.remove_metrics_collection_job(user_id)
            
            # Get interval from settings
            interval_hours = settings.METRICS_COLLECTION_INTERVAL_HOURS
            
            # Convert to hours for logging but use seconds for the scheduler
            interval_seconds = interval_hours * 3600
            
            # Add jitter to prevent all jobs running at exactly the same time
            # jitter_minutes = random.randint(0, 60)
            
            # Schedule a new job to run at the configured interval
            self.scheduler.add_job(
                self.collect_metrics_for_user,
                trigger=IntervalTrigger(seconds=interval_seconds),
                id=f"metrics_collection_{user_id}",
                replace_existing=True,
                args=[user_id]
            )
            
            logger.info(f"Scheduled metrics collection for user {user_id} every {interval_hours} hours")
            
            # Run initially only if no data exists yet for this user and if specified delay
            should_run_initial = await self._should_run_initial_collection(user_id)
            
            if should_run_initial:
                try:
                    # Get Facebook credentials first to validate
                    credentials = await self.get_user_fb_credentials(user_id)
                    
                    # If credentials are valid, start collection
                    if credentials["access_token"] and credentials["account_id"]:
                        total_delay = initial_delay + 5  # Add 5 seconds base delay
                        logger.info(f"Starting initial metrics collection for user {user_id} with delay of {total_delay} seconds")
                        # Use delay to add a delay before first collection
                        asyncio.create_task(self._delayed_collect_metrics(user_id, delay_seconds=total_delay))
                    else:
                        logger.warning(f"Skipping initial collection for user {user_id}: Invalid credentials")
                except Exception as e:
                    logger.error(f"Error starting initial collection for user {user_id}: {str(e)}")
                    # Don't raise the error, just log it
                    # The scheduled job will try again later
            else:
                logger.info(f"Skipping initial collection for user {user_id}: Recent data exists")
            
        except Exception as e:
            logger.error(f"Error scheduling metrics collection for user {user_id}: {str(e)}")
            raise
    
    async def _should_run_initial_collection(self, user_id: str) -> bool:
        """Check if we should run an initial collection for this user."""
        try:
            # Check if user already has data from the last 24 hours
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            
            # Check if any metrics exist for this user in the last 24 hours
            count = await self.db.ad_metrics.count_documents({
                "user_id": user_id,
                "collected_at": {"$gte": one_day_ago}
            })
            
            # Only run initial collection if no recent data exists
            return count == 0
        except Exception as e:
            logger.error(f"Error checking if initial collection needed: {str(e)}")
            # Default to not running initial collection if there's an error
            return False
    
    async def _delayed_collect_metrics(self, user_id: str, delay_seconds: int = 0):
        """Collect metrics with a delay to avoid rate limits."""
        if delay_seconds > 0:
            logger.info(f"Delaying initial collection for user {user_id} by {delay_seconds} seconds")
            await asyncio.sleep(delay_seconds)
        
        try:
            await self.collect_metrics_for_user(user_id)
        except Exception as e:
            logger.error(f"Error in delayed metrics collection for user {user_id}: {str(e)}")
    
    def remove_metrics_collection_job(self, user_id: str):
        """Remove metrics collection job for a specific user."""
        job_id = f"metrics_collection_{user_id}"
        
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed metrics collection job for user {user_id}")
            else:
                logger.info(f"No job found to remove for user {user_id}")
        except Exception as e:
            logger.error(f"Error removing job for user {user_id}: {str(e)}")
            # Job might not exist, that's fine
            pass
    
    async def _check_rate_limit_status(self) -> bool:
        """Check if we're approaching global rate limits.
        Returns True if it's safe to proceed, False if we should delay.
        """
        # Calculate current rate
        current_time = time.time()
        self._global_request_count += 1
        
        # Check if we're making too many requests too quickly
        time_since_last = current_time - self._global_last_request_time
        if time_since_last < 1.0:  # Less than 1 second since last request
            logger.warning("Rate limit protection: Requests too frequent, delaying")
            return False
        
        # Check if we've made too many requests in the last day
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        try:
            
            # Group by user_id and collected_at (rounded to minute) to count collection runs
            # Each collection run = 1 API call regardless of how many ads were collected
            pipeline = [
                {
                    "$match": {
                        "collected_at": {"$gte": one_day_ago}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "user_id": "$user_id",
                            "collection_time": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d %H:%M",
                                    "date": "$collected_at"
                                }
                            }
                        }
                    }
                },
                {
                    "$count": "total_collections"
                }
            ]
            
            collection_results = await self.db.ad_metrics.aggregate(pipeline).to_list(1)
            estimated_api_calls = collection_results[0]["total_collections"] if collection_results else 0
            
            if estimated_api_calls > self._GLOBAL_RATE_LIMIT * 0.8:  # 80% of limit
                logger.warning(f"Rate limit protection: Approaching global limit ({estimated_api_calls} estimated calls)")
                return False
        except Exception as e:
            logger.error(f"Error checking rate limit status: {str(e)}")
        
        # Update last request time
        self._global_last_request_time = current_time
        return True
    
    async def collect_metrics_for_user(self, user_id: str):
        """Collect metrics for a specific user."""
        # Check if collection is already in progress for this user
        if user_id in self._collection_in_progress:
            logger.warning(f"Collection already in progress for user {user_id}, skipping")
            return []
        
        # Check time since last collection to avoid too frequent collections
        last_collection = self._last_collection_time.get(user_id, 0)
        time_since_last = time.time() - last_collection
        
        # Validate collection interval
        interval_hours = time_since_last / 3600  # Convert seconds to hours
        if not await self._validate_collection_interval(interval_hours):
            time_remaining = (settings.MIN_METRICS_COLLECTION_INTERVAL_HOURS * 3600) - time_since_last
            hours_remaining = time_remaining / 3600
            logger.warning(f"Rate limit protection: Too soon for user {user_id}, will collect again in {hours_remaining:.1f} hours")
            return []
        
        # Check global rate limits
        if not await self._check_rate_limit_status():
            logger.warning(f"Rate limit protection: Delaying collection for user {user_id}")
            # Try again later with exponential backoff
            delay = random.randint(10, 60) * 60  # 10-60 minutes
            asyncio.create_task(self._delayed_collect_metrics(user_id, delay_seconds=delay))
            return []
        
        # Mark collection as in progress
        self._collection_in_progress.add(user_id)
        
        try:
            start_time = time.time()
            
            # Get Facebook credentials
            credentials = await self.get_user_fb_credentials(user_id)
            
            # Collect and store metrics
            stored_metrics_ids = await self.metrics_service.collect_and_store_user_ad_metrics(
                user_id,
                credentials["access_token"],
                credentials["account_id"]
            )
            
            # Update last collection time
            self._last_collection_time[user_id] = time.time()
            
            # Log completion time
            duration = time.time() - start_time
            logger.info(f"Collected metrics for user {user_id}: {len(stored_metrics_ids)} ads in {duration:.1f} seconds")
            
            return stored_metrics_ids
        except Exception as e:
            logger.error(f"Error collecting metrics for user {user_id}: {str(e)}")
            return []
        finally:
            # Remove from in-progress set
            if user_id in self._collection_in_progress:
                self._collection_in_progress.remove(user_id)
    
    def is_job_running(self, user_id: str) -> bool:
        """Check if a job is currently running for a user."""
        try:
            job_id = f"metrics_collection_{user_id}"
            job = self.scheduler.get_job(job_id)
            return job is not None and job.next_run_time is not None
        except Exception as e:
            logger.error(f"Error checking job status for user {user_id}: {str(e)}")
            return False
    
    async def _validate_collection_interval(self, interval_hours: float) -> bool:
        """Validate if the collection interval is acceptable."""
        min_collection_interval_hours = settings.MIN_METRICS_COLLECTION_INTERVAL_HOURS
        if interval_hours < min_collection_interval_hours:
            logger.warning(f"Collection interval {interval_hours} hours is less than minimum allowed {min_collection_interval_hours} hours")
            return False
        return True 