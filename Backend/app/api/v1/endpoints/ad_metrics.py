from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.database import get_database, get_metrics_collection, get_users_collection
from app.models.ad_metrics import AdMetrics, AdMetricsResponse
from app.services.metrics_service import MetricsService
from app.services.scheduler_service import SchedulerService
from app.services.user_service import UserService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from bson import ObjectId
import logging
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)
metrics_service = MetricsService()

# Define dashboard response model
class PeriodMetrics(BaseModel):
    start_date: str
    end_date: str
    roas: float = 0
    ctr: float = 0
    cpc: float = 0
    cpm: float = 0
    conversions: int = 0
    spend: float = 0
    revenue: float = 0
    clicks: int = 0
    impressions: int = 0

class DailyMetric(BaseModel):
    date: str
    spend: float = 0
    revenue: float = 0
    clicks: int = 0
    impressions: int = 0
    purchases: int = 0
    ctr: float = 0
    roas: float = 0

class RefreshStatus(BaseModel):
    metrics_fetched: bool = False
    has_complete_data: bool = False
    force_refresh_attempted: bool = False

class AdDailyMetric(BaseModel):
    date: str
    ad_id: str
    ad_name: str
    ad_title: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    adset_name: Optional[str] = None
    spend: float = 0
    revenue: float = 0
    clicks: int = 0
    impressions: int = 0
    purchases: int = 0
    ctr: float = 0
    cpc: float = 0
    cpm: float = 0
    roas: float = 0

class DashboardResponse(BaseModel):
    current_period: PeriodMetrics
    previous_period: PeriodMetrics
    daily_metrics: List[DailyMetric] = Field(default_factory=list)
    refresh_status: RefreshStatus = Field(default_factory=RefreshStatus)
    ad_metrics: List[AdDailyMetric] = Field(default_factory=list)
    unique_ads: List[Dict[str, Any]] = Field(default_factory=list)

class AdMetricsByAdResponse(BaseModel):
    ad_metrics: List[AdDailyMetric] = Field(default_factory=list)
    unique_ads: List[Dict[str, Any]] = Field(default_factory=list)
    date_range: Dict[str, str] = Field(default_factory=dict)

# Use lazy loading for scheduler service
def get_scheduler_service():
    return SchedulerService()

@router.get("/", response_model=List[AdMetricsResponse])
async def get_user_metrics(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user)
):
    """
    Get metrics for the current user.
    """
    metrics = await metrics_service.get_user_metrics(current_user.id, skip, limit)
    return metrics

