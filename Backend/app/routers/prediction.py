from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.services.prediction_service import PredictionService
from app.services.prediction_time_series import TimeSeriesPredictionService
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/predictions", tags=["predictions"])

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
    current_user: User = Depends(get_current_user)
):
    """
    Find the best performing ad based on predicted metrics.
    Uses time series forecasting by default for more accurate predictions.
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
        
        # Predict metrics for all ads and get the best one
        result = await prediction_service.predict_all_user_ads(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            days_to_predict=days_to_predict
        )
        
        # If we have a successful result with a best_ad, return it
        if result["success"] and result["best_ad"]:
            return {
                "success": True,
                "best_ad": result["best_ad"]
            }
        
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
                
                # Create a fallback best ad
                return {
                    "success": True,
                    "best_ad": {
                        "ad_id": first_ad["ad_id"],
                        "ad_name": ad_name,
                        "average_metrics": metrics_avg
                    }
                }
        
        # If we still don't have data, return an error message
        if not result["success"] or not result["best_ad"]:
            # Log the original error message
            if "message" in result:
                print(f"Original prediction error: {result['message']}")
                
            # Return error message instead of sample data
            return {
                "success": False,
                "message": "No ad performance data available to make predictions. Please ensure you have ad data for the selected date range."
            }
        
        # For any other cases, return the original result
        return {
            "success": False,
            "message": result.get("message", "Failed to find best performing ad")
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return error instead of fallback sample data
        return {
            "success": False,
            "message": f"Error finding best performing ad: {str(e)}"
        } 