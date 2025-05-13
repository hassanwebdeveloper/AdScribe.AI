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
import asyncio

from app.core.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class TimeSeriesPredictionService:
    def __init__(self):
        # Suppress statsmodels convergence warnings
        warnings.filterwarnings("ignore")
    
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
            
            if not historical_metrics or len(historical_metrics) < 1:
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
            
            # Ensure dates are in datetime format and sort
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Set date as index for time series analysis
            df_ts = df.set_index('date')
            
            # Define metrics to predict
            metrics_to_predict = ['roas', 'ctr', 'cpc', 'cpm', 'conversions', 'revenue', 'spend']
            
            # For each metric, fill missing values with 0 or forward fill
            for metric in metrics_to_predict:
                if metric not in df.columns:
                    df[metric] = 0
                df[metric] = df[metric].fillna(method='ffill').fillna(0)
            
            # Prepare future dates to predict
            last_date = datetime.strptime(end_date, "%Y-%m-%d")
            future_dates = [last_date + timedelta(days=i+1) for i in range(days_to_predict)]
            
            predictions = []
            
            # Detect patterns in the data
            has_weekly_pattern = False
            days_count = len(df)
            
            if days_count >= 14:
                # Check for weekly patterns if we have at least 2 weeks of data
                for metric in metrics_to_predict:
                    if metric in df.columns:
                        # Calculate autocorrelation at lag 7 (weekly)
                        series = df[metric].values
                        if len(series) > 7:
                            try:
                                acf = np.corrcoef(series[7:], series[:-7])[0, 1]
                                if abs(acf) > 0.3:  # If there's meaningful correlation
                                    has_weekly_pattern = True
                                    break
                            except:
                                pass
            
            # Add a fallback model selection logic based on available data
            model_type = "simple_average"  # Default for very limited data
            if days_count >= 14 and has_weekly_pattern:
                model_type = "sarima"
            elif days_count >= 10:
                model_type = "arima"
            elif days_count >= 5:
                model_type = "exp_smoothing"
            elif days_count >= 2:
                model_type = "trend_extension"
                
            logger.info(f"Using {model_type} model for ad {ad_id} with {days_count} days of data")
            
            # Predict each metric for each future date
            for i, future_date in enumerate(future_dates):
                day_prediction = {
                    "date": future_date.strftime("%Y-%m-%d"),
                    "ad_id": ad_id,
                    "ad_title": ad_title
                }
                
                for metric in metrics_to_predict:
                    try:
                        # Get time series data for this metric
                        ts_data = df_ts[metric].copy()
                        
                        # Calculate variance and mean to check for volatility
                        metric_variance = ts_data.var()
                        metric_mean = ts_data.mean()
                        
                        # Calculate coefficient of variation to measure volatility
                        cv = (metric_variance ** 0.5) / metric_mean if metric_mean > 0 else 0
                        is_volatile = cv > 0.3  # If coefficient of variation > 30%
                        
                        # Check for recent trend by looking at last 3-5 data points
                        recent_data = ts_data.tail(min(5, len(ts_data)))
                        recent_slope = 0
                        
                        if len(recent_data) >= 3:
                            x = np.arange(len(recent_data))
                            y = recent_data.values
                            # Simple linear regression to detect trend
                            if np.std(y) > 0:  # Only if there's variation
                                slope, _, _, _, _ = stats.linregress(x, y)
                                recent_slope = slope
                        
                        # Select appropriate model based on data characteristics
                        if model_type == "sarima":
                            # SARIMA with weekly seasonality (s=7)
                            try:
                                from statsmodels.tsa.statespace.sarimax import SARIMAX
                                
                                # Adjust parameters based on volatility
                                p, d, q = (2, 1, 2) if is_volatile else (1, 1, 1)
                                model = SARIMAX(ts_data, 
                                               order=(p, d, q),
                                               seasonal_order=(1, 0, 1, 7))
                                model_fit = model.fit(disp=False)
                                forecast = model_fit.forecast(steps=i+1)
                                predicted_value = forecast.iloc[-1]
                            except Exception as e:
                                logger.warning(f"SARIMA forecast failed: {str(e)}, falling back to ARIMA")
                                # Fall back to simpler model
                                model = ARIMA(ts_data, order=(1, 1, 1))
                                model_fit = model.fit()
                                forecast = model_fit.forecast(steps=i+1)
                                predicted_value = forecast.iloc[-1]
                        elif model_type == "arima":
                            # Adjust ARIMA parameters based on data characteristics
                            if is_volatile:
                                # More complex model for volatile data
                                model = ARIMA(ts_data, order=(2, 1, 2))
                            else:
                                # Standard model for stable data
                                model = ARIMA(ts_data, order=(1, 1, 1))
                                
                            model_fit = model.fit()
                            forecast = model_fit.forecast(steps=i+1)
                            predicted_value = forecast.iloc[-1]
                        elif model_type == "exp_smoothing":
                            # Use Exponential Smoothing with trend component based on data
                            if abs(recent_slope) > 0.1:  # If there's a noticeable trend
                                model = ExponentialSmoothing(ts_data, trend='add', seasonal=None, damped=True)
                            else:
                                model = ExponentialSmoothing(ts_data, trend='add', seasonal=None)
                                
                            model_fit = model.fit()
                            forecast = model_fit.forecast(steps=i+1)
                            predicted_value = forecast.iloc[-1]
                        elif model_type == "trend_extension":
                            # For very limited data, use simple average with trend
                            base_value = ts_data.mean()
                            trend_factor = recent_slope * (i + 1) if abs(recent_slope) > 0 else 0
                            predicted_value = base_value + trend_factor
                        else:  # simple_average
                            # Simplest model: just repeat the existing value(s)
                            predicted_value = ts_data.mean()
                            
                            # If there's only one data point, we'll just use that value
                            if len(ts_data) == 1:
                                logger.info(f"Only one data point for ad {ad_id}, using that value for predictions")
                                predicted_value = ts_data.iloc[0]
                        
                        # Ensure continuity with historical data
                        if i == 0 and len(ts_data) > 0:
                            # For the first prediction, blend with the last historical value
                            # to ensure continuity
                            last_actual = ts_data.iloc[-1]
                            # Weighted average: 30% last actual + 70% model prediction
                            blended_value = 0.3 * last_actual + 0.7 * predicted_value
                            predicted_value = blended_value
                        
                        # Ensure prediction is non-negative
                        predicted_value = max(0, predicted_value)
                            
                        # Add to prediction
                        day_prediction[metric] = float(predicted_value)
                        
                    except Exception as e:
                        logger.warning(f"Error predicting {metric} for ad {ad_id}: {str(e)}")
                        # Fall back to mean of last values with trend
                        last_values = df[metric].tail(min(5, len(df))).values
                        if len(last_values) > 0:
                            # Simple trend-based prediction
                            mean_value = np.mean(last_values)
                            if len(last_values) >= 3:
                                # Calculate trend
                                x = np.arange(len(last_values))
                                y = last_values
                                if np.std(y) > 0:
                                    try:
                                        slope, _, _, _, _ = stats.linregress(x, y)
                                        trend = slope * (i + 1)
                                        day_prediction[metric] = float(mean_value + trend)
                                    except:
                                        day_prediction[metric] = float(mean_value)
                                else:
                                    day_prediction[metric] = float(mean_value)
                            else:
                                day_prediction[metric] = float(mean_value)
                        else:
                            day_prediction[metric] = 0.0
                
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
            
            # Sort historical data by date
            formatted_historical.sort(key=lambda x: x["date"])
            
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
        use_time_series: bool = True,  # Added parameter, will be ignored in this class
        only_analyzed_ads: bool = False  # Added parameter for filtering ads
    ) -> Dict[str, Any]:
        """
        Predict metrics for all ads of a user using time series forecasting.
        
        Args:
            user_id: The user ID
            start_date: Start date for historical data (format: YYYY-MM-DD)
            end_date: End date for historical data (format: YYYY-MM-DD)
            days_to_predict: Number of days to predict into the future
            use_time_series: Ignored in TimeSeriesPredictionService (always true)
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
            
            # Find the best performing ad based on multiple metrics
            best_ad = self._find_best_performing_ad(all_predictions)
            
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
    
    def _find_best_performing_ad(self, all_predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Find the best performing ad based on metrics.
        
        Uses a weighted scoring system across all metrics to determine the best ad.
        """
        if not all_predictions:
            return None
            
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
                    loop = asyncio.get_event_loop()
                    analysis = loop.run_until_complete(
                        self.db.ad_analyses.find_one({
                            "user_id": user_id,
                            "$or": [
                                {"ad_id": best_ad_id},
                                {"video_id": best_ad_id}
                            ]
                        })
                    )
                    
                    if analysis and "ad_title" in analysis:
                        best_ad["ad_title"] = analysis["ad_title"]
                        logger.info(f"Enhanced best ad with title from ad_analyses: {analysis['ad_title']}")
            except Exception as e:
                logger.error(f"Error getting ad_title from ad_analyses in time series model: {str(e)}")
        
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
            
            # Log query parameters for debugging
            logger.info(f"Querying ad metrics for user_id={user_id}, ad_id={ad_id}, date range={start_date} to {end_date}")
            
            # Query metrics for this specific ad
            query = {
                "user_id": user_id,
                "ad_id": ad_id,
                "collected_at": {
                    "$gte": start_date_obj,
                    "$lte": end_date_obj
                }
            }
            
            # First, count how many metrics match our query
            count = await self.db.ad_metrics.count_documents(query)
            logger.info(f"Found {count} metrics records for ad {ad_id}")
            
            # If we didn't find any records, try with a more inclusive query (without date range)
            if count == 0:
                logger.warning(f"No metrics found for ad {ad_id} in date range, trying without date restriction")
                query = {
                    "user_id": user_id,
                    "ad_id": ad_id,
                }
                count = await self.db.ad_metrics.count_documents(query)
                logger.info(f"Found {count} metrics records for ad {ad_id} without date restriction")
                
                # If we still don't have any records, we can't make predictions
                if count == 0:
                    return []
            
            # Proceed with query (either the original or updated one)
            cursor = self.db.ad_metrics.find(query)
            
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