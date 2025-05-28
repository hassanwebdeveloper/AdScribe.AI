import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from app.core.base_service import BaseService
from app.core.database import get_database, get_metrics_collection, get_users_collection
from app.models.ad_metrics import AdMetrics
from app.services.facebook_service import FacebookAdService
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from app.services.scheduler_interface import SchedulerInterface

logger = logging.getLogger(__name__)

class MetricsService(BaseService):
    def __init__(self, scheduler: Optional[SchedulerInterface] = None):
        super().__init__()
        self.scheduler = scheduler
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance lazily when needed."""
        return get_database()
    
    async def get_collection_status(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> bool:
        """Get the current collection status for a user."""
        try:
            if user_data is None:
                user_data = await self.find_user_by_id(user_id)
            
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            return user_data.get("is_collecting_metrics", False)
        except Exception as e:
            logger.error(f"Error getting collection status: {str(e)}")
            raise ValueError(f"Error getting collection status: {str(e)}")
    
    async def toggle_collection(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> bool:
        """Toggle the collection status for a user."""
        try:
            if user_data is None:
                user_data = await self.find_user_by_id(user_id)
            
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Get current status
            current_status = user_data.get("is_collecting_metrics", False)
            new_status = not current_status
            
            # Update user's collection status
            success = await self.update_user_field(user_id, {"is_collecting_metrics": new_status})
            
            if not success:
                raise ValueError("Failed to update collection status")
            
            # Handle scheduling if scheduler is available
            if self.scheduler:
                if new_status:
                    try:
                        await self.scheduler.schedule_metrics_collection_for_user(user_id)
                        logger.info(f"Started metrics collection for user {user_id}")
                    except Exception as e:
                        # If scheduling fails, revert the status
                        await self.update_user_field(user_id, {"is_collecting_metrics": False})
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
    
    async def get_metrics_by_date_range(self, user_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get metrics by date range from MongoDB.
        Accepts date range as string formatted as YYYY-MM-DD.
        """
        try:
            # Convert string dates to datetime objects
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if isinstance(start_date, str) else start_date
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if isinstance(end_date, str) else end_date
            
            # Include the full end day
            end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
            
            collection = await get_metrics_collection()
            
            # Query metrics using the collected_at date field
            cursor = collection.find({
                "user_id": user_id,  # Use string user_id as stored in metrics
                "collected_at": {
                    "$gte": start_date_obj,
                    "$lte": end_date_obj
                }
            })
            
            # Convert to list
            metrics = await cursor.to_list(length=None)
            
            # Log metrics count for debugging
            logger.info(f"Found {len(metrics)} metrics for user {user_id} from {start_date} to {end_date}")
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting metrics by date range: {str(e)}")
            return []
    
    async def has_complete_data_for_range(self, user_id: str, start_date: str, end_date: str) -> bool:
        """
        Check if we have metrics data for each day in the specified date range.
        Returns True if we have complete data, False otherwise.
        """
        try:
            # Convert string dates to datetime objects
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if isinstance(start_date, str) else start_date
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if isinstance(end_date, str) else end_date
            
            # Calculate expected number of days in the date range
            expected_days = (end_date_obj - start_date_obj).days + 1
            logger.info(f"Checking data completeness for user {user_id} from {start_date} to {end_date} ({expected_days} days)")
            
            # Get the metrics collection
            collection = await get_metrics_collection()
            
            # First check if we have any data at all for this user
            count = await collection.count_documents({"user_id": user_id})
            if count == 0:
                logger.info(f"No metrics data found for user {user_id}")
                return False
            
            # Count metrics in the date range
            date_range_count = await collection.count_documents({
                "user_id": user_id,
                "collected_at": {
                    "$gte": start_date_obj,
                    "$lte": end_date_obj
                }
            })
            logger.info(f"Found {date_range_count} metrics in date range for user {user_id}")
            
            # Now use aggregation to group by date and see how many unique dates we have
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "collected_at": {
                            "$gte": start_date_obj,
                            "$lte": end_date_obj
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d", 
                                "date": "$collected_at"
                            }
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "dates": {"$push": "$_id"},
                        "total_days": {"$sum": 1}
                    }
                }
            ]
            
            result = await collection.aggregate(pipeline).to_list(length=1)
            
            # If no results, we don't have any data
            if not result:
                logger.info(f"No data found for user {user_id} from {start_date} to {end_date}, expected {expected_days} days")
                return False
                
            days_with_data = result[0].get("total_days", 0)
            dates_found = result[0].get("dates", [])
            
            logger.info(f"Found data for {days_with_data} days out of {expected_days} expected days")
            logger.debug(f"Dates with data: {sorted(dates_found)}")
            
            # Consider data complete if we have at least 80% of the expected days
            # This accounts for potential gaps in Facebook data
            completeness_threshold = 0.8
            is_complete = days_with_data >= (expected_days * completeness_threshold)
            
            logger.info(f"Data completeness: {days_with_data}/{expected_days} = {days_with_data/expected_days:.2%}, threshold: {completeness_threshold:.0%}, complete: {is_complete}")
            
            return is_complete
            
        except Exception as e:
            logger.error(f"Error checking data completeness: {str(e)}")
            return False
    
    async def get_aggregated_metrics(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get aggregated metrics for a date range."""
        try:
            collection = await get_metrics_collection()
            
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "collected_at": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_spend": {"$sum": "$spend"},
                        "total_revenue": {"$sum": "$revenue"},
                        "total_clicks": {"$sum": "$clicks"},
                        "total_impressions": {"$sum": "$impressions"},
                        "total_purchases": {"$sum": "$purchases"}
                    }
                }
            ]
            
            result = await collection.aggregate(pipeline).to_list(length=1)
            
            if not result:
                return {
                    "spend": 0,
                    "revenue": 0,
                    "clicks": 0,
                    "impressions": 0,
                    "purchases": 0,
                    "roas": 0,
                    "ctr": 0,
                    "cpc": 0,
                    "cpm": 0
                }
            
            data = result[0]
            spend = data.get("total_spend", 0)
            revenue = data.get("total_revenue", 0)
            clicks = data.get("total_clicks", 0)
            impressions = data.get("total_impressions", 0)
            purchases = data.get("total_purchases", 0)
            
            # Calculate derived metrics
            roas = revenue / spend if spend > 0 else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = spend / clicks if clicks > 0 else 0
            cpm = (spend / impressions * 1000) if impressions > 0 else 0
            
            return {
                "spend": spend,
                "revenue": revenue,
                "clicks": clicks,
                "impressions": impressions,
                "purchases": purchases,
                "roas": roas,
                "ctr": ctr,
                "cpc": cpc,
                "cpm": cpm
            }
            
        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {str(e)}")
            return {}
    
    async def fetch_metrics_from_facebook(
        self, 
        user_id: str, 
        start_date: str, 
        end_date: str,
        time_increment: int = 1,
        credentials: Optional[Dict[str, str]] = None,
        user_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch metrics from Facebook API for a specific date range.
        
        Args:
            user_id: The user ID
            start_date: Start date (string in format YYYY-MM-DD)
            end_date: End date (string in format YYYY-MM-DD)
            time_increment: Time increment for the data (1 = daily)
            credentials: Facebook credentials (if not provided, will fetch from user_data)
            user_data: User data (if not provided, will fetch from database)
        """
        try:
            # Get credentials if not provided
            if credentials is None:
                if user_data is None:
                    user_data = await self.find_user_by_id(user_id)
                
                if not user_data:
                    logger.warning(f"User not found: {user_id}")
                    return []
                
                credentials = self.extract_facebook_credentials(user_data)
            
            # Validate credentials
            if not self.has_valid_facebook_credentials(credentials):
                logger.warning(f"No valid Facebook credentials found for user {user_id}")
                return []
            
            # Create Facebook service
            fb_service = FacebookAdService(
                access_token=credentials["access_token"],
                account_id=credentials["account_id"]
            )
            
            # Fetch metrics for the date range
            metrics = await fb_service.collect_ad_metrics_for_range(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                time_increment=time_increment
            )
            
            logger.info(f"Fetched {len(metrics)} metrics from Facebook for user {user_id}")
            
            # Store the metrics
            stored_count = 0
            for metric in metrics:
                try:
                    await self.store_ad_metrics(metric)
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Error storing metric: {str(e)}")
                    continue
            
            logger.info(f"Stored {stored_count} metrics for user {user_id}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error fetching metrics from Facebook: {str(e)}")
            return []
    
    async def ensure_data_completeness(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        force_refresh: bool = False,
        user_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ensure data completeness for the specified date range.
        Checks if data is complete and fetches missing data from Facebook if needed.
        
        Args:
            user_id: The user ID
            start_date: Start date (string in format YYYY-MM-DD or datetime object)
            end_date: End date (string in format YYYY-MM-DD or datetime object)
            force_refresh: Whether to force refresh data even if it exists
            user_data: User data (if not provided, will fetch from database)
            
        Returns:
            Dictionary with status information
        """
        try:
            # Convert string dates to datetime if needed
            start_date_obj = start_date if isinstance(start_date, datetime) else datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = end_date if isinstance(end_date, datetime) else datetime.strptime(end_date, "%Y-%m-%d")
            
            # Initialize response
            result = {
                "metrics_fetched": False,
                "has_complete_data": False,
                "force_refresh_attempted": force_refresh,
                "missing_dates": [],
                "metrics_count": 0
            }
            
            # Get user data if not provided
            if user_data is None:
                user_data = await self.find_user_by_id(user_id)
            
            if not user_data:
                logger.warning(f"User not found: {user_id}")
                result["error"] = "User not found"
                return result
            
            # Check if we need to refresh the data
            need_to_fetch = force_refresh
            
            # If not forcing refresh, check if we have complete data
            if not need_to_fetch:
                has_complete_data = await self.has_complete_data_for_range(user_id, start_date_obj, end_date_obj)
                result["has_complete_data"] = has_complete_data
                need_to_fetch = not has_complete_data
            
            # Get a list of missing dates
            if need_to_fetch:
                missing_dates = await self._get_missing_dates(user_id, start_date_obj, end_date_obj)
                result["missing_dates"] = [date.strftime("%Y-%m-%d") for date in missing_dates]
                
                # Only fetch if we actually have missing dates
                need_to_fetch = len(missing_dates) > 0
            
            # Get Facebook credentials if we need to fetch
            if need_to_fetch:
                logger.info(f"Need to fetch data for user {user_id} for date range {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}")
                
                credentials = self.extract_facebook_credentials(user_data)
                
                if self.has_valid_facebook_credentials(credentials):
                    logger.info(f"Found Facebook credentials for user {user_id}")
                    
                    # Fetch missing data
                    fetched_metrics = await self.fetch_metrics_from_facebook(
                        user_id=user_id,
                        start_date=start_date_obj.strftime("%Y-%m-%d"),
                        end_date=end_date_obj.strftime("%Y-%m-%d"),
                        credentials=credentials,
                        user_data=user_data
                    )
                    
                    result["metrics_fetched"] = len(fetched_metrics) > 0
                    result["metrics_count"] = len(fetched_metrics)
                    
                    # Re-check completeness after fetching
                    result["has_complete_data"] = await self.has_complete_data_for_range(user_id, start_date_obj, end_date_obj)
                else:
                    logger.info(f"No Facebook credentials found for user {user_id} - will use existing data only")
                    result["has_complete_data"] = await self.has_any_data_for_range(user_id, start_date_obj, end_date_obj)
                    result["no_credentials"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error ensuring data completeness: {str(e)}")
            return {
                "metrics_fetched": False,
                "has_complete_data": False,
                "error": str(e)
            }
    
    async def _get_missing_dates(self, user_id: str, start_date: datetime, end_date: datetime) -> List[datetime]:
        """
        Get a list of dates in the range that don't have data.
        
        Args:
            user_id: The user ID
            start_date: Start date as datetime
            end_date: End date as datetime
            
        Returns:
            List of datetime objects representing dates without data
        """
        try:
            # Get all dates in the range
            all_dates = []
            current_date = start_date
            while current_date <= end_date:
                all_dates.append(current_date)
                current_date += timedelta(days=1)
            
            # Get dates that have data
            collection = await get_metrics_collection()
            dates_with_data = set()
            
            # Aggregate to get unique dates with data
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "collected_at": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$collected_at"
                            }
                        }
                    }
                }
            ]
            
            result = await collection.aggregate(pipeline).to_list(length=None)
            
            # Convert results to a set of date strings
            for doc in result:
                date_str = doc["_id"]
                dates_with_data.add(date_str)
            
            # Find missing dates
            missing_dates = []
            for date in all_dates:
                date_str = date.strftime("%Y-%m-%d")
                if date_str not in dates_with_data:
                    missing_dates.append(date)
            
            return missing_dates
            
        except Exception as e:
            logger.error(f"Error getting missing dates: {str(e)}")
            # Return all dates in range as missing
            all_dates = []
            current_date = start_date
            while current_date <= end_date:
                all_dates.append(current_date)
                current_date += timedelta(days=1)
            return all_dates 

    async def has_any_data_for_range(self, user_id: str, start_date: datetime, end_date: datetime) -> bool:
        """
        Check if there is any data available for the specified date range.
        Less strict than has_complete_data_for_range - only checks if we have at least one data point.
        
        Args:
            user_id: The user ID
            start_date: Start date as datetime
            end_date: End date as datetime
            
        Returns:
            True if there is at least one data point in the range, False otherwise
        """
        try:
            # Get metrics collection
            collection = await get_metrics_collection()
            
            # Check if there's at least one data point
            count = await collection.count_documents({
                "user_id": user_id,
                "collected_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            })
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking if any data exists for range: {str(e)}")
            return False
    
    async def collect_and_store_user_ad_metrics(
        self, 
        user_id: str, 
        access_token: str, 
        account_id: str
    ) -> List[str]:
        """
        Collect ad metrics from Facebook and store them in the database.
        This method is called by the scheduler service.
        
        Args:
            user_id: The user ID
            access_token: Facebook access token
            account_id: Facebook ad account ID
            
        Returns:
            List of stored metric IDs
        """
        try:
            logger.info(f"Starting metrics collection for user {user_id}")
            
            # Create Facebook service instance
            fb_service = FacebookAdService(
                access_token=access_token,
                account_id=account_id
            )
            
            # Collect metrics from Facebook
            metrics_data = await fb_service.collect_ad_metrics(user_id)
            
            if not metrics_data:
                logger.info(f"No metrics data collected for user {user_id}")
                return []
            
            logger.info(f"Collected {len(metrics_data)} metrics for user {user_id}")
            
            # Store metrics in database
            stored_ids = []
            for metric_data in metrics_data:
                try:
                    # Convert the metric data to the format expected by store_ad_metrics
                    formatted_metric = self._format_metric_for_storage(metric_data)
                    
                    # Store the metric
                    metric_id = await self.store_ad_metrics(formatted_metric)
                    stored_ids.append(metric_id)
                    
                except Exception as e:
                    logger.error(f"Error storing individual metric: {str(e)}")
                    continue
            
            logger.info(f"Successfully stored {len(stored_ids)} metrics for user {user_id}")
            return stored_ids
            
        except Exception as e:
            logger.error(f"Error collecting and storing metrics for user {user_id}: {str(e)}")
            raise
    
    def _format_metric_for_storage(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format metric data from Facebook service for storage in AdMetrics model.
        
        Args:
            metric_data: Raw metric data from Facebook service
            
        Returns:
            Formatted metric data for AdMetrics model
        """
        additional_metrics = metric_data.get("additional_metrics", {})
        
        # Extract main metrics
        formatted_metric = {
            "user_id": metric_data.get("user_id"),
            "ad_id": metric_data.get("ad_id"),
            "ad_account_id": metric_data.get("ad_account_id"),
            "campaign_id": metric_data.get("campaign_id"),
            "campaign_name": metric_data.get("campaign_name"),
            "adset_id": metric_data.get("adset_id"),
            "adset_name": metric_data.get("adset_name"),
            "ad_name": metric_data.get("ad_name"),
            "video_id": metric_data.get("video_id"),
            
            # Main metrics
            "impressions": additional_metrics.get("impressions", 0),
            "clicks": additional_metrics.get("clicks", 0),
            "spend": additional_metrics.get("spend", 0.0),
            "purchases": metric_data.get("purchases", 0),
            "revenue": additional_metrics.get("purchases_value", 0.0),
            "reach": additional_metrics.get("reach", 0),
            
            # Calculated metrics
            "ctr": additional_metrics.get("ctr", 0.0),
            "cpc": additional_metrics.get("cpc", 0.0),
            "cpm": additional_metrics.get("cpm", 0.0),
            "roas": additional_metrics.get("roas", 0.0),
            
            # Video metrics
            "video_p25_watched": additional_metrics.get("video_p25_watched", 0),
            "video_p50_watched": additional_metrics.get("video_p50_watched", 0),
            "video_p75_watched": additional_metrics.get("video_p75_watched", 0),
            "video_p95_watched": additional_metrics.get("video_p95_watched", 0),
            "video_p100_watched": additional_metrics.get("video_p100_watched", 0),
            
            # Timestamp
            "collected_at": metric_data.get("collected_at", datetime.utcnow())
        }
        
        return formatted_metric
    
    async def get_daily_metrics(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get daily aggregated metrics for a date range.
        
        Args:
            user_id: The user ID
            start_date: Start date as datetime
            end_date: End date as datetime
            
        Returns:
            List of daily metrics
        """
        try:
            collection = await get_metrics_collection()
            
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "collected_at": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$collected_at"
                            }
                        },
                        "spend": {"$sum": "$spend"},
                        "revenue": {"$sum": "$revenue"},
                        "clicks": {"$sum": "$clicks"},
                        "impressions": {"$sum": "$impressions"},
                        "purchases": {"$sum": "$purchases"}
                    }
                },
                {
                    "$project": {
                        "date": "$_id",
                        "spend": 1,
                        "revenue": 1,
                        "clicks": 1,
                        "impressions": 1,
                        "purchases": 1,
                        "ctr": {
                            "$cond": {
                                "if": {"$gt": ["$impressions", 0]},
                                "then": {"$multiply": [{"$divide": ["$clicks", "$impressions"]}, 100]},
                                "else": 0
                            }
                        },
                        "roas": {
                            "$cond": {
                                "if": {"$gt": ["$spend", 0]},
                                "then": {"$divide": ["$revenue", "$spend"]},
                                "else": 0
                            }
                        }
                    }
                },
                {
                    "$sort": {"date": 1}
                }
            ]
            
            result = await collection.aggregate(pipeline).to_list(length=None)
            
            # Convert _id to date and remove _id field
            for item in result:
                if "_id" in item:
                    del item["_id"]
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting daily metrics: {str(e)}")
            return [] 