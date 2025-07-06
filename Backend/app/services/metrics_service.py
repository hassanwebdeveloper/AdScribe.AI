import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.core.database import get_database, get_metrics_collection, get_users_collection
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
    
    async def has_complete_data_for_range(self, user_id: str, start_date, end_date) -> bool:
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
            logger.info(f"Checking data completeness for user {user_id} from {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')} ({expected_days} days)")
            
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
                logger.info(f"No data found for user {user_id} from {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}, expected {expected_days} days")
                return False
                
            days_with_data = result[0].get("total_days", 0)
            dates_found = result[0].get("dates", [])
            logger.info(f"Found data for {days_with_data} days out of {expected_days} expected days for user {user_id}")
            logger.info(f"Dates with data: {dates_found}")
            
            # Check each day in the date range
            current_date = start_date_obj
            missing_dates = []
            while current_date <= end_date_obj:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in dates_found:
                    missing_dates.append(date_str)
                current_date += timedelta(days=1)
            
            if missing_dates:
                logger.info(f"Missing data for dates: {missing_dates}")
            
            # Check if we have data for each day
            is_complete = days_with_data >= expected_days
            logger.info(f"Data completeness for user {user_id}: {is_complete}")
            return is_complete
            
        except Exception as e:
            logger.error(f"Error checking for complete data: {str(e)}")
            return False
    
    async def get_aggregated_metrics(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Calculate aggregated metrics for the specified date range.
        Similar to calculate_aggregated_kpis but with a cleaner interface.
        Returns a dict with all the KPI metrics.
        """
        try:
            # Format dates for string conversion if needed
            start_date_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, datetime) else start_date
            end_date_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime) else end_date
            
            # Delegate to existing method
            return await self.calculate_aggregated_kpis(user_id, start_date_str, end_date_str)
        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {str(e)}")
            # Return empty metrics
            return {
                "roas": 0,
                "ctr": 0,
                "cpc": 0,
                "cpm": 0,
                "conversions": 0,
                "spend": 0,
                "revenue": 0
            }
    
    async def fetch_metrics_from_facebook(
        self, 
        user_id: str, 
        start_date: str, 
        end_date: str,
        time_increment: int = 1,
        credentials: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch metrics directly from Facebook API for the specified date range.
        Uses a single account-level API call with time_increment to get daily metrics efficiently.
        
        Args:
            user_id: The user ID
            start_date: Start date (string or datetime)
            end_date: End date (string or datetime)
            time_increment: Time increment for the API call (1 for daily metrics)
            credentials: Optional Facebook credentials dict with access_token and account_id.
                         If not provided, will attempt to look up from the database.
        """
        try:
            # Convert string dates to properly formatted strings if they're datetime objects
            start_date_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, datetime) else start_date
            end_date_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime) else end_date
            
            # Log the date parameters for debugging
            logger.info(f"fetch_metrics_from_facebook called with start_date={start_date_str}, end_date={end_date_str}, type(start_date)={type(start_date)}, type(end_date)={type(end_date)}")
            
            access_token = None
            account_id = None
            
            # Use provided credentials if available
            if credentials and isinstance(credentials, dict):
                access_token = credentials.get("access_token")
                account_id = credentials.get("account_id")
                logger.info(f"Using provided credentials for user {user_id}")
            
            # If credentials not provided or incomplete, try to get from database
            if not access_token or not account_id:
                logger.info(f"Credentials not provided or incomplete, looking up from database for user {user_id}")
                # Get user's Facebook credentials - handle ObjectId conversion
                users_collection = await get_users_collection()
                user = None
                
                # Try with ObjectId first
                try:
                    user = await users_collection.find_one({"_id": ObjectId(user_id)})
                except Exception:
                    # If conversion fails, try with string ID
                    user = await users_collection.find_one({"_id": user_id})
                    
                # If still not found, try with different ID field formats
                if not user:
                    logger.warning(f"User not found with ID {user_id}, trying alternate ID formats")
                    # Try to find by string ID in case it's stored that way
                    user = await users_collection.find_one({"id": user_id})
                
                if not user:
                    logger.error(f"User {user_id} not found after multiple attempts")
                    # Return empty data but don't fail to avoid breaking the dashboard
                    return []
                    
                # Log successful user lookup
                logger.info(f"Found user {user_id} in database")
                    
                # Extract credentials - check both formats (direct and nested)
                db_credentials = {}
                if "facebook_credentials" in user and isinstance(user["facebook_credentials"], dict):
                    db_credentials = user.get("facebook_credentials", {})
                
                access_token = access_token or db_credentials.get("access_token") or user.get("facebook_access_token")
                account_id = account_id or db_credentials.get("ad_account_id") or db_credentials.get("account_id") or user.get("facebook_account_id")
                
                # Legacy format check
                if not access_token or not account_id:
                    access_token = user.get("facebook_access_token")
                    account_id = user.get("facebook_account_id")
                    
                    if access_token and account_id:
                        logger.info(f"Using fb_graph_api_key and fb_ad_account_id fields for user {user_id}")
                        access_token = access_token
                        account_id = account_id
                
                # Check for fb_graph_api_key and fb_ad_account_id fields
                if not access_token or not account_id:
                    graph_api_key = user.get("fb_graph_api_key")
                    ad_account_id = user.get("fb_ad_account_id")
                    
                    if graph_api_key and ad_account_id:
                        logger.info(f"Using fb_graph_api_key and fb_ad_account_id fields for user {user_id}")
                        access_token = graph_api_key
                        account_id = ad_account_id
            
            if not access_token or not account_id:
                logger.warning(f"User {user_id} has no valid Facebook credentials")
                return []
                
            # Validate the credentials format
            if not isinstance(access_token, str) or not isinstance(account_id, str):
                logger.error(f"Invalid credential format for user {user_id}: access_token={type(access_token).__name__}, account_id={type(account_id).__name__}")
                return []
            
            # Log info about the credentials
            logger.info(f"Using Facebook credentials for user {user_id}, account_id: {account_id}")
            
            # Initialize Facebook service
            facebook_service = FacebookAdService(
                access_token=access_token,
                account_id=account_id
            )
            
            # Fetch metrics using account-level insights with time_increment
            logger.info(f"Fetching Facebook metrics for date range {start_date_str} to {end_date_str} with time_increment={time_increment}")
            
            start_time = datetime.now()
            metrics = await facebook_service.collect_ad_metrics_for_range(
                user_id=user_id,
                start_date=start_date_str,  # Ensure we pass string dates to avoid type issues
                end_date=end_date_str,      # Ensure we pass string dates to avoid type issues
                time_increment=time_increment
            )
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            # Return empty list instead of failing if no metrics were found
            if not metrics:
                logger.warning(f"No metrics fetched from Facebook for {user_id} from {start_date_str} to {end_date_str}")
                return []
                
            # Ensure metrics is a list to avoid type errors
            if not isinstance(metrics, list):
                logger.warning(f"Expected list of metrics but got {type(metrics).__name__}")
                if isinstance(metrics, dict):
                    # Convert single dict to list with one item
                    metrics = [metrics]
                else:
                    # Return empty list for any other non-list type
                    return []
            
            logger.info(f"Fetched {len(metrics)} metrics in {elapsed_time:.2f} seconds")
            
            # Store metrics in MongoDB
            if metrics:
                collection = await get_metrics_collection()
                stored_count = 0
                
                # Use collected_at from each metric (should be the actual date of the metrics)
                for metric in metrics:
                    try:
                        # Handle duplicates by removing any existing metrics for the same ad_id and date
                        metric_date = metric.get("collected_at")
                        if not isinstance(metric_date, datetime):
                            # Try to convert string date to datetime
                            try:
                                metric_date = datetime.strptime(metric_date, "%Y-%m-%d")
                                metric["collected_at"] = metric_date
                            except (ValueError, TypeError):
                                # If conversion fails, use current date
                                metric_date = datetime.now()
                                metric["collected_at"] = metric_date
                                
                        metric_date_str = metric_date.strftime("%Y-%m-%d")
                        
                        # Log the date we're processing
                        logger.debug(f"Processing metric for date {metric_date_str}, ad_id {metric.get('ad_id')}")
                        
                        # Delete any existing metrics for this ad on this date
                        delete_result = await collection.delete_many({
                            "user_id": user_id,
                            "ad_id": metric.get("ad_id"),
                            "collected_at": {
                                "$gte": datetime.strptime(metric_date_str, "%Y-%m-%d"),
                                "$lt": datetime.strptime(metric_date_str, "%Y-%m-%d") + timedelta(days=1)
                            }
                        })
                        
                        if delete_result.deleted_count > 0:
                            logger.debug(f"Deleted {delete_result.deleted_count} existing metrics for ad {metric.get('ad_id')} on {metric_date_str}")
                        
                        # Verify the date before insertion
                        logger.debug(f"Storing metric with collected_at={metric_date.isoformat()} ({type(metric_date).__name__})")
                        
                        # Insert the new metric
                        await collection.insert_one(metric)
                        stored_count += 1
                    except Exception as e:
                        logger.error(f"Error storing metric: {str(e)}")
                
                logger.info(f"Stored {stored_count} out of {len(metrics)} metrics from Facebook for user {user_id}")
            
            # Get the updated metrics from the database to return
            return await self.get_metrics_by_date_range(user_id, start_date_str, end_date_str)
        
        except Exception as e:
            logger.error(f"Error fetching metrics from Facebook: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def calculate_aggregated_kpis(self, user_id: str, start_date: str, end_date: str) -> Dict[str, float]:
        """
        Calculate aggregated KPIs for the specified date range.
        Only includes metrics for ads that are present in the ad_analyses collection.
        Sums raw metrics across all ads and all days, then computes derived metrics manually.
        """
        # Get metrics for the date range
        all_metrics = await self.get_metrics_by_date_range(user_id, start_date, end_date)
        
        # Filter metrics to only include analyzed ads
        metrics = await self._filter_metrics_by_analyses(all_metrics, user_id)
        
        if not metrics:
            return {
                "roas": 0,
                "ctr": 0,
                "cpc": 0,
                "cpm": 0,
                "conversions": 0,
                "spend": 0,
                "revenue": 0,
                "clicks": 0,
                "impressions": 0
            }

        # Initialize total sums
        total_spend = 0
        total_clicks = 0
        total_impressions = 0
        total_purchases = 0
        total_revenue = 0

        metrics_by_date_and_ad = {}

        for metric in metrics:
            collected_at = metric.get("collected_at")
            date_str = collected_at.strftime("%Y-%m-%d") if isinstance(collected_at, datetime) else str(collected_at).split("T")[0]
            ad_id = metric.get("ad_id", "unknown")

            key = f"{date_str}_{ad_id}"

            additional = metric.get("additional_metrics", {}) or {}
            current_spend = float(additional.get("spend", 0))
            current_clicks = int(additional.get("clicks", 0))
            current_impressions = int(additional.get("impressions", 0))
            current_purchases = int(metric.get("purchases", 0))
            current_revenue = float(additional.get("purchases_value", 0))

            if key not in metrics_by_date_and_ad:
                metrics_by_date_and_ad[key] = {
                    "spend": current_spend,
                    "clicks": current_clicks,
                    "impressions": current_impressions,
                    "purchases": current_purchases,
                    "revenue": current_revenue
                }
            else:
                metrics_by_date_and_ad[key]["spend"] = max(metrics_by_date_and_ad[key]["spend"], current_spend)
                metrics_by_date_and_ad[key]["clicks"] = max(metrics_by_date_and_ad[key]["clicks"], current_clicks)
                metrics_by_date_and_ad[key]["impressions"] = max(metrics_by_date_and_ad[key]["impressions"], current_impressions)
                metrics_by_date_and_ad[key]["purchases"] = max(metrics_by_date_and_ad[key]["purchases"], current_purchases)
                metrics_by_date_and_ad[key]["revenue"] = max(metrics_by_date_and_ad[key]["revenue"], current_revenue)

        # Aggregate totals
        for entry in metrics_by_date_and_ad.values():
            total_spend += entry["spend"]
            total_clicks += entry["clicks"]
            total_impressions += entry["impressions"]
            total_purchases += entry["purchases"]
            total_revenue += entry["revenue"]

        # Derived metrics
        ctr = (total_clicks / total_impressions) * 100 if total_impressions else 0
        roas = total_revenue / total_spend if total_spend else 0
        cpc = total_spend / total_clicks if total_clicks else 0
        cpm = (total_spend / total_impressions * 1000) if total_impressions else 0

        return {
            "roas": roas,
            "ctr": ctr,
            "cpc": cpc,
            "cpm": cpm,
            "conversions": total_purchases,
            "spend": total_spend,
            "revenue": total_revenue,
            "clicks": total_clicks,
            "impressions": total_impressions
        }
    
    async def get_daily_metrics(self, user_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get daily metrics for trend charts.
        Only includes metrics for ads that are present in the ad_analyses collection.
        Returns a list of daily metrics with date, spend, revenue, ctr, and roas.
        Ensures all dates in the range have entries, even if there's no data.
        """
        try:
            # Convert string dates to datetime objects
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if isinstance(start_date, str) else start_date
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if isinstance(end_date, str) else end_date
            
            # Include the full end day
            end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)

            # Get valid ad/campaign IDs from ad_analyses
            valid_ad_ids, valid_campaign_ids = await self._get_valid_ad_ids_from_analyses(user_id)
            
            # If no valid ads found, return empty data for all dates
            if not valid_ad_ids and not valid_campaign_ids:
                logger.info(f"No ads found in ad_analyses collection for user {user_id}, returning empty daily metrics")
                all_days = []
                current_date = start_date_obj
                while current_date <= end_date_obj:
                    date_str = current_date.strftime("%Y-%m-%d")
                    all_days.append({
                        "date": date_str,
                        "spend": 0,
                        "revenue": 0,
                        "clicks": 0,
                        "impressions": 0,
                        "purchases": 0,
                        "ctr": 0,
                        "roas": 0
                    })
                    current_date += timedelta(days=1)
                return all_days
            
            # Get metrics collection
            collection = await get_metrics_collection()
            
            # Log the date range being queried
            logger.info(f"Querying daily metrics from {start_date_obj} to {end_date_obj} for user {user_id}")
            
            # Create filter for valid ads - include metrics that match either ad_id or campaign_id
            ad_filter = {"$or": []}
            if valid_ad_ids:
                ad_filter["$or"].append({"ad_id": {"$in": list(valid_ad_ids)}})
            if valid_campaign_ids:
                ad_filter["$or"].append({"campaign_id": {"$in": list(valid_campaign_ids)}})
            
            # Aggregate metrics by day - using $sum for raw metrics
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "collected_at": {
                            "$gte": start_date_obj,
                            "$lte": end_date_obj
                        },
                        **ad_filter
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
                        "spend": {"$sum": {"$toDouble": {"$ifNull": [{"$getField": {"field": "spend", "input": "$additional_metrics"}}, 0]}}},
                        "clicks": {"$sum": {"$toInt": {"$ifNull": [{"$getField": {"field": "clicks", "input": "$additional_metrics"}}, 0]}}},
                        "impressions": {"$sum": {"$toInt": {"$ifNull": [{"$getField": {"field": "impressions", "input": "$additional_metrics"}}, 0]}}},
                        "purchases": {"$sum": {"$toInt": {"$ifNull": ["$purchases", 0]}}},
                        "revenue": {"$sum": {"$toDouble": {"$ifNull": [{"$getField": {"field": "purchases_value", "input": "$additional_metrics"}}, 0]}}}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "date": "$_id",
                        "spend": 1,
                        "revenue": 1,
                        "clicks": 1,
                        "impressions": 1,
                        "purchases": 1
                    }
                },
                {
                    "$sort": {"date": 1}
                }
            ]
            
            raw_metrics = await collection.aggregate(pipeline).to_list(length=None)
            
            logger.info(f"Found {len(raw_metrics)} days with data out of {(end_date_obj - start_date_obj).days + 1} days in range")
            
            # Generate final metrics with derived values
            all_days = []
            current_date = start_date_obj
            while current_date <= end_date_obj:
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Find data for this day
                raw = next((day for day in raw_metrics if day["date"] == date_str), None)
                
                if raw:
                    spend = raw["spend"]
                    revenue = raw["revenue"]
                    clicks = raw["clicks"]
                    impressions = raw["impressions"]
                    purchases = raw["purchases"]

                    # Manual derived metrics
                    ctr = (clicks / impressions) if impressions > 0 else 0
                    roas = (revenue / spend) if spend > 0 else 0
                    cpc = (spend / clicks) if clicks > 0 else 0
                    cpm = (spend / (impressions / 1000)) if impressions > 0 else 0

                    all_days.append({
                        "date": date_str,
                        "spend": spend,
                        "revenue": revenue,
                        "clicks": clicks,
                        "impressions": impressions,
                        "purchases": purchases,
                        "ctr": ctr,
                        "roas": roas,
                        "cpc": cpc,
                        "cpm": cpm
                    })
                else:
                    all_days.append({
                        "date": date_str,
                        "spend": 0,
                        "revenue": 0,
                        "clicks": 0,
                        "impressions": 0,
                        "purchases": 0,
                        "ctr": 0,
                        "roas": 0,
                        "cpc": 0,
                        "cpm": 0
                    })
                
                current_date += timedelta(days=1)
            
            if len(all_days) != (end_date_obj - start_date_obj).days + 1:
                logger.warning(f"Generated {len(all_days)} days but expected {(end_date_obj - start_date_obj).days + 1} days")
            
            return all_days
            
        except Exception as e:
            logger.error(f"Error getting daily metrics: {str(e)}")
            return []
    
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

    # Add a new method for ensuring data completeness
    async def ensure_data_completeness(
        self,
        user_id: str,
        start_date,
        end_date,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Ensure data completeness for the specified date range.
        Checks if data is complete and fetches missing data from Facebook if needed.
        
        Args:
            user_id: The user ID
            start_date: Start date (string in format YYYY-MM-DD or datetime object)
            end_date: End date (string in format YYYY-MM-DD or datetime object)
            force_refresh: Whether to force refresh data even if it exists
            
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
            fb_credentials = None
            if need_to_fetch:
                logger.info(f"Need to fetch data for user {user_id} for date range {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}")
                
                # Get user's Facebook credentials
                users_collection = await get_users_collection()
                
                try:
                    # Try with ObjectId first
                    user = await users_collection.find_one({"_id": ObjectId(user_id)})
                except Exception:
                    # If conversion fails, try with string ID
                    user = await users_collection.find_one({"_id": user_id})
                
                if not user:
                    # Last attempt - try by string ID field
                    user = await users_collection.find_one({"id": user_id})
                
                if not user:
                    logger.warning(f"User not found: {user_id}")
                    # Set result to indicate user not found but don't raise exception
                    result["error"] = "User not found"
                    return result
                
                # Check for credentials in various formats
                if "facebook_credentials" in user and isinstance(user["facebook_credentials"], dict):
                    fb_credentials = user["facebook_credentials"]
                    
                    # Verify credentials have required fields
                    if not fb_credentials.get("access_token") or not fb_credentials.get("account_id"):
                        logger.warning(f"Incomplete Facebook credentials for user {user_id}")
                        fb_credentials = None
                
                # Legacy format check
                if not fb_credentials:
                    access_token = user.get("facebook_access_token")
                    account_id = user.get("facebook_account_id")
                    
                    if access_token and account_id:
                        fb_credentials = {
                            "access_token": access_token,
                            "account_id": account_id
                        }
                
                # Check for fb_graph_api_key and fb_ad_account_id fields
                if not fb_credentials:
                    graph_api_key = user.get("fb_graph_api_key")
                    ad_account_id = user.get("fb_ad_account_id")
                    
                    if graph_api_key and ad_account_id:
                        logger.info(f"Using fb_graph_api_key and fb_ad_account_id fields for user {user_id}")
                        fb_credentials = {
                            "access_token": graph_api_key,
                            "account_id": ad_account_id
                        }
                
                if fb_credentials:
                    logger.info(f"Found Facebook credentials for user {user_id}")
                else:
                    logger.info(f"No Facebook credentials found for user {user_id} - will use existing data only")
                    # Set has_complete_data based on existing data
                    result["has_complete_data"] = await self.has_any_data_for_range(user_id, start_date_obj, end_date_obj)
                    result["no_credentials"] = True
                    return result
            
            # Fetch data if needed and we have credentials
            if need_to_fetch and fb_credentials:
                logger.info(f"Attempting to fetch metrics from Facebook for user {user_id}")
                try:
                    # Convert datetime objects to string format for fetch_metrics_from_facebook
                    start_date_str = start_date_obj.strftime("%Y-%m-%d")
                    end_date_str = end_date_obj.strftime("%Y-%m-%d")
                    
                    # Fetch metrics for the date range
                    num_metrics = await self.fetch_metrics_from_facebook(
                        user_id=user_id,
                        start_date=start_date_str,
                        end_date=end_date_str,
                        credentials=fb_credentials
                    )
                    
                    # Check if num_metrics is a list and get its length, otherwise treat as int
                    if isinstance(num_metrics, list):
                        result["metrics_fetched"] = len(num_metrics) > 0
                        result["metrics_count"] = len(num_metrics)
                        logger.info(f"Fetched {len(num_metrics)} metrics from Facebook for date range {start_date_str} to {end_date_str}")
                    else:
                        result["metrics_fetched"] = num_metrics > 0
                        result["metrics_count"] = num_metrics
                        logger.info(f"Fetched {num_metrics} metrics from Facebook for date range {start_date_str} to {end_date_str}")
                    
                    # Check if we now have complete data
                    result["has_complete_data"] = await self.has_complete_data_for_range(user_id, start_date_obj, end_date_obj)
                    
                except Exception as e:
                    logger.error(f"Error fetching metrics from Facebook: {str(e)}")
                    # Continue with available data
            
            return result
            
        except Exception as e:
            logger.error(f"Error ensuring data completeness: {str(e)}")
            return {
                "metrics_fetched": False,
                "has_complete_data": False,
                "force_refresh_attempted": force_refresh,
                "missing_dates": [],
                "metrics_count": 0,
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

    async def has_any_data_for_range(self, user_id: str, start_date, end_date) -> bool:
        """
        Check if there is any data available for the specified date range.
        Less strict than has_complete_data_for_range - only checks if we have at least one data point.
        
        Args:
            user_id: The user ID
            start_date: Start date (string in format YYYY-MM-DD or datetime object)
            end_date: End date (string in format YYYY-MM-DD or datetime object)
            
        Returns:
            True if there is at least one data point in the range, False otherwise
        """
        try:
            # Convert string dates to datetime if needed
            start_date_obj = start_date if isinstance(start_date, datetime) else datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = end_date if isinstance(end_date, datetime) else datetime.strptime(end_date, "%Y-%m-%d")
            
            # Get metrics collection
            collection = await get_metrics_collection()
            
            # Check if there's at least one data point
            count = await collection.count_documents({
                "user_id": user_id,
                "collected_at": {
                    "$gte": start_date_obj,
                    "$lte": end_date_obj
                }
            })
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking if any data exists for range: {str(e)}")
            return False 

    async def _get_valid_ad_ids_from_analyses(self, user_id: str) -> tuple[set, set]:
        """
        Helper method to get valid ad_ids and campaign_ids from ad_analyses collection.
        Returns a tuple of (valid_ad_ids, valid_campaign_ids).
        """
        try:
            db = get_database()
            ad_analyses = await db.ad_analyses.find({"user_id": str(user_id)}).to_list(length=1000)
            
            valid_ad_ids = set()
            valid_campaign_ids = set()
            
            for analysis in ad_analyses:
                # Add ad_id if present
                if "ad_id" in analysis and analysis["ad_id"]:
                    valid_ad_ids.add(analysis["ad_id"])
                
                # Add campaign_id if present
                if "campaign_id" in analysis and analysis["campaign_id"]:
                    valid_campaign_ids.add(analysis["campaign_id"])
            
            logger.info(f"Found {len(valid_ad_ids)} valid ad IDs and {len(valid_campaign_ids)} valid campaign IDs from ad_analyses for user {user_id}")
            return valid_ad_ids, valid_campaign_ids
            
        except Exception as e:
            logger.error(f"Error getting valid ad IDs from ad_analyses: {str(e)}")
            return set(), set()

    async def _filter_metrics_by_analyses(self, metrics: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """
        Helper method to filter metrics to only include ads that are present in ad_analyses collection.
        """
        valid_ad_ids, valid_campaign_ids = await self._get_valid_ad_ids_from_analyses(user_id)
        
        # If no valid ads found, return empty list
        if not valid_ad_ids and not valid_campaign_ids:
            logger.info(f"No ads found in ad_analyses collection for user {user_id}, filtering all metrics")
            return []
        
        # Filter metrics
        filtered_metrics = []
        for metric in metrics:
            ad_id = metric.get("ad_id")
            campaign_id = metric.get("campaign_id")
            
            # Include metric if either ad_id or campaign_id is in the valid sets
            if (ad_id and ad_id in valid_ad_ids) or (campaign_id and campaign_id in valid_campaign_ids):
                filtered_metrics.append(metric)
        
        logger.info(f"Filtered metrics from {len(metrics)} to {len(filtered_metrics)} based on ad_analyses collection for user {user_id}")
        return filtered_metrics 