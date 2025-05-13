import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings

from app.core.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class PredictionService:
    def __init__(self):
        pass
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance lazily when needed."""
        return get_database()
    
    async def predict_ad_metrics(
        self, 
        user_id: str, 
        ad_id: str, 
        start_date: str, 
        end_date: str, 
        days_to_predict: int = 7
    ) -> Dict[str, Any]:
        """
        Predict metrics for a specific ad based on historical data using time series forecasting.
        
        Args:
            user_id: The user ID
            ad_id: The ad ID to predict metrics for
            start_date: Start date for historical data (format: YYYY-MM-DD)
            end_date: End date for historical data (format: YYYY-MM-DD)
            days_to_predict: Number of days to predict into the future
            
        Returns:
            Dictionary with predicted metrics for each day and historical data
        """
        try:
            # Suppress statsmodels convergence warnings
            warnings.filterwarnings("ignore")
            
            # First, get historical metrics for this ad
            historical_metrics = await self._get_ad_historical_metrics(user_id, ad_id, start_date, end_date)
            
            if not historical_metrics or len(historical_metrics) < 3:
                logger.warning(f"Not enough historical data for ad {ad_id} to make predictions")
                return {
                    "ad_id": ad_id,
                    "predictions": [],
                    "historical": historical_metrics,
                    "success": False,
                    "message": "Not enough historical data to make predictions"
                }
            
            # Get ad details
            ad_info = await self._get_ad_details(user_id, ad_id)
            ad_title = ad_info.get("ad_title", "")
            
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(historical_metrics)
            
            # Ensure we have date column as datetime
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Set date as index for time series analysis
            df_ts = df.set_index('date')
            
            # Create a numerical representation of dates for regression fallback
            df['date_numeric'] = (df['date'] - df['date'].min()).dt.days
            
            # Convert missing values to 0
            metrics_to_predict = ['roas', 'ctr', 'cpc', 'cpm', 'conversions', 'revenue', 'spend']
            for metric in metrics_to_predict:
                if metric not in df.columns:
                    df[metric] = 0
                df[metric] = df[metric].fillna(0)
            
            # Prepare future dates to predict
            last_date = datetime.strptime(end_date, "%Y-%m-%d")
            future_dates = [last_date + timedelta(days=i+1) for i in range(days_to_predict)]
            future_date_numeric = [(last_date + timedelta(days=i+1) - df['date'].min().to_pydatetime()).days 
                                  for i in range(days_to_predict)]
            
            predictions = []
            
            # Predict each metric
            for i, future_date in enumerate(future_dates):
                day_prediction = {
                    "date": future_date.strftime("%Y-%m-%d"),
                    "ad_id": ad_id,
                    "ad_title": ad_title  # Add ad_title to each day prediction
                }
                
                for metric in metrics_to_predict:
                    # Only predict if we have enough non-zero data
                    non_zero_data = df[df[metric] > 0]
                    
                    # For time series forecasting, we need enough data points
                    if len(non_zero_data) >= 5:
                        try:
                            # Try to use ARIMA for time series with enough data
                            # Use (1,1,1) order as a simple starting point
                            ts_data = df_ts[metric].dropna()
                            
                            # Choose the best model based on data characteristics
                            if len(ts_data) >= 10:
                                # For longer time series, use ARIMA
                                model = ARIMA(ts_data, order=(1,1,1))
                                model_fit = model.fit()
                                # Predict days ahead
                                forecast_steps = i + 1
                                forecast = model_fit.forecast(steps=forecast_steps)
                                predicted_value = forecast.iloc[-1]
                            else:
                                # For shorter time series, use Exponential Smoothing
                                model = ExponentialSmoothing(ts_data, trend='add', seasonal=None)
                                model_fit = model.fit()
                                # Predict days ahead
                                forecast_steps = i + 1
                                forecast = model_fit.forecast(steps=forecast_steps)
                                predicted_value = forecast.iloc[-1]
                                
                            # Ensure prediction doesn't go below zero for metrics that can't be negative
                            predicted_value = max(0, predicted_value)
                            
                            day_prediction[metric] = float(predicted_value)
                        except Exception as e:
                            logger.warning(f"Time series prediction failed for {ad_id}, metric {metric}: {str(e)}")
                            # Fall back to linear regression if time series fails
                            X = non_zero_data[['date_numeric']].values
                            y = non_zero_data[metric].values
                            
                            model = LinearRegression()
                            model.fit(X, y)
                            
                            # Predict
                            predicted_value = model.predict([[future_date_numeric[i]]])[0]
                            predicted_value = max(0, predicted_value)
                            day_prediction[metric] = float(predicted_value)
                    elif len(non_zero_data) >= 3:
                        # Use linear regression for basic prediction if we have at least 3 data points
                        X = non_zero_data[['date_numeric']].values
                        y = non_zero_data[metric].values
                        
                        model = LinearRegression()
                        model.fit(X, y)
                        
                        # Predict
                        predicted_value = model.predict([[future_date_numeric[i]]])[0]
                        
                        # Ensure prediction doesn't go below zero for metrics that can't be negative
                        if metric in ['roas', 'ctr', 'cpc', 'cpm', 'conversions', 'revenue', 'spend']:
                            predicted_value = max(0, predicted_value)
                            
                        day_prediction[metric] = float(predicted_value)
                    else:
                        # Use average of last 3 days or whatever we have
                        recent_values = df[metric].tail(min(3, len(df))).values
                        if len(recent_values) > 0:
                            day_prediction[metric] = float(np.mean(recent_values))
                        else:
                            day_prediction[metric] = 0.0
                
                # Add this day's prediction to the list
                predictions.append(day_prediction)
            
            # Format historical data to match prediction format
            formatted_historical = []
            for _, row in df.iterrows():
                historical_point = {
                    "date": row['date'].strftime("%Y-%m-%d"),
                    "ad_id": ad_id,
                    "ad_title": ad_title
                }
                
                for metric in metrics_to_predict:
                    if metric in row:
                        historical_point[metric] = float(row[metric])
                
                formatted_historical.append(historical_point)
            
            return {
                "ad_id": ad_id,
                "predictions": predictions,
                "historical": formatted_historical,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error predicting metrics for ad {ad_id}: {str(e)}")
            return {
                "ad_id": ad_id,
                "predictions": [],
                "historical": [],
                "success": False,
                "message": f"Error making predictions: {str(e)}"
            }
    
    async def predict_all_user_ads(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        days_to_predict: int = 7,
        use_time_series: bool = True,
        only_analyzed_ads: bool = False
    ) -> Dict[str, Any]:
        """
        Predict metrics for all ads of a user.
        
        Args:
            user_id: The user ID
            start_date: Start date for historical data (format: YYYY-MM-DD)
            end_date: End date for historical data (format: YYYY-MM-DD)
            days_to_predict: Number of days to predict into the future
            use_time_series: If True, uses weighted scoring system. If False, uses frequency of top metrics.
            only_analyzed_ads: If True, only predict for ads that have entries in ad_analyses collection
            
        Returns:
            Dictionary with predictions for all ads and the best performing ad
        """
        try:
            # Get all the user's ads
            all_ads = await self._get_user_ads(user_id)
            
            if not all_ads:
                logger.warning(f"No ads found for user {user_id}")
                return {
                    "success": False,
                    "message": "No ads found",
                    "predictions": [],
                    "best_ad": None
                }
            
            # Filter ads to only those in ad_analyses if required
            if only_analyzed_ads:
                logger.info(f"Filtering {len(all_ads)} ads to only those with analyses in the database")
                # Get all video_ids from ad_analyses
                analyzed_ads = []
                try:
                    # Get unique ad_id or video_id from ad_analyses
                    cursor = self.db.ad_analyses.find({"user_id": user_id})
                    ad_analyses = await cursor.to_list(length=None)
                    
                    logger.info(f"Found {len(ad_analyses)} ad analyses in the database for user {user_id}")
                    
                    # Create a set of all video_ids and ad_ids
                    analyzed_video_ids = set()
                    for analysis in ad_analyses:
                        if "video_id" in analysis and analysis["video_id"]:
                            analyzed_video_ids.add(analysis["video_id"])
                        if "ad_id" in analysis and analysis["ad_id"]:
                            analyzed_video_ids.add(analysis["ad_id"])
                    
                    logger.info(f"Found {len(analyzed_video_ids)} unique video/ad IDs in ad_analyses")
                    
                    # Get matching ads from ad_metrics using campaign_id
                    campaign_ids = set()
                    for analysis in ad_analyses:
                        if "campaign_id" in analysis and analysis["campaign_id"]:
                            campaign_ids.add(analysis["campaign_id"])
                    
                    logger.info(f"Found {len(campaign_ids)} unique campaign IDs in ad_analyses")
                    
                    # Filter ads that match either by direct id or campaign_id
                    for ad in all_ads:
                        ad_id = ad["ad_id"]
                        # Check if this ad's ID matches any video_id in ad_analyses
                        if ad_id in analyzed_video_ids:
                            analyzed_ads.append(ad)
                            logger.info(f"Including ad {ad_id} - direct match with video_id")
                            continue
                            
                        # Otherwise check if we can find this ad's campaign_id in ad_metrics
                        try:
                            ad_metric = await self.db.ad_metrics.find_one({"user_id": user_id, "ad_id": ad_id})
                            if ad_metric and "campaign_id" in ad_metric and ad_metric["campaign_id"] in campaign_ids:
                                analyzed_ads.append(ad)
                                logger.info(f"Including ad {ad_id} - campaign match with {ad_metric['campaign_id']}")
                        except Exception as e:
                            logger.error(f"Error checking campaign_id for ad {ad_id}: {str(e)}")
                    
                    if not analyzed_ads:
                        logger.warning(f"No analyzed ads found for user {user_id} after filtering")
                        # Fallback to using all ads if none match
                        analyzed_ads = all_ads
                except Exception as e:
                    logger.error(f"Error filtering for analyzed ads: {str(e)}")
                    # On error, just use all ads
                    analyzed_ads = all_ads
                
                # Use the filtered ads list
                all_ads = analyzed_ads
                logger.info(f"Filtered to {len(all_ads)} ads that have analyses")
            
            # Predict metrics for each ad
            all_predictions = []
            for ad in all_ads:
                ad_id = ad["ad_id"]
                ad_name = ad.get("ad_name", "Unknown Ad")
                
                if use_time_series:
                    # Get full predictions with time series forecasting
                    prediction = await self.predict_ad_metrics(
                        user_id=user_id,
                        ad_id=ad_id,
                        start_date=start_date,
                        end_date=end_date,
                        days_to_predict=days_to_predict
                    )
                    
                    if prediction["success"] and prediction["predictions"]:
                        # Add ad_name to each prediction
                        for pred in prediction["predictions"]:
                            pred["ad_name"] = ad_name
                        
                        all_predictions.append(prediction)
                else:
                    # For frequency-based analysis, we only need historical data
                    historical_metrics = await self._get_ad_historical_metrics(
                        user_id=user_id,
                        ad_id=ad_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    # Get ad details
                    ad_info = await self._get_ad_details(user_id, ad_id)
                    ad_title = ad_info.get("ad_title", "")
                    
                    # Format historical data
                    formatted_historical = []
                    for metric in historical_metrics:
                        historical_point = {
                            "date": metric.get("date", ""),
                            "ad_id": ad_id,
                            "ad_name": ad_name,
                            "ad_title": ad_title
                        }
                        
                        for field in ["roas", "ctr", "cpc", "cpm", "conversions", "revenue", "spend"]:
                            if field in metric:
                                historical_point[field] = float(metric[field])
                        
                        formatted_historical.append(historical_point)
                    
                    if formatted_historical:
                        all_predictions.append({
                            "ad_id": ad_id,
                            "historical": formatted_historical,
                            "predictions": [],  # Empty predictions for frequency-based mode
                            "success": True
                        })
            
            # Find the best performing ad
            best_ad = await self._find_best_performing_ad(all_predictions, use_time_series)
            
            return {
                "success": True,
                "predictions": all_predictions,
                "best_ad": best_ad
            }
            
        except Exception as e:
            logger.error(f"Error predicting metrics for all ads: {str(e)}")
            return {
                "success": False,
                "message": f"Error making predictions: {str(e)}",
                "predictions": [],
                "best_ad": None
            }
    
    async def _find_best_performing_ad(self, all_predictions: List[Dict[str, Any]], use_time_series: bool = True) -> Dict[str, Any]:
        """
        Find the best performing ad based on metrics.
        
        Uses a weighted scoring system across all metrics to determine the best ad.
        """
        if not all_predictions:
            return None
            
        if use_time_series:
            # Weights for different metrics (can be adjusted based on importance)
            weights = {
                "roas": 0.3,  # Return on ad spend is very important
                "ctr": 0.15,  # Click-through rate
                "cpc": -0.1,  # Cost per click (lower is better, hence negative)
                "cpm": -0.05, # Cost per mille (lower is better)
                "conversions": 0.2, # Number of conversions
                "revenue": 0.2 # Revenue generated
            }
            
            # Calculate average predicted metrics for each ad
            ad_scores = {}
            for prediction in all_predictions:
                ad_id = prediction["ad_id"]
                if not prediction.get("predictions"):
                    continue
                    
                # Get the average values for each metric across all predicted days
                metrics_sum = {}
                for day_prediction in prediction["predictions"]:
                    for metric, weight in weights.items():
                        if metric in day_prediction:
                            metrics_sum[metric] = metrics_sum.get(metric, 0) + day_prediction[metric]
                
                # Calculate the averages
                days_count = len(prediction["predictions"])
                metrics_avg = {metric: value / days_count for metric, value in metrics_sum.items()}
                
                # Get ad details from first prediction
                ad_name = prediction["predictions"][0].get("ad_name", "Unknown Ad")
                ad_title = prediction["predictions"][0].get("ad_title", "")  # Get ad_title if available
                
                # Calculate score
                score = 0
                for metric, weight in weights.items():
                    if metric in metrics_avg:
                        score += metrics_avg[metric] * weight
                
                ad_scores[ad_id] = {
                    "ad_id": ad_id,
                    "ad_name": ad_name,
                    "ad_title": ad_title,  # Include ad_title in the result
                    "score": score,
                    "average_metrics": metrics_avg
                }
            
            # Find the ad with the highest score
            if not ad_scores:
                return None
                
            best_ad_id = max(ad_scores.keys(), key=lambda x: ad_scores[x]["score"])
            
            # Try to enhance the best ad with ad_title from ad_analyses if it's not already set
            best_ad = ad_scores[best_ad_id]
            
            # If no ad_title is set, try to get it from ad_analyses
            if not best_ad.get("ad_title"):
                try:
                    # Get user_id from the first prediction
                    user_id = None
                    for prediction in all_predictions:
                        if "user_id" in prediction:
                            user_id = prediction["user_id"]
                            break
                    
                    if user_id:
                        # Try to find title in ad_analyses
                        analysis = await self.db.ad_analyses.find_one({
                            "user_id": user_id,
                            "$or": [
                                {"ad_id": best_ad_id},
                                {"video_id": best_ad_id}
                            ]
                        })
                        
                        if analysis and "ad_title" in analysis:
                            best_ad["ad_title"] = analysis["ad_title"]
                            logger.info(f"Enhanced best ad with title from ad_analyses: {analysis['ad_title']}")
                except Exception as e:
                    logger.error(f"Error getting ad_title from ad_analyses: {str(e)}")
            
            return best_ad
        else:
            # Frequency-based scoring system
            metrics_to_track = ["roas", "ctr", "conversions", "revenue"]
            ad_frequencies = {}
            
            # For each ad, analyze historical data
            for prediction in all_predictions:
                ad_id = prediction["ad_id"]
                historical_data = prediction.get("historical", [])
                
                if not historical_data:
                    continue
                
                if ad_id not in ad_frequencies:
                    first_historical = historical_data[0] if historical_data else {}
                    ad_name = first_historical.get("ad_name", "Unknown Ad")
                    ad_title = first_historical.get("ad_title", "")
                    
                    ad_frequencies[ad_id] = {
                        "ad_id": ad_id,
                        "ad_name": ad_name,
                        "ad_title": ad_title,
                        "top_metrics_count": 0,
                        "total_days": len(historical_data),
                        "metrics_sum": {metric: 0 for metric in metrics_to_track}
                    }
                
                # For each day in historical data
                for day_data in historical_data:
                    date = day_data.get("date", "")
                    
                    # Sum up the metrics for averaging
                    for metric in metrics_to_track:
                        if metric in day_data:
                            ad_frequencies[ad_id]["metrics_sum"][metric] += day_data[metric]
                            
                            # Get all values for this metric across all ads for this date
                            all_values = [
                                h_data[metric]
                                for p in all_predictions
                                for h_data in p.get("historical", [])
                                if h_data.get("date") == date and metric in h_data
                            ]
                            
                            # If this ad had the highest value for this metric on this day
                            if all_values and day_data[metric] == max(all_values):
                                ad_frequencies[ad_id]["top_metrics_count"] += 1
            
            # Calculate final scores and averages
            for ad_id, data in ad_frequencies.items():
                if data["total_days"] > 0:
                    # Calculate average metrics
                    data["average_metrics"] = {
                        metric: data["metrics_sum"][metric] / data["total_days"]
                        for metric in metrics_to_track
                    }
                    # Score is the percentage of times this ad was top performer
                    total_possible = data["total_days"] * len(metrics_to_track)
                    if total_possible > 0:
                        data["score"] = (data["top_metrics_count"] / total_possible) * 100
                    else:
                        data["score"] = 0
                else:
                    data["average_metrics"] = {metric: 0 for metric in metrics_to_track}
                    data["score"] = 0
                    
                # Remove the temporary metrics_sum
                del data["metrics_sum"]
            
            # Find the ad with the highest frequency score
            if not ad_frequencies:
                return None
                
            best_ad_id = max(ad_frequencies.keys(), key=lambda x: ad_frequencies[x]["score"])
            best_ad = ad_frequencies[best_ad_id]
            
            # Try to enhance the best ad with ad_title from ad_analyses if it's not already set
            if not best_ad.get("ad_title"):
                try:
                    # Get user_id from the first prediction
                    user_id = None
                    for prediction in all_predictions:
                        if "user_id" in prediction:
                            user_id = prediction["user_id"]
                            break
                    
                    if user_id:
                        # Try to find title in ad_analyses
                        analysis = await self.db.ad_analyses.find_one({
                            "user_id": user_id,
                            "$or": [
                                {"ad_id": best_ad_id},
                                {"video_id": best_ad_id}
                            ]
                        })
                        
                        if analysis and "ad_title" in analysis:
                            best_ad["ad_title"] = analysis["ad_title"]
                            logger.info(f"Enhanced best ad with title from ad_analyses: {analysis['ad_title']}")
                except Exception as e:
                    logger.error(f"Error getting ad_title from ad_analyses: {str(e)}")
            
            return best_ad
    
    async def _get_ad_historical_metrics(
        self, 
        user_id: str, 
        ad_id: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get historical metrics for a specific ad."""
        try:
            # Convert string dates to datetime objects
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            
            # Query metrics for this specific ad
            cursor = self.db.ad_metrics.find({
                "user_id": user_id,
                "ad_id": ad_id,
                "collected_at": {
                    "$gte": start_date_obj,
                    "$lte": end_date_obj
                }
            })
            
            metrics = await cursor.to_list(length=None)
            
            # Process metrics to get daily values
            daily_metrics = {}
            for metric in metrics:
                date_str = metric["collected_at"].strftime("%Y-%m-%d")
                additional_metrics = metric.get("additional_metrics", {})
                
                if date_str not in daily_metrics:
                    daily_metrics[date_str] = {
                        "date": date_str,
                        "ad_id": ad_id,
                        "roas": additional_metrics.get("roas", 0),
                        "ctr": additional_metrics.get("ctr", 0),
                        "cpc": additional_metrics.get("cpc", 0),
                        "cpm": additional_metrics.get("cpm", 0),
                        "conversions": metric.get("purchases", 0),
                        "revenue": additional_metrics.get("purchases_value", 0),
                        "spend": additional_metrics.get("spend", 0)
                    }
                else:
                    # If we have multiple entries for the same day, use the latest one
                    for key in ["roas", "ctr", "cpc", "cpm", "spend"]:
                        if key in additional_metrics:
                            daily_metrics[date_str][key] = additional_metrics[key]
                    
                    # Handle purchases and purchases_value separately
                    if "purchases" in metric:
                        daily_metrics[date_str]["conversions"] = metric["purchases"]
                    if "purchases_value" in additional_metrics:
                        daily_metrics[date_str]["revenue"] = additional_metrics["purchases_value"]
            
            return list(daily_metrics.values())
            
        except Exception as e:
            logger.error(f"Error getting historical metrics for ad {ad_id}: {str(e)}")
            return []
    
    async def _get_user_ads(self, user_id: str) -> List[Dict[str, str]]:
        """Get all ads for a user."""
        try:
            # Use aggregation to get distinct ads
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id
                    }
                },
                {
                    "$group": {
                        "_id": "$ad_id",
                        "ad_name": {"$first": "$ad_name"}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "ad_id": "$_id",
                        "ad_name": 1
                    }
                }
            ]
            
            result = await self.db.ad_metrics.aggregate(pipeline).to_list(length=None)
            return result
            
        except Exception as e:
            logger.error(f"Error getting user ads: {str(e)}")
            return [] 
    
    async def _get_ad_details(self, user_id: str, ad_id: str) -> Dict[str, Any]:
        """Get ad details including title."""
        try:
            # First check for ad information in ad_metrics
            cursor = self.db.ad_metrics.find({
                "user_id": user_id,
                "ad_id": ad_id
            }).limit(1)
            
            ad_info = await cursor.to_list(length=1)
            
            # Initialize with defaults
            ad_title = ""
            ad_name = "Unknown Ad"
            
            if ad_info:
                metric = ad_info[0]
                ad_title = metric.get("ad_title", "")
                ad_name = metric.get("ad_name", "Unknown Ad")
            
            # If no ad_title was found, check in ad_analyses collection
            if not ad_title:
                # Try to find by ad_id first
                analysis = await self.db.ad_analyses.find_one({
                    "user_id": user_id,
                    "ad_id": ad_id
                })
                
                # If not found, try by video_id
                if not analysis:
                    analysis = await self.db.ad_analyses.find_one({
                        "user_id": user_id,
                        "video_id": ad_id
                    })
                
                # If we found an analysis, extract the title
                if analysis:
                    ad_title = analysis.get("ad_title", "")
                    logger.info(f"Found ad_title '{ad_title}' from ad_analyses for ad {ad_id}")
                    
                    # If no name yet, use the ad_message as a fallback
                    if ad_name == "Unknown Ad" and analysis.get("ad_message"):
                        ad_name = analysis.get("ad_message")[:30] + "..." if len(analysis.get("ad_message", "")) > 30 else analysis.get("ad_message", "")
            
            return {
                "ad_title": ad_title,
                "ad_name": ad_name
            }
        except Exception as e:
            logger.error(f"Error getting ad details for ad {ad_id}: {str(e)}")
            return {"ad_title": "", "ad_name": "Unknown Ad"} 