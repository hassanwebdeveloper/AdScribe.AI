from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient

from ..core.database import get_database
from ..core.database import get_redis
from ..core.deps import get_current_user
from ..schemas.user import User
from ..services.facebook_api import FacebookAdService
from ..schemas.ad_metrics import AdMetricsResponse

router = APIRouter(
    prefix="/ad-metrics",
    tags=["ad-metrics"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

@router.get("/by-ad/", response_model=AdMetricsResponse)
async def get_ad_metrics_by_ad(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    force_refresh: bool = Query(False, description="Force refresh data from Facebook API"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorClient = Depends(get_database),
    redis_client: Any = Depends(get_redis),
):
    """
    Get ad metrics broken down by individual ad, grouped by day
    """
    try:
        # Validate dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Check if date range is valid
        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        # Check if date range is not too large
        if (end - start).days > 90:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")

        # Cache key for Redis
        cache_key = f"ad_metrics:by_ad:{current_user.id}:{start_date}:{end_date}"
        
        # Try to get from cache if not forcing refresh
        if not force_refresh:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Retrieved ad metrics from cache for user {current_user.id}")
                import json
                return json.loads(cached_data)
        
        # Get connected ad accounts for this user
        ad_accounts_collection = db.adscribe.ad_accounts
        ad_accounts = await ad_accounts_collection.find({"user_id": str(current_user.id)}).to_list(None)
        
        if not ad_accounts:
            raise HTTPException(status_code=404, detail="No ad accounts found for this user")
        
        # Collect metrics for all ad accounts
        all_metrics = []
        unique_ads = set()
        
        for ad_account in ad_accounts:
            # Skip accounts that are not connected
            if not ad_account.get("access_token"):
                continue
                
            # Initialize Facebook service
            fb_service = FacebookAdService(
                ad_account_id=ad_account["ad_account_id"],
                access_token=ad_account["access_token"]
            )
            
            # Get ad insights from Facebook
            try:
                account_metrics = await fb_service.get_ad_insights(
                    start_date=start_date,
                    end_date=end_date,
                    time_increment=1,  # Daily breakdown
                    fields=[
                        "ad_id", "ad_name", "spend", "impressions", "clicks", 
                        "actions", "action_values", "date_start"
                    ],
                    level="ad"  # Get data at the ad level
                )
                
                # Process metrics
                for metric in account_metrics:
                    # Extract purchase actions
                    purchases = 0
                    revenue = 0
                    
                    if "actions" in metric:
                        for action in metric["actions"]:
                            if action["action_type"] == "purchase":
                                purchases = int(action["value"])
                    
                    if "action_values" in metric:
                        for action_value in metric["action_values"]:
                            if action_value["action_type"] == "purchase":
                                revenue = float(action_value["value"])
                    
                    # Calculate derived metrics
                    spend = float(metric["spend"]) if "spend" in metric else 0
                    impressions = int(metric["impressions"]) if "impressions" in metric else 0
                    clicks = int(metric["clicks"]) if "clicks" in metric else 0
                    
                    # Avoid division by zero
                    ctr = clicks / impressions if impressions > 0 else 0
                    cpc = spend / clicks if clicks > 0 else 0
                    cpm = (spend / impressions) * 1000 if impressions > 0 else 0
                    roas = revenue / spend if spend > 0 else 0
                    
                    processed_metric = {
                        "date": metric["date_start"],
                        "ad_id": metric["ad_id"],
                        "ad_name": metric["ad_name"],
                        "spend": spend,
                        "revenue": revenue,
                        "clicks": clicks,
                        "impressions": impressions,
                        "purchases": purchases,
                        "ctr": ctr,
                        "cpc": cpc,
                        "cpm": cpm,
                        "roas": roas
                    }
                    
                    all_metrics.append(processed_metric)
                    unique_ads.add((metric["ad_id"], metric["ad_name"]))
                
            except Exception as e:
                logger.error(f"Error fetching insights for ad account {ad_account['ad_account_id']}: {str(e)}")
                # Continue to next account instead of failing completely
                continue
        
        # Format unique ads for response
        unique_ads_list = [{"ad_id": ad_id, "ad_name": ad_name} for ad_id, ad_name in unique_ads]
        
        # Sort ads by ad name
        unique_ads_list.sort(key=lambda x: x["ad_name"])
        
        # Prepare response
        response = {
            "ad_metrics": all_metrics,
            "unique_ads": unique_ads_list,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
        # Cache in Redis for 30 minutes
        import json
        await redis_client.setex(
            cache_key, 
            1800,  # 30 minutes in seconds
            json.dumps(response)
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in get_ad_metrics_by_ad: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 