import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.core.database import get_database
from app.models.ad_metrics import AdMetrics
from app.services.facebook_service import FacebookAdService
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from app.services.scheduler_interface import SchedulerInterface

logger = logging.getLogger(__name__)

class MetricsService:
    def __init__(self, scheduler: Optional[SchedulerInterface] = None):
        self.scheduler = scheduler
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance lazily when needed."""
        return get_database()
    
    async def get_collection_status(self, user_id: str) -> bool:
        """Get the current collection status for a user."""
        try:
            user = await self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise ValueError(f"User not found: {user_id}")
            return user.get("is_collecting_metrics", False)
        except Exception as e:
            logger.error(f"Error getting collection status: {str(e)}")
            raise ValueError(f"Error getting collection status: {str(e)}")
    
    async def toggle_collection(self, user_id: str) -> bool:
        """Toggle the collection status for a user."""
        try:
            # Get current status
            current_status = await self.get_collection_status(user_id)
            new_status = not current_status
            
            # Update user's collection status
            result = await self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_collecting_metrics": new_status}}
            )
            
            if result.modified_count == 0:
                raise ValueError("Failed to update collection status")
            
            # Handle scheduling if scheduler is available
            if self.scheduler:
                if new_status:
                    try:
                        await self.scheduler.schedule_metrics_collection_for_user(user_id)
                        logger.info(f"Started metrics collection for user {user_id}")
                    except Exception as e:
                        # If scheduling fails, revert the status
                        await self.db.users.update_one(
                            {"_id": ObjectId(user_id)},
                            {"$set": {"is_collecting_metrics": False}}
                        )
                        logger.error(f"Error starting metrics collection: {str(e)}")
                        raise ValueError(f"Error starting metrics collection: {str(e)}")
                else:
                    self.scheduler.remove_metrics_collection_job(user_id)
                    logger.info(f"Stopped metrics collection for user {user_id}")
            
            return new_status
            
        except Exception as e:
            logger.error(f"Error toggling collection: {str(e)}")
            raise ValueError(f"Error toggling collection: {str(e)}")
    
    async def store_ad_metrics(self, metrics_data: Dict[str, Any]) -> str:
        """Store ad metrics in the database."""
        try:
            # Create AdMetrics object
            metrics = AdMetrics(**metrics_data)
            
            # Insert into database
            result = await self.db.ad_metrics.insert_one(metrics.model_dump(by_alias=True))
            
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error storing ad metrics: {str(e)}")
            raise
    
    async def get_user_metrics(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get metrics for a specific user."""
        cursor = self.db.ad_metrics.find({"user_id": user_id}).skip(skip).limit(limit).sort("collected_at", -1)
        metrics = await cursor.to_list(length=limit)
        return metrics
    
    async def get_ad_metrics_history(self, ad_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical metrics for a specific ad."""
        cursor = self.db.ad_metrics.find({"ad_id": ad_id}).skip(skip).limit(limit).sort("collected_at", -1)
        metrics = await cursor.to_list(length=limit)
        return metrics

    async def collect_and_store_user_ad_metrics(
        self, 
        user_id: str, 
        fb_access_token: str, 
        fb_account_id: str
    ) -> List[str]:
        """Collect and store metrics for all ads of a user."""
        try:
            # Create Facebook service
            fb_service = FacebookAdService(fb_access_token, fb_account_id)
            
            # Get all ads with their metrics in one call
            metrics_list = await fb_service.collect_ad_metrics(user_id)
            
            stored_metrics_ids = []
            
            # Store each set of metrics
            for metrics_data in metrics_list:
                try:
                    metrics_id = await self.store_ad_metrics(metrics_data)
                    stored_metrics_ids.append(metrics_id)
                except Exception as e:
                    logger.error(f"Error storing metrics for ad {metrics_data.get('ad_id')}: {str(e)}")
                    continue
            
            return stored_metrics_ids
        except Exception as e:
            logger.error(f"Error collecting and storing metrics for user {user_id}: {str(e)}")
            raise 

    async def collect_and_store_metrics(self, user_id: str) -> None:
        """Collect and store metrics for a user."""
        try:
            # Get user from database
            user = await self.user_service.get_user(user_id)
            if not user:
                raise ValueError(f"User not found: {user_id}")
            
            # Validate Facebook credentials
            if not user.get("facebook_access_token") or not user.get("facebook_account_id"):
                raise ValueError("Facebook credentials not found")
            
            # Initialize Facebook service
            fb_service = FacebookAdService(
                access_token=user["facebook_access_token"],
                account_id=user["facebook_account_id"]
            )
            
            try:
                # Collect metrics
                metrics = await fb_service.collect_ad_metrics(user_id)
                
                if not metrics:
                    logger.warning(f"No metrics collected for user {user_id}")
                    return
                
                # Store metrics
                await self.store_metrics(metrics)
                logger.info(f"Successfully collected and stored metrics for user {user_id}")
                
            except ValueError as e:
                # Handle Facebook API errors
                logger.error(f"Facebook API error for user {user_id}: {str(e)}")
                raise
            except Exception as e:
                # Handle other errors
                logger.error(f"Error collecting metrics for user {user_id}: {str(e)}")
                raise
            
        except Exception as e:
            error_msg = f"Error collecting and storing metrics for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) 