@router.get("/dashboard/", response_model=DashboardResponse)
async def get_dashboard_metrics(
    start_date: str = "2023-09-01",
    end_date: str = "2023-09-30",
    force_refresh: bool = False,
    use_only_analyzed_ads: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    Get metrics for the dashboard.
    """
    logger.info(f"Dashboard metrics requested by user {current_user.id} for date range {start_date} to {end_date}")
    
    try:
        # Parse dates
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Calculate previous period
        date_diff = (end_date_obj - start_date_obj).days
        prev_end_date_obj = start_date_obj - timedelta(days=1)
        prev_start_date_obj = prev_end_date_obj - timedelta(days=date_diff)
        
        prev_start_date = prev_start_date_obj.strftime("%Y-%m-%d")
        prev_end_date = prev_end_date_obj.strftime("%Y-%m-%d")
        
        logger.info(f"Previous period: {prev_start_date} to {prev_end_date}")
        
        # Check for Facebook credentials
        fb_credentials = None
        users_collection = await get_users_collection()
        user = await users_collection.find_one({"_id": ObjectId(current_user.id)})
        
        if user and "facebook_credentials" in user:
            fb_credentials = user.get("facebook_credentials", {})
        
        # Check if we have metrics for current and previous periods
        metrics_fetched = False
        
        # Use the new method to ensure data completeness for both time periods
        current_period_status = await metrics_service.ensure_data_completeness(
            user_id=current_user.id,
            start_date=start_date_obj,
            end_date=end_date_obj,
            force_refresh=force_refresh
        )
        
        previous_period_status = await metrics_service.ensure_data_completeness(
            user_id=current_user.id,
            start_date=prev_start_date_obj,
            end_date=prev_end_date_obj,
            force_refresh=force_refresh
        )
        
        # Check if metrics were fetched in either period
        metrics_fetched = current_period_status["metrics_fetched"] or previous_period_status["metrics_fetched"]

        # After potentially fetching from Facebook, calculate aggregated KPIs
        # Current period
        current_agg_metrics = await metrics_service.get_aggregated_metrics(
            user_id=current_user.id,
            start_date=start_date_obj,
            end_date=end_date_obj,
            use_only_analyzed_ads=use_only_analyzed_ads
        )
        
        # Previous period for comparison
        prev_agg_metrics = await metrics_service.get_aggregated_metrics(
            user_id=current_user.id,
            start_date=prev_start_date_obj,
            end_date=prev_end_date_obj,
            use_only_analyzed_ads=use_only_analyzed_ads
        )
        
        # Get daily metrics for charts
        daily_metrics = await metrics_service.get_daily_metrics(
            user_id=current_user.id,
            start_date=start_date_obj,
            end_date=end_date_obj,
            use_only_analyzed_ads=use_only_analyzed_ads
        )
        
        # Get ad-level metrics for the period
        ad_metrics_response = await get_metrics_by_ad(
            start_date=start_date,
            end_date=end_date,
            force_refresh=False,  # We already refreshed if needed
            use_only_analyzed_ads=use_only_analyzed_ads,
            current_user=current_user
        )
        
        # Add ad_id and ad_name to daily metrics if available
        enhanced_daily_metrics = daily_metrics
        if ad_metrics_response and ad_metrics_response.ad_metrics:
            # Create a lookup from date to ad details
            ad_lookup = {}
            for ad_metric in ad_metrics_response.ad_metrics:
                if ad_metric.date not in ad_lookup:
                    ad_lookup[ad_metric.date] = []
                ad_lookup[ad_metric.date].append({
                    "ad_id": ad_metric.ad_id,
                    "ad_name": ad_metric.ad_name
                })
            
            # Enhance daily metrics with ad information
            for daily_metric in enhanced_daily_metrics:
                date_str = daily_metric["date"]
                if date_str in ad_lookup:
                    # Use the first ad for this date as representative
                    if ad_lookup[date_str]:
                        daily_metric["ad_id"] = ad_lookup[date_str][0]["ad_id"]
                        daily_metric["ad_name"] = ad_lookup[date_str][0]["ad_name"]

        # Return the dashboard data
        response = {
            "current_period": {"start_date": start_date, "end_date": end_date, **current_agg_metrics},
            "previous_period": {"start_date": prev_start_date, "end_date": prev_end_date, **prev_agg_metrics},
            "daily_metrics": enhanced_daily_metrics,
            "refresh_status": {
                "metrics_fetched": metrics_fetched,
                "has_complete_data": await metrics_service.has_complete_data_for_range(
                    current_user.id, start_date_obj, end_date_obj
                ),
                "force_refresh_attempted": force_refresh,
            },
            "ad_metrics": ad_metrics_response.ad_metrics if ad_metrics_response else [],
            "unique_ads": ad_metrics_response.unique_ads if ad_metrics_response else []
        }
        
        logger.info(f"Dashboard response refresh_status: {response['refresh_status']}")
        return response

    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ad_id}", response_model=List[AdMetricsResponse])
async def get_ad_metrics_history(
    ad_id: str, 
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user)
):
    """
    Get historical metrics for a specific ad.
    """
    metrics = await metrics_service.get_ad_metrics_history(ad_id, skip, limit)
    
    # Check if metrics belong to the current user
    if metrics and metrics[0]["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access these metrics"
        )
    
    return metrics

@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_metrics_collection(current_user: User = Depends(get_current_user)):
    """
    Manually trigger metrics collection for the current user.
    """
    if not current_user.facebook_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook credentials not configured"
        )
    
    # Get scheduler service instance and schedule metrics collection
    scheduler_service = get_scheduler_service()
    await scheduler_service.schedule_metrics_collection_for_user(current_user.id)
    
    return {"message": "Metrics collection scheduled"}

@router.get("/by-ad/", response_model=AdMetricsByAdResponse)
async def get_metrics_by_ad(
    start_date: str,
    end_date: str,
    force_refresh: bool = False,
    use_only_analyzed_ads: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    Get daily metrics broken down by ad for the specified date range.
    Returns metrics for each ad for each day in the range.
    """
    try:
        # Parse dates
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Calculate previous period
        date_diff = (end_date_obj - start_date_obj).days
        prev_end_date_obj = start_date_obj - timedelta(days=1)
        prev_start_date_obj = prev_end_date_obj - timedelta(days=date_diff)
        
        prev_start_date = prev_start_date_obj.strftime("%Y-%m-%d")
        prev_end_date = prev_end_date_obj.strftime("%Y-%m-%d")
        
        logger.info(f"Previous period: {prev_start_date} to {prev_end_date}")
        
        # Check if we have complete data for the requested period - pass datetime objects
        has_complete_data = await metrics_service.has_complete_data_for_range(
            current_user.id, start_date_obj, end_date_obj
        )
        logger.info(f"Has complete data for requested period: {has_complete_data}")

        # Get FB credentials for the user
        user_service = UserService()
        fb_credentials = await user_service.get_facebook_credentials(current_user.id)
        
        # Check if credentials are valid
        has_credentials = (
            bool(fb_credentials) and 
            'access_token' in fb_credentials and 
            'account_id' in fb_credentials
        )
        
        # Determine if we need to fetch data from Facebook (only if we have credentials)
        need_to_fetch = (force_refresh or not has_complete_data) and has_credentials
        
        # If we don't have complete data and have credentials, try to fetch from Facebook
        if need_to_fetch:
            logger.info(f"Attempting to fetch metrics from Facebook for user {current_user.id}")
            try:
                # Use time_increment=1 to get daily breakdown - pass string dates
                await metrics_service.fetch_metrics_from_facebook(
                    user_id=current_user.id,
                    start_date=start_date,
                    end_date=end_date,
                    credentials=fb_credentials
                )
            except Exception as e:
                logger.error(f"Error fetching metrics from Facebook: {str(e)}")
                # Continue with available data
        
        # Get raw metrics for the date range - pass string dates
        all_metrics = await metrics_service.get_metrics_by_date_range(current_user.id, start_date, end_date)
        
        # Initialize variables for filtering
        valid_ad_ids = set()
        valid_campaign_ids = set()
        ad_titles = {}
        
        # Apply filtering if use_only_analyzed_ads is True
        if use_only_analyzed_ads:
            # Fetch ad_analyses collection to get valid ads
            db = get_database()
            ad_analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).to_list(length=1000)
            
            # Create a set of valid ad/campaign IDs and a map of ad_id to ad_title
            for analysis in ad_analyses:
                # Add ad_id if present
                if "ad_id" in analysis and analysis["ad_id"]:
                    valid_ad_ids.add(analysis["ad_id"])
                    ad_titles[analysis["ad_id"]] = analysis.get("ad_title", "")
                
                # Add campaign_id if present
                if "campaign_id" in analysis and analysis["campaign_id"]:
                    valid_campaign_ids.add(analysis["campaign_id"])
                    ad_titles[analysis["campaign_id"]] = analysis.get("ad_title", "")
            
            logger.info(f"Found {len(valid_ad_ids)} valid ad IDs and {len(valid_campaign_ids)} valid campaign IDs from ad_analyses")
            
            # If no valid ads found in ad_analyses, return empty response
            if not valid_ad_ids and not valid_campaign_ids:
                logger.info("No ads found in ad_analyses collection, returning empty response")
                return AdMetricsByAdResponse(
                    ad_metrics=[],
                    unique_ads=[],
                    date_range={"start_date": start_date, "end_date": end_date}
                )
            
            # Filter metrics to only include ads that are present in ad_analyses collection
            metrics = []
            for metric in all_metrics:
                ad_id = metric.get("ad_id")
                campaign_id = metric.get("campaign_id")
                
                # Include metric if either ad_id or campaign_id is in the valid sets
                if (ad_id and ad_id in valid_ad_ids) or (campaign_id and campaign_id in valid_campaign_ids):
                    metrics.append(metric)
            
            logger.info(f"Filtered metrics from {len(all_metrics)} to {len(metrics)} based on ad_analyses collection")
        else:
            # Use all metrics without filtering
            metrics = all_metrics
            logger.info(f"Using all {len(metrics)} metrics without filtering")
        
        if not metrics:
            return AdMetricsByAdResponse(
                ad_metrics=[],
                unique_ads=[],
                date_range={"start_date": start_date, "end_date": end_date}
            )
        
        logger.info(f"Found {len(ad_titles)} ad titles from ad_analyses for user {current_user.id}")
        
        # Process metrics to get daily values by ad
        ad_metrics = []
        unique_ads = {}  # Keep track of unique ads

        # Group metrics by date and ad_id
        metrics_by_date_and_ad = {}
        
        for metric in metrics:
            collected_at = metric.get("collected_at")
            date_str = collected_at.strftime("%Y-%m-%d") if isinstance(collected_at, datetime) else str(collected_at).split("T")[0]
            ad_id = metric.get("ad_id", "unknown") or "unknown"  # Use "unknown" if ad_id is None
            ad_name = metric.get("ad_name", "Unknown Ad") or "Unknown Ad"  # Use "Unknown Ad" if ad_name is None
            
            # Track unique ads
            if ad_id not in unique_ads:
                # Get ad title from ad_analyses if available
                ad_title = None
                campaign_id = metric.get("campaign_id")
                if campaign_id and campaign_id in ad_titles:
                    ad_title = ad_titles[campaign_id]
                elif ad_id in ad_titles:
                    ad_title = ad_titles[ad_id]
                
                unique_ads[ad_id] = {
                    "ad_id": ad_id, 
                    "ad_name": ad_name,
                    "ad_title": ad_title or "",  # Empty string instead of None
                    "campaign_id": metric.get("campaign_id") or None,  # Ensure None instead of empty string
                    "campaign_name": metric.get("campaign_name") or None,  # Ensure None instead of empty string
                    "adset_id": metric.get("adset_id") or None,  # Ensure None instead of empty string
                    "adset_name": metric.get("adset_name") or None  # Ensure None instead of empty string
                }
            
            # Create key for grouping
            key = f"{date_str}_{ad_id}"
            
            additional = metric.get("additional_metrics", {}) or {}  # Handle None case
            current_spend = float(additional.get("spend", 0))
            current_clicks = int(additional.get("clicks", 0))
            current_impressions = int(additional.get("impressions", 0))
            current_purchases = int(metric.get("purchases", 0))
            current_revenue = float(additional.get("purchases_value", 0))
            
            # Calculate derived metrics
            current_ctr = float(additional.get("ctr", 0))
            current_cpc = float(additional.get("cpc", 0))
            current_cpm = float(additional.get("cpm", 0))
            current_roas = float(additional.get("roas", 0))
            
            # Get ad title from ad_analyses if available
            ad_title = None
            campaign_id = metric.get("campaign_id")
            if campaign_id and campaign_id in ad_titles:
                ad_title = ad_titles[campaign_id]
            elif ad_id in ad_titles:
                ad_title = ad_titles[ad_id]
            
            if key not in metrics_by_date_and_ad:
                metrics_by_date_and_ad[key] = {
                    "date": date_str,
                    "ad_id": ad_id,
                    "ad_name": ad_name,
                    "ad_title": ad_title or "",  # Empty string instead of None
                    "campaign_id": metric.get("campaign_id") or None,  # Ensure None instead of empty string
                    "campaign_name": metric.get("campaign_name") or None,  # Ensure None instead of empty string
                    "adset_id": metric.get("adset_id") or None,  # Ensure None instead of empty string
                    "adset_name": metric.get("adset_name") or None,  # Ensure None instead of empty string
                    "spend": current_spend,
                    "clicks": current_clicks,
                    "impressions": current_impressions,
                    "purchases": current_purchases,
                    "revenue": current_revenue,
                    "ctr": current_ctr,
                    "cpc": current_cpc,
                    "cpm": current_cpm,
                    "roas": current_roas
                }
            else:
                # Take the highest value for each metric
                metrics_by_date_and_ad[key]["spend"] = max(metrics_by_date_and_ad[key]["spend"], current_spend)
                metrics_by_date_and_ad[key]["clicks"] = max(metrics_by_date_and_ad[key]["clicks"], current_clicks)
                metrics_by_date_and_ad[key]["impressions"] = max(metrics_by_date_and_ad[key]["impressions"], current_impressions)
                metrics_by_date_and_ad[key]["purchases"] = max(metrics_by_date_and_ad[key]["purchases"], current_purchases)
                metrics_by_date_and_ad[key]["revenue"] = max(metrics_by_date_and_ad[key]["revenue"], current_revenue)
                metrics_by_date_and_ad[key]["ctr"] = max(metrics_by_date_and_ad[key]["ctr"], current_ctr)
                metrics_by_date_and_ad[key]["cpc"] = max(metrics_by_date_and_ad[key]["cpc"], current_cpc)
                metrics_by_date_and_ad[key]["cpm"] = max(metrics_by_date_and_ad[key]["cpm"], current_cpm)
                metrics_by_date_and_ad[key]["roas"] = max(metrics_by_date_and_ad[key]["roas"], current_roas)
        
        # Convert to list and sort by date and ad_id
        ad_metrics = list(metrics_by_date_and_ad.values())
        # Use a safe sort key function that handles None values
        ad_metrics.sort(key=lambda x: (x["date"], x["ad_id"] or ""))
        
        return AdMetricsByAdResponse(
            ad_metrics=ad_metrics,
            unique_ads=list(unique_ads.values()),
            date_range={"start_date": start_date, "end_date": end_date}
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics by ad: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 