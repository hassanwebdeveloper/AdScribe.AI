from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
import json

from app.services.prediction_service import PredictionService
from app.services.prediction_time_series import TimeSeriesPredictionService
from app.core.deps import get_current_user
from app.models.user import User
from app.services.metrics_service import MetricsService
from ..core.database import get_redis

router = APIRouter(prefix="/predictions", tags=["predictions"])
logger = logging.getLogger(__name__)

@router.get("/ad/{ad_id}")
async def predict_ad_metrics(
    ad_id: str,
    start_date: str = Query(..., description="Start date for historical data (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date for historical data (YYYY-MM-DD)"),
    days_to_predict: int = Query(7, description="Number of days to predict into the future"),
    use_time_series: bool = Query(True, description="Whether to use time series forecasting"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict metrics for a specific ad based on historical data.
    """
    if use_time_series:
        prediction_service = TimeSeriesPredictionService()
    else:
        prediction_service = PredictionService()
    
    try:
        # Validate date formats
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        
        # Get user_id from current user
        user_id = str(current_user.id)
        
        # Predict metrics
        result = await prediction_service.predict_ad_metrics(
            user_id=user_id,
            ad_id=ad_id,
            start_date=start_date,
            end_date=end_date,
            days_to_predict=days_to_predict
        )
        
        if not result["success"]:
            return {
                "success": False,
                "message": result.get("message", "Failed to predict metrics")
            }
            
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error predicting metrics: {str(e)}")

@router.get("/all-ads")
async def predict_all_ads_metrics(
    start_date: str = Query(..., description="Start date for historical data (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date for historical data (YYYY-MM-DD)"),
    days_to_predict: int = Query(7, description="Number of days to predict into the future"),
    use_time_series: bool = Query(True, description="Whether to use time series forecasting"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict metrics for all ads of the current user and find the best performing ad.
    """
    if use_time_series:
        prediction_service = TimeSeriesPredictionService()
    else:
        prediction_service = PredictionService()
    
    try:
        # Validate date formats
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        
        # Get user_id from current user
        user_id = str(current_user.id)
        
        # Predict metrics for all ads
        result = await prediction_service.predict_all_user_ads(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            days_to_predict=days_to_predict
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error predicting metrics: {str(e)}")

@router.get("/best-ad")
async def get_best_performing_ad(
    start_date: str = Query(..., description="Start date for historical data (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date for historical data (YYYY-MM-DD)"),
    days_to_predict: int = Query(7, description="Number of days to predict into the future"),
    use_time_series: bool = Query(True, description="Whether to use time series forecasting"),
    force_refresh: bool = Query(False, description="Force refresh data from Facebook API"),
    use_only_analyzed_ads: bool = Query(False, description="Only use ads that have entries in ad_analyses collection"),
    current_user: User = Depends(get_current_user),
    redis_client: Any = Depends(get_redis)
):
    """
    Find the best performing ad based on predicted metrics.
    Uses time series forecasting by default for more accurate predictions.
    If use_time_series is False, only returns the best ad based on frequency analysis without predictions.
    
    Before making predictions, ensures that all necessary historical data is available.
    """
    if use_time_series:
        prediction_service = TimeSeriesPredictionService()
    else:
        prediction_service = PredictionService()
    
    # Create metrics service for data completeness check
    metrics_service = MetricsService()
    
    try:
        # Validate date formats
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        
        # Ensure redis_client is a valid instance (handle direct function invocation in tests)
        if redis_client is None or not hasattr(redis_client, "get"):
            try:
                redis_client = get_redis()
            except Exception:
                redis_client = None  # Fallback to no-cache mode
        
        # Build cache key specific to user and parameters
        user_id = str(current_user.id)
        cache_key = (
            f"best_ad:{user_id}:{start_date}:{end_date}:"
            f"{int(use_time_series)}:{int(use_only_analyzed_ads)}"
        )

        # Try serving from cache unless force_refresh is requested and redis is available
        if redis_client and not force_refresh:
            cached_value = redis_client.get(cache_key)
            if cached_value:
                try:
                    return json.loads(cached_value)
                except Exception:
                    # Fall through to recompute if cache is corrupted
                    pass
        
        # First ensure data completeness
        logger.info(f"Ensuring data completeness for prediction for user {user_id} for date range {start_date} to {end_date}")
        completeness_result = await metrics_service.ensure_data_completeness(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            force_refresh=force_refresh
        )
        
        logger.info(f"Data completeness result: {completeness_result}")
        
        # Handle case when user doesn't have Facebook credentials
        if completeness_result.get("no_credentials"):
            logger.info(f"User {user_id} doesn't have Facebook credentials - continuing with existing data")
            # We'll proceed with prediction using existing data, but log a warning
        
        # If we couldn't get complete data and have no historical data, return an error
        if not completeness_result.get("has_complete_data") and not completeness_result.get("metrics_fetched"):
            # Check if we already have some data in the database
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            has_any_data = await metrics_service.has_any_data_for_range(user_id, start_date_obj, end_date_obj)
            
            if not has_any_data:
                return {
                    "success": False,
                    "message": "No historical data available for the selected date range. Please ensure you have ad data for the selected dates.",
                    "predictions": [],
                    "historical": []
                }
        
        # Predict metrics for all ads and get the best one
        result = await prediction_service.predict_all_user_ads(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            days_to_predict=days_to_predict,
            use_time_series=use_time_series,
            only_analyzed_ads=use_only_analyzed_ads
        )
        
        # If use_time_series is False, return only the best ad without predictions
        if not use_time_series and result["success"] and result["best_ad"]:
            # Find the historical data for the best ad
            best_ad_id = result["best_ad"]["ad_id"]
            best_ad_historical = []
            
            # Find the data for the best ad in the result predictions
            for prediction in result["predictions"]:
                if prediction["ad_id"] == best_ad_id:
                    best_ad_historical = prediction.get("historical", [])
                    break
            
            response_data = {
                "success": True,
                "best_ad": result["best_ad"],
                "predictions": [],  # Empty predictions when not using time series
                "historical": best_ad_historical  # Include historical data even in frequency mode
            }
            # Cache the response if redis available
            if redis_client:
                try:
                    redis_client.setex(cache_key, 3600, json.dumps(response_data))
                except Exception:
                    pass
            return response_data
        
        # If we have a successful result with a best_ad, return it
        if result["success"] and result["best_ad"]:
            # Get predictions and historical data for the best ad
            best_ad_id = result["best_ad"]["ad_id"]
            best_ad_data = None
            
            # Find the data for the best ad in the result predictions
            for prediction in result["predictions"]:
                if prediction["ad_id"] == best_ad_id:
                    best_ad_data = prediction
                    break
                    
            response_data = {
                "success": True,
                "best_ad": result["best_ad"],
                "predictions": best_ad_data["predictions"] if best_ad_data else [],
                "historical": best_ad_data["historical"] if best_ad_data else []
            }
            # Cache the response if redis available
            if redis_client:
                try:
                    redis_client.setex(cache_key, 3600, json.dumps(response_data))
                except Exception:
                    pass
            return response_data
        
        # If no best ad found but we have ads, try to generate a fallback best ad
        if result["success"] and result["predictions"] and len(result["predictions"]) > 0:
            # Try to create a best ad from the first prediction
            first_ad = result["predictions"][0]
            if first_ad["predictions"] and len(first_ad["predictions"]) > 0:
                # Calculate average metrics from available predictions
                metrics_sum = {}
                for day_pred in first_ad["predictions"]:
                    for metric in ["roas", "ctr", "cpc", "cpm", "conversions", "revenue"]:
                        if metric in day_pred:
                            metrics_sum[metric] = metrics_sum.get(metric, 0) + day_pred[metric]
                
                # Calculate averages
                days_count = len(first_ad["predictions"])
                metrics_avg = {metric: value / days_count for metric, value in metrics_sum.items()}
                
                # Get ad name from first prediction
                ad_name = first_ad["predictions"][0].get("ad_name", "Unknown Ad")
                
                response_data = {
                    "success": True,
                    "best_ad": {
                        "ad_id": first_ad["ad_id"],
                        "ad_name": ad_name,
                        "average_metrics": metrics_avg
                    },
                    "predictions": first_ad["predictions"],
                    "historical": first_ad["historical"] if "historical" in first_ad else []
                }
                # Cache the response if redis available
                if redis_client:
                    try:
                        redis_client.setex(cache_key, 3600, json.dumps(response_data))
                    except Exception:
                        pass
                return response_data
        
        # If we still don't have data, return an error message
        if not result["success"] or not result["best_ad"]:
            # Log the original error message
            if "message" in result:
                print(f"Original prediction error: {result['message']}")
                
            # Return error message instead of sample data
            return {
                "success": False,
                "message": "No ad performance data available to make predictions. Please ensure you have ad data for the selected date range.",
                "predictions": [],
                "historical": []
            }
        
        # For any other cases, return the original result
        return {
            "success": False,
            "message": result.get("message", "Failed to find best performing ad"),
            "predictions": [],
            "historical": []
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return error instead of fallback sample data
        return {
            "success": False,
            "message": f"Error finding best performing ad: {str(e)}",
            "predictions": [],
            "historical": []
        } 