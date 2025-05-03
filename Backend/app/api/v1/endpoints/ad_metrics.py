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

class DashboardResponse(BaseModel):
    current_period: PeriodMetrics
    previous_period: PeriodMetrics
    daily_metrics: List[DailyMetric] = Field(default_factory=list)
    refresh_status: RefreshStatus = Field(default_factory=RefreshStatus)

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
    current_user: User = Depends(get_current_user),
):
    """
    Get metrics dashboard for current user.
    If we don't have complete data for the requested date range,
    we'll fetch the latest data from Facebook.
    """
    try:
        # Parse dates
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            logger.error(f"Invalid date format: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

        logger.info(f"Dashboard request: start_date={start_date}, end_date={end_date}, force_refresh={force_refresh}")
        
        # Initialize MetricsService
        metrics_service = MetricsService()
        
        # Check if we have complete data for the requested period
        has_complete_data = await metrics_service.has_complete_data_for_range(
            current_user.id, start_date_obj, end_date_obj
        )
        logger.info(f"Has complete data for current period: {has_complete_data}")

        # Calculate previous period dates (same length as current period)
        period_length = (end_date_obj - start_date_obj).days
        prev_end_date_obj = start_date_obj - timedelta(days=1)
        prev_start_date_obj = prev_end_date_obj - timedelta(days=period_length)
        prev_start_date = prev_start_date_obj.strftime("%Y-%m-%d")
        prev_end_date = prev_end_date_obj.strftime("%Y-%m-%d")
        
        # Check if we have complete data for the previous period
        has_prev_complete_data = await metrics_service.has_complete_data_for_range(
            current_user.id, prev_start_date_obj, prev_end_date_obj
        )
        logger.info(f"Has complete data for previous period: {has_prev_complete_data}")

        # Get FB credentials for the user
        user_service = UserService()
        fb_credentials = await user_service.get_facebook_credentials(current_user.id)
        
        # Debug log the full credentials object to see what's happening
        logger.info(f"Facebook credentials object for user {current_user.id}: {fb_credentials}")
        
        # Check what credential fields are present 
        if hasattr(current_user, 'fb_graph_api_key'):
            logger.info(f"User has fb_graph_api_key: {bool(current_user.fb_graph_api_key)}")
        
        if hasattr(current_user, 'fb_ad_account_id'):
            logger.info(f"User has fb_ad_account_id: {bool(current_user.fb_ad_account_id)}")
        
        if hasattr(current_user, 'facebook_credentials'):
            logger.info(f"User has facebook_credentials: {bool(current_user.facebook_credentials)}")
        
        # We need both access_token and account_id for valid credentials
        has_credentials = (
            bool(fb_credentials) and 
            'access_token' in fb_credentials and 
            'account_id' in fb_credentials
        )
        
        logger.info(f"User {current_user.id} has complete Facebook credentials: {has_credentials}")
        
        if has_credentials:
            # Log details of the credentials (careful with sensitive data)
            logger.info(f"Account ID: {fb_credentials.get('account_id')}")
            token = fb_credentials.get('access_token', '')
            if token:
                masked_token = token[:5] + '*****' + token[-5:] if len(token) > 10 else '*****'
                logger.info(f"Access token: {masked_token}")
        else:
            logger.warning(f"No Facebook credentials found for user {current_user.id} - will continue with available data only")
            # Don't attempt to fetch from Facebook if no credentials available
            need_to_fetch = False

        # Determine if we need to fetch data from Facebook (only if we have credentials)
        need_to_fetch = (force_refresh or not has_complete_data or not has_prev_complete_data) and has_credentials
        logger.info(f"Need to fetch from Facebook: {need_to_fetch} (force_refresh={force_refresh}, has_complete_data={has_complete_data}, has_prev_complete_data={has_prev_complete_data}, has_credentials={has_credentials})")

        metrics_fetched = False
        
        # If we don't have complete data for either period and have credentials, try to fetch from Facebook
        if need_to_fetch:
            logger.info(f"Attempting to fetch metrics from Facebook for user {current_user.id}")
            try:
                # Fetch metrics for both periods in one go
                # Convert dates to strings to avoid type comparison issues
                prev_start_str = prev_start_date_obj.strftime("%Y-%m-%d")
                start_str = start_date_obj.strftime("%Y-%m-%d")
                prev_end_str = prev_end_date_obj.strftime("%Y-%m-%d") 
                end_str = end_date_obj.strftime("%Y-%m-%d")
                
                # Find the earlier start date and later end date
                fetch_start_date = prev_start_date_obj if prev_start_str < start_str else start_date_obj
                fetch_end_date = end_date_obj if end_str > prev_end_str else prev_end_date_obj
                
                # Use time_increment=1 to get daily breakdown
                num_metrics = await metrics_service.fetch_metrics_from_facebook(
                    user_id=current_user.id,
                    start_date=fetch_start_date,
                    end_date=fetch_end_date,
                    credentials=fb_credentials
                )
                
                # Check if num_metrics is a list and get its length, otherwise treat as int
                if isinstance(num_metrics, list):
                    metrics_fetched = len(num_metrics) > 0
                    logger.info(f"Fetched {len(num_metrics)} metrics (returned as list) from Facebook for date range {fetch_start_date} to {fetch_end_date}")
                else:
                    metrics_fetched = num_metrics > 0
                    logger.info(f"Fetched {num_metrics} metrics from Facebook for date range {fetch_start_date} to {fetch_end_date}")
            except Exception as e:
                logger.error(f"Error fetching metrics from Facebook: {str(e)}")
                # Continue with available data
        else:
            logger.info("Skipping Facebook fetch: Complete data already available for both periods")

        # After potentially fetching from Facebook, calculate aggregated KPIs
        # Current period
        current_agg_metrics = await metrics_service.get_aggregated_metrics(
            user_id=current_user.id,
            start_date=start_date_obj,
            end_date=end_date_obj,
        )
        
        # Previous period for comparison
        prev_agg_metrics = await metrics_service.get_aggregated_metrics(
            user_id=current_user.id,
            start_date=prev_start_date_obj,
            end_date=prev_end_date_obj,
        )
        
        # Get daily metrics for charts
        daily_metrics = await metrics_service.get_daily_metrics(
            user_id=current_user.id,
            start_date=start_date_obj,
            end_date=end_date_obj,
        )

        # Return the dashboard data
        response = {
            "current_period": {"start_date": start_date, "end_date": end_date, **current_agg_metrics},
            "previous_period": {"start_date": prev_start_date, "end_date": prev_end_date, **prev_agg_metrics},
            "daily_metrics": daily_metrics,
            "refresh_status": {
                "metrics_fetched": metrics_fetched,
                "has_complete_data": await metrics_service.has_complete_data_for_range(
                    current_user.id, start_date_obj, end_date_obj
                ),
                "force_refresh_attempted": force_refresh,
            }
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