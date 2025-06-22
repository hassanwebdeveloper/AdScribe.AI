"""
ML Optimization Service for ROAS Improvement Recommendations

This service implements an optimization-based approach to generate recommendations:
1. Train ML models to predict ROAS based on performance metrics
2. Optimize input parameters to achieve 10% ROAS improvement
3. Generate specific recommendations based on which parameters need to change
4. Automatically collect fresh data from Facebook API when insufficient historical data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from scipy.optimize import minimize, differential_evolution
import logging
from datetime import datetime, timedelta
import asyncio

from app.core.database import get_database
from app.services.openai_service import openai_service
from app.services.facebook_service import FacebookAdService
from app.services.user_service import UserService
from app.services.ml_recommendation_storage import MLRecommendationStorageService

logger = logging.getLogger(__name__)

class MLOptimizationService:
    """ML-based optimization service for ROAS improvement recommendations."""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        # Ensure feature_names matches the exact keys used in current_metrics
        self.feature_names = ['spend', 'ctr', 'cpc', 'cpm', 'clicks', 'impressions', 'purchases']
        self.model_trained = False
        self.feature_importance = {}
        self.user_service = UserService()
        self.storage_service = MLRecommendationStorageService()
        
        # Log feature names for debugging
        logger.info(f"Initialized ML optimization with features: {self.feature_names}")
        
    async def _calculate_account_level_metrics(self, user_id: str) -> Dict[str, float]:
        """Calculate account-level metrics including ROAS."""
        db = get_database()
        
        # Get last 30 days of data for account-level calculations
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "collected_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_spend": {"$sum": {"$toDouble": {"$ifNull": ["$additional_metrics.spend", 0]}}},
                    "total_revenue": {"$sum": {"$toDouble": {"$ifNull": ["$additional_metrics.purchases_value", 0]}}},
                    "total_clicks": {"$sum": {"$toInt": {"$ifNull": ["$additional_metrics.clicks", 0]}}},
                    "total_impressions": {"$sum": {"$toInt": {"$ifNull": ["$additional_metrics.impressions", 0]}}},
                    "total_purchases": {"$sum": {"$toInt": {"$ifNull": ["$purchases", 0]}}}
                }
            }
        ]
        
        results = await db.ad_metrics.aggregate(pipeline).to_list(length=1)
        
        if not results:
            return {
                "account_roas": 0,
                "account_ctr": 0,
                "account_conversion_rate": 0,
                "total_spend": 0,
                "total_revenue": 0
            }
        
        account_metrics = results[0]
        total_spend = account_metrics["total_spend"]
        total_revenue = account_metrics["total_revenue"]
        total_clicks = account_metrics["total_clicks"]
        total_impressions = account_metrics["total_impressions"]
        total_purchases = account_metrics["total_purchases"]
        
        # Calculate account-level metrics
        account_roas = total_revenue / total_spend if total_spend > 0 else 0
        account_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        account_conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
        
        return {
            "account_roas": account_roas,
            "account_ctr": account_ctr,
            "account_conversion_rate": account_conversion_rate,
            "total_spend": total_spend,
            "total_revenue": total_revenue
        }

    async def _calculate_account_level_roas_impact(
        self, 
        current_metrics: Dict, 
        optimized_metrics: Dict, 
        account_metrics: Dict
    ) -> float:
        """Calculate how much this ad's optimization will improve account-level ROAS."""
        # Get current account totals
        account_total_spend = account_metrics["total_spend"]
        account_total_revenue = account_metrics["total_revenue"]
        
        # Calculate new account totals after optimization
        new_total_spend = account_total_spend - current_metrics["spend"] + optimized_metrics["spend"]
        new_total_revenue = account_total_revenue - current_metrics["revenue"] + optimized_metrics["revenue"]
        
        # Calculate ROAS values
        current_account_roas = account_metrics["account_roas"]
        new_account_roas = new_total_revenue / new_total_spend if new_total_spend > 0 else 0
        
        # Calculate percentage improvement
        roas_improvement = ((new_account_roas - current_account_roas) / current_account_roas * 100) if current_account_roas > 0 else 0
        
        return round(roas_improvement, 2)

    async def generate_optimization_recommendations(
        self, 
        user_id: str, 
        target_roas_improvement: float = 10.0
    ) -> Dict[str, Any]:
        """Generate optimization-based recommendations to achieve target ROAS improvement."""
        logger.info(f"Starting ML optimization for user {user_id}, target improvement: {target_roas_improvement}%")
        
        # Get account-level metrics first
        account_metrics = await self._calculate_account_level_metrics(user_id)
        logger.info(f"Current account ROAS: {account_metrics['account_roas']:.2f}")        
        
        # Step 1: Get user's ad performance data
        ad_data = await self._get_user_ad_data(user_id)
        
        # Step 2: Check if we have sufficient data for ML optimization
        if len(ad_data) < 5:
            logger.info(f"Insufficient historical data for ML optimization. Found {len(ad_data)} ads. Attempting to collect fresh data from Facebook API.")
            
            # Try to collect fresh data from Facebook API
            fresh_data_collected = await self._collect_fresh_facebook_data(user_id)
            
            if fresh_data_collected:
                logger.info("Successfully collected fresh data from Facebook API. Retrying data retrieval.")
                # Retry getting user ad data after fresh collection
                ad_data = await self._get_user_ad_data(user_id)
                logger.info(f"After fresh data collection: Found {len(ad_data)} ads")
            else:
                logger.warning("Failed to collect fresh data from Facebook API")
        
        # Step 3: Final check - if still insufficient data, use fallback
        if len(ad_data) < 5:
            logger.warning(f"Still insufficient data for ML optimization after Facebook API collection. Found {len(ad_data)} ads.")
            return self._generate_fallback_recommendations(ad_data, target_roas_improvement)
        
        # Step 4: Train or update ML model
        await self._train_roas_prediction_model(user_id)
        
        if not self.model_trained:
            logger.error("Failed to train ML model")
            return self._generate_fallback_recommendations(ad_data, target_roas_improvement)
        
        # Step 5: Optimize each ad to achieve target ROAS improvement
        optimization_results = []
        
        logger.info(f"Starting optimization for {len(ad_data)} ads")
        
        for ad in ad_data:
            try:
                logger.info(f"Processing ad {ad['ad_id']} (ROAS: {ad['current_metrics']['roas']:.2f})")
                result = await self._optimize_ad_parameters(ad, target_roas_improvement, account_metrics)
                if result:
                    optimization_results.append(result)
                    logger.info(f"✅ Ad {ad['ad_id']} optimization successful")
                else:
                    logger.info(f"❌ Ad {ad['ad_id']} optimization skipped (insufficient improvement or errors)")
            except Exception as e:
                logger.error(f"Error optimizing ad {ad['ad_id']}: {str(e)}")
                continue
        
        logger.info(f"Optimization completed: {len(optimization_results)} out of {len(ad_data)} ads generated valid recommendations")
        
        # Step 6: Group recommendations by optimization strategy
        recommendations = await self._group_recommendations_by_strategy(optimization_results, user_id, target_roas_improvement)
        
        # Add account-level metrics to recommendations
        recommendations["account_metrics"] = {
            "current_roas": account_metrics["account_roas"],
            "current_ctr": account_metrics["account_ctr"],
            "current_conversion_rate": account_metrics["account_conversion_rate"],
            "total_monthly_spend": account_metrics["total_spend"],
            "total_monthly_revenue": account_metrics["total_revenue"]
        }
        
        # Calculate total account-level ROAS improvement if all optimizations are implemented
        total_new_spend = account_metrics["total_spend"]
        total_new_revenue = account_metrics["total_revenue"]
        
        for result in optimization_results:
            current_spend = result["parameter_changes"]["spend"]["current"]
            current_revenue = current_spend * result["current_roas"]
            optimized_spend = result["parameter_changes"]["spend"]["optimized"]
            optimized_revenue = optimized_spend * result["predicted_roas"]
            
            total_new_spend = total_new_spend - current_spend + optimized_spend
            total_new_revenue = total_new_revenue - current_revenue + optimized_revenue
        
        new_account_roas = total_new_revenue / total_new_spend if total_new_spend > 0 else 0
        total_account_roas_improvement = ((new_account_roas - account_metrics["account_roas"]) / account_metrics["account_roas"] * 100) if account_metrics["account_roas"] > 0 else 0
        
        recommendations["account_level_impact"] = {
            "current_account_roas": account_metrics["account_roas"],
            "predicted_account_roas": new_account_roas,
            "total_account_roas_improvement": round(total_account_roas_improvement, 2),
            "current_monthly_spend": account_metrics["total_spend"],
            "predicted_monthly_spend": total_new_spend,
            "current_monthly_revenue": account_metrics["total_revenue"],
            "predicted_monthly_revenue": total_new_revenue
        }
        
        # Step 7: Save recommendations to database
        try:
            batch_id = await self.storage_service.save_recommendations(
                user_id=user_id,
                optimization_results=recommendations,
                optimization_summary=recommendations.get("optimization_summary", {}),
                goal=recommendations.get("goal", f"Improve ROAS by {target_roas_improvement}%"),
                target_improvement=target_roas_improvement,
                ml_enabled=True
            )
            recommendations["batch_id"] = batch_id
            recommendations["generated_at"] = datetime.now().isoformat()
            logger.info(f"Saved recommendations to database with batch ID: {batch_id}")
        except Exception as e:
            logger.error(f"Failed to save recommendations to database: {str(e)}")
            recommendations["batch_id"] = f"temp_{int(datetime.now().timestamp())}"
            recommendations["generated_at"] = datetime.now().isoformat()
        
        logger.info(f"Final summary: {recommendations.get('optimization_summary', {}).get('total_ads_analyzed', 0)} ads analyzed, predicted account ROAS improvement: {total_account_roas_improvement:.2f}%")
        return recommendations
    
    async def _collect_fresh_facebook_data(self, user_id: str) -> bool:
        """
        Collect fresh data from Facebook API when insufficient historical data is available.
        
        Returns:
            bool: True if data collection was successful, False otherwise
        """
        try:
            logger.info(f"Starting fresh Facebook data collection for user {user_id}")
            
            # Get user's Facebook credentials
            credentials = await self.user_service.get_facebook_credentials(user_id)
            
            if not credentials or not credentials.get("access_token") or not credentials.get("account_id"):
                logger.warning(f"User {user_id} has no valid Facebook credentials for data collection")
                return False
            
            access_token = credentials["access_token"]
            account_id = credentials["account_id"]
            
            # Initialize Facebook service
            fb_service = FacebookAdService(access_token=access_token, account_id=account_id)
            
            # Collect data for the last 30 days to get sufficient data points
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            logger.info(f"Collecting Facebook data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Collect metrics using the existing Facebook service method
            metrics_data = await fb_service.collect_ad_metrics_for_range(
                user_id=user_id,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                time_increment=1  # Daily data
            )
            
            if not metrics_data:
                logger.warning(f"No metrics data collected from Facebook API for user {user_id}")
                return False
            
            # Store the collected data in the database
            db = get_database()
            
            # Insert metrics data into ad_metrics collection
            if metrics_data:
                # Ensure all documents have proper structure
                for metric in metrics_data:
                    # Ensure collected_at is a datetime object
                    if isinstance(metric.get("collected_at"), str):
                        try:
                            metric["collected_at"] = datetime.fromisoformat(metric["collected_at"])
                        except:
                            metric["collected_at"] = datetime.now()
                    elif not isinstance(metric.get("collected_at"), datetime):
                        metric["collected_at"] = datetime.now()
                
                # Insert the data
                result = await db.ad_metrics.insert_many(metrics_data)
                logger.info(f"Successfully stored {len(result.inserted_ids)} fresh metrics records for user {user_id}")
                
                return True
            else:
                logger.warning(f"No valid metrics data to store for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error collecting fresh Facebook data for user {user_id}: {str(e)}")
            return False
    
    async def _get_user_ad_data(self, user_id: str) -> List[Dict]:
        """Get comprehensive ad performance data for the user."""
        db = get_database()
        
        # STEP 1: First, get all ad_ids that have creative metadata in ad_analyses
        # This ensures we only work with ads that have creative analysis data
        ad_analyses = await db.ad_analyses.find({
            "user_id": user_id,
            "ad_analysis": {"$exists": True, "$ne": {}}
        }).to_list(length=1000)
        
        # Extract ad_ids and campaign_ids from analyses
        ad_ids_with_analysis = set()
        campaign_ids_with_analysis = set()
        
        for analysis in ad_analyses:
            if analysis.get("ad_id"):
                ad_ids_with_analysis.add(analysis.get("ad_id"))
            if analysis.get("campaign_id"):
                campaign_ids_with_analysis.add(analysis.get("campaign_id"))
        
        # If no ads with analyses found, return empty list
        if not ad_ids_with_analysis and not campaign_ids_with_analysis:
            logger.warning(f"No ads with creative analyses found for user {user_id}")
            return []
        
        logger.info(f"Found {len(ad_ids_with_analysis)} ad IDs and {len(campaign_ids_with_analysis)} campaign IDs with creative metadata")
        
        # STEP 2: Get last 60 days of data for better ML training
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # STEP 3: Now query ad_metrics but only for ads that have creative metadata
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "collected_at": {"$gte": start_date, "$lte": end_date},
                    "$or": [
                        {"ad_id": {"$in": list(ad_ids_with_analysis)}},
                        {"campaign_id": {"$in": list(campaign_ids_with_analysis)}}
                    ]
                }
            },
            {
                "$group": {
                    "_id": "$ad_id",
                    "ad_name": {"$first": "$ad_name"},
                    "campaign_id": {"$first": "$campaign_id"},
                    "video_id": {"$first": "$video_id"},
                    "avg_spend": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.spend", 0]}}},
                    "avg_revenue": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.purchases_value", 0]}}},
                    "avg_clicks": {"$avg": {"$toInt": {"$ifNull": ["$additional_metrics.clicks", 0]}}},
                    "avg_impressions": {"$avg": {"$toInt": {"$ifNull": ["$additional_metrics.impressions", 0]}}},
                    "avg_purchases": {"$avg": {"$toInt": {"$ifNull": ["$purchases", 0]}}},
                    "avg_ctr": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.ctr", 0]}}},
                    "avg_cpc": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.cpc", 0]}}},
                    "avg_cpm": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.cpm", 0]}}},
                    "avg_roas": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.roas", 0]}}},
                    "data_points": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "data_points": {"$gte": 3},  # At least 3 data points
                    "avg_spend": {"$gt": 10}     # Meaningful spend
                }
            }
        ]
        
        results = await db.ad_metrics.aggregate(pipeline).to_list(length=1000)
        logger.info(f"Retrieved {len(results)} ads with metrics that also have creative metadata")
        
        # STEP 4: Check if there are any ads in ad_analyses that weren't found in ad_metrics
        found_ad_ids = {result["_id"] for result in results}
        found_campaign_ids = {result.get("campaign_id") for result in results if result.get("campaign_id")}
        
        missing_ad_ids = ad_ids_with_analysis - found_ad_ids
        missing_campaign_ids = campaign_ids_with_analysis - found_campaign_ids
        
        if missing_ad_ids:
            logger.info(f"Found {len(missing_ad_ids)} ad IDs and {len(missing_campaign_ids)} campaign IDs with creative metadata but no metrics")
            
            # STEP 5: Try to fetch fresh metrics from Facebook API for these missing ads
            # Get user's Facebook credentials
            from app.services.user_service import UserService
            from app.services.facebook_service import FacebookAdService
            
            user_service = UserService()
            credentials = await user_service.get_facebook_credentials(user_id)
            
            if credentials and credentials.get("access_token") and credentials.get("account_id"):
                logger.info(f"Fetching fresh metrics from Facebook API for {len(missing_ad_ids)} missing ads")
                
                # Initialize Facebook service
                fb_service = FacebookAdService(
                    access_token=credentials["access_token"], 
                    account_id=credentials["account_id"]
                )
                
                # Collect metrics for missing ads - only include ad IDs, not campaign IDs
                missing_ids_list = list(missing_ad_ids)  # Don't include campaign IDs as they can't be used with ad-level metrics
                
                # Use a 30-day window for metrics collection
                fb_end_date = end_date
                fb_start_date = fb_end_date - timedelta(days=30)
                
                try:
                    # Collect metrics for specific ads
                    metrics_data = await fb_service.collect_ad_metrics_for_specific_ads(
                        user_id=user_id,
                        ad_ids=missing_ids_list,
                        start_date=fb_start_date.strftime('%Y-%m-%d'),
                        end_date=fb_end_date.strftime('%Y-%m-%d')
                    )
                    
                    if metrics_data:
                        logger.info(f"Successfully fetched {len(metrics_data)} metrics records from Facebook API")
                        
                        # Store the collected data in the database
                        for metric in metrics_data:
                            # Ensure collected_at is a datetime object
                            if isinstance(metric.get("collected_at"), str):
                                try:
                                    metric["collected_at"] = datetime.fromisoformat(metric["collected_at"])
                                except:
                                    metric["collected_at"] = datetime.now()
                            elif not isinstance(metric.get("collected_at"), datetime):
                                metric["collected_at"] = datetime.now()
                        
                        # Insert the data
                        result = await db.ad_metrics.insert_many(metrics_data)
                        logger.info(f"Stored {len(result.inserted_ids)} fresh metrics records for missing ads")
                        
                        # Process newly fetched metrics
                        for ad_id in missing_ids_list:
                            # Find metrics for this specific ad
                            ad_metrics = [m for m in metrics_data if m.get("ad_id") == ad_id or m.get("campaign_id") == ad_id]
                            
                            if ad_metrics:
                                # Calculate averages manually for this ad
                                ad_data = {
                                    "_id": ad_metrics[0].get("ad_id"),
                                    "ad_name": ad_metrics[0].get("ad_name", f"Ad {ad_metrics[0].get('ad_id')}"),
                                    "campaign_id": ad_metrics[0].get("campaign_id"),
                                    "video_id": ad_metrics[0].get("video_id"),
                                    "data_points": len(ad_metrics)
                                }
                                
                                # Calculate averages for metrics
                                spend_values = [float(m.get("additional_metrics", {}).get("spend", 0)) for m in ad_metrics]
                                revenue_values = [float(m.get("additional_metrics", {}).get("purchases_value", 0)) for m in ad_metrics]
                                clicks_values = [int(m.get("additional_metrics", {}).get("clicks", 0)) for m in ad_metrics]
                                impressions_values = [int(m.get("additional_metrics", {}).get("impressions", 0)) for m in ad_metrics]
                                purchases_values = [int(m.get("purchases", 0)) for m in ad_metrics]
                                ctr_values = [float(m.get("additional_metrics", {}).get("ctr", 0)) for m in ad_metrics]
                                cpc_values = [float(m.get("additional_metrics", {}).get("cpc", 0)) for m in ad_metrics]
                                cpm_values = [float(m.get("additional_metrics", {}).get("cpm", 0)) for m in ad_metrics]
                                
                                # Calculate averages
                                ad_data["avg_spend"] = sum(spend_values) / len(spend_values) if spend_values else 0
                                ad_data["avg_revenue"] = sum(revenue_values) / len(revenue_values) if revenue_values else 0
                                ad_data["avg_clicks"] = sum(clicks_values) / len(clicks_values) if clicks_values else 0
                                ad_data["avg_impressions"] = sum(impressions_values) / len(impressions_values) if impressions_values else 0
                                ad_data["avg_purchases"] = sum(purchases_values) / len(purchases_values) if purchases_values else 0
                                ad_data["avg_ctr"] = sum(ctr_values) / len(ctr_values) if ctr_values else 0
                                ad_data["avg_cpc"] = sum(cpc_values) / len(cpc_values) if cpc_values else 0
                                ad_data["avg_cpm"] = sum(cpm_values) / len(cpm_values) if cpm_values else 0
                                
                                # Calculate ROAS
                                ad_data["avg_roas"] = ad_data["avg_revenue"] / ad_data["avg_spend"] if ad_data["avg_spend"] > 0 else 0
                                
                                # Add to results if it meets minimum criteria
                                if ad_data["data_points"] >= 1:
                                    results.append(ad_data)
                                    logger.info(f"Added ad {ad_data['_id']} with {ad_data['data_points']} fresh data points from Facebook API")
                
                except Exception as e:
                    logger.error(f"Error fetching metrics from Facebook API: {str(e)}")
                    
                    # Fallback: Try to find any existing metrics for missing ads with relaxed criteria
                    await self._try_find_existing_metrics_for_missing_ads(
                        db, user_id, missing_ids_list, start_date, end_date, results
                    )
            else:
                logger.warning(f"No valid Facebook credentials found for user {user_id}, can't fetch fresh metrics")
                
                # Fallback: Try to find any existing metrics for missing ads with relaxed criteria
                await self._try_find_existing_metrics_for_missing_ads(
                    db, user_id, list(missing_ad_ids) + list(missing_campaign_ids), 
                    start_date, end_date, results
                )
        
        # STEP 6: Create a map of ad_id/campaign_id to creative metadata for quick lookup
        creative_map = {}
        for analysis in ad_analyses:
            # Try multiple ID fields for mapping
            ad_id = analysis.get("ad_id")
            campaign_id = analysis.get("campaign_id")
            
            if ad_id and analysis.get("ad_analysis"):
                creative_map[ad_id] = analysis["ad_analysis"]
            if campaign_id and analysis.get("ad_analysis"):
                creative_map[campaign_id] = analysis["ad_analysis"]
        
        # STEP 7: Format data for ML
        formatted_data = []
        for result in results:
            ad_id = result["_id"]
            campaign_id = result.get("campaign_id")
            
            # Calculate derived metrics
            spend = float(result.get("avg_spend", 0))
            revenue = float(result.get("avg_revenue", 0))
            clicks = int(result.get("avg_clicks", 0))
            impressions = int(result.get("avg_impressions", 0))
            purchases = int(result.get("avg_purchases", 0))
            
            # Check if this is an ad from ad_analyses with minimal metrics data
            is_from_ad_analyses = ad_id in ad_ids_with_analysis or campaign_id in campaign_ids_with_analysis
            
            # For regular ads, ensure we have meaningful data
            # For ads from ad_analyses, be more lenient to ensure we try to optimize all ads with creative metadata
            if (spend <= 0 or impressions <= 0) and not is_from_ad_analyses:
                continue
                
            # For ads from ad_analyses with no metrics, set minimal default values to allow optimization attempt
            if spend <= 0 and is_from_ad_analyses:
                spend = 1.0  # Minimal spend to allow optimization
                logger.info(f"Setting minimal default spend for ad {ad_id} from ad_analyses with no metrics data")
                
            if impressions <= 0 and is_from_ad_analyses:
                impressions = 100  # Minimal impressions to allow optimization
                logger.info(f"Setting minimal default impressions for ad {ad_id} from ad_analyses with no metrics data")
                
            roas = revenue / spend if spend > 0 else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0  # As percentage
            cpc = float(result.get("avg_cpc", 0))
            cpm = float(result.get("avg_cpm", 0))
            
            # Get creative metadata, first try ad_id then campaign_id
            creative_metadata = creative_map.get(ad_id, creative_map.get(campaign_id, {}))
            
            # Only include ads that have creative metadata
            if not creative_metadata:
                logger.warning(f"Skipping ad {ad_id} - no creative metadata found despite being in initial list")
                continue
            
            formatted_data.append({
                "ad_id": ad_id,
                "ad_name": result.get("ad_name", f"Ad {ad_id}"),
                "campaign_id": campaign_id,
                "video_id": result.get("video_id"),
                "current_metrics": {
                    "spend": spend,
                    "revenue": revenue,
                    "clicks": clicks,
                    "impressions": impressions,
                    "purchases": purchases,
                    "ctr": ctr,
                    "cpc": cpc,
                    "cpm": cpm,
                    "roas": roas
                },
                "creative_metadata": creative_metadata,
                "data_points": result.get("data_points", 0)
            })
        
        logger.info(f"Final result: {len(formatted_data)} ads with both sufficient metrics data and creative metadata")
        
        # Log ad data quality for debugging
        if len(formatted_data) == 0:
            logger.warning(f"No ads found for user {user_id} that meet all criteria: has creative metadata, spend > 0, impressions > 0, data_points >= 3, avg_spend > 10")
        else:
            avg_roas = sum(ad['current_metrics']['roas'] for ad in formatted_data) / len(formatted_data)
            logger.info(f"Ad data summary: {len(formatted_data)} ads, average ROAS: {avg_roas:.2f}")
            
        return formatted_data
        
    async def _try_find_existing_metrics_for_missing_ads(
        self, 
        db, 
        user_id: str, 
        missing_ids_list: List[str], 
        start_date: datetime, 
        end_date: datetime, 
        results: List[Dict]
    ):
        """Fallback method to find any existing metrics for missing ads with relaxed criteria."""
        logger.info(f"Trying to find any existing metrics for {len(missing_ids_list)} missing ads with relaxed criteria")
        
        for missing_id in missing_ids_list:
            # Try to find any metrics for this ad, even with less strict criteria
            single_ad_metrics = await db.ad_metrics.find({
                "user_id": user_id,
                "$or": [
                    {"ad_id": missing_id},
                    {"campaign_id": missing_id}
                ],
                "collected_at": {"$gte": start_date, "$lte": end_date}
            }).to_list(length=100)
            
            if single_ad_metrics:
                # Calculate averages manually for this ad
                ad_data = {
                    "_id": single_ad_metrics[0].get("ad_id"),
                    "ad_name": single_ad_metrics[0].get("ad_name", f"Ad {single_ad_metrics[0].get('ad_id')}"),
                    "campaign_id": single_ad_metrics[0].get("campaign_id"),
                    "video_id": single_ad_metrics[0].get("video_id"),
                    "data_points": len(single_ad_metrics)
                }
                
                # Calculate averages for metrics
                spend_values = [float(m.get("additional_metrics", {}).get("spend", 0)) for m in single_ad_metrics]
                revenue_values = [float(m.get("additional_metrics", {}).get("purchases_value", 0)) for m in single_ad_metrics]
                clicks_values = [int(m.get("additional_metrics", {}).get("clicks", 0)) for m in single_ad_metrics]
                impressions_values = [int(m.get("additional_metrics", {}).get("impressions", 0)) for m in single_ad_metrics]
                purchases_values = [int(m.get("purchases", 0)) for m in single_ad_metrics]
                ctr_values = [float(m.get("additional_metrics", {}).get("ctr", 0)) for m in single_ad_metrics]
                cpc_values = [float(m.get("additional_metrics", {}).get("cpc", 0)) for m in single_ad_metrics]
                cpm_values = [float(m.get("additional_metrics", {}).get("cpm", 0)) for m in single_ad_metrics]
                
                # Calculate averages
                ad_data["avg_spend"] = sum(spend_values) / len(spend_values) if spend_values else 0
                ad_data["avg_revenue"] = sum(revenue_values) / len(revenue_values) if revenue_values else 0
                ad_data["avg_clicks"] = sum(clicks_values) / len(clicks_values) if clicks_values else 0
                ad_data["avg_impressions"] = sum(impressions_values) / len(impressions_values) if impressions_values else 0
                ad_data["avg_purchases"] = sum(purchases_values) / len(purchases_values) if purchases_values else 0
                ad_data["avg_ctr"] = sum(ctr_values) / len(ctr_values) if ctr_values else 0
                ad_data["avg_cpc"] = sum(cpc_values) / len(cpc_values) if cpc_values else 0
                ad_data["avg_cpm"] = sum(cpm_values) / len(cpm_values) if cpm_values else 0
                
                # Calculate ROAS
                ad_data["avg_roas"] = ad_data["avg_revenue"] / ad_data["avg_spend"] if ad_data["avg_spend"] > 0 else 0
                
                # Add all ads with any data
                results.append(ad_data)
                logger.info(f"Added ad {ad_data['_id']} with {ad_data['data_points']} existing data points with relaxed criteria")
    
    async def _train_roas_prediction_model(self, user_id: str) -> bool:
        """Train ML model to predict ROAS based on performance metrics."""
        try:
            # Get training data from database (more historical data)
            db = get_database()
            
            # Get last 90 days for training
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            
            # Get individual data points (not aggregated) for better training
            # Removed restrictive minimum thresholds to include all valid data
            training_data = await db.ad_metrics.find({
                "user_id": user_id,
                "collected_at": {"$gte": start_date, "$lte": end_date},
                "additional_metrics.spend": {"$gt": 0},      # Only exclude zero spend
                "additional_metrics.impressions": {"$gt": 0}  # Only exclude zero impressions
            }).to_list(length=5000)
            
            if len(training_data) < 20:
                logger.warning(f"Insufficient training data: {len(training_data)} records")
                return False

            # Run the CPU-intensive training in a thread pool to avoid blocking the event loop
            return await asyncio.to_thread(self._train_model_sync, training_data, user_id)
            
        except Exception as e:
            logger.error(f"Error training ROAS prediction model: {str(e)}")
            return False

    def _train_model_sync(self, training_data: List[Dict], user_id: str) -> bool:
        """Synchronous ML model training that runs in a thread pool"""
        try:
            # Prepare features and target
            features = []
            targets = []
            
            for record in training_data:
                metrics = record.get("additional_metrics", {})
                
                spend = float(metrics.get("spend", 0))
                revenue = float(metrics.get("purchases_value", 0))
                clicks = int(metrics.get("clicks", 0))
                impressions = int(metrics.get("impressions", 0))
                purchases = int(record.get("purchases", 0))
                
                if spend <= 0 or impressions <= 0:
                    continue
                
                # Calculate derived metrics
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cpc = float(metrics.get("cpc", 0))
                cpm = float(metrics.get("cpm", 0))
                roas = revenue / spend if spend > 0 else 0
                
                # Features: [spend, ctr, cpc, cpm, clicks, impressions, purchases]
                features.append([spend, ctr, cpc, cpm, clicks, impressions, purchases])
                targets.append(roas)
            
            if len(features) < 20:
                logger.warning(f"Insufficient valid training samples: {len(features)}")
                return False
            
            # Convert to numpy arrays
            X = np.array(features)
            y = np.array(targets)
            
            # Remove outliers (ROAS > 20 or < 0)
            valid_indices = (y >= 0) & (y <= 20)
            X = X[valid_indices]
            y = y[valid_indices]
            
            if len(X) < 15:
                logger.warning("Too few samples after outlier removal")
                return False
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train ensemble model with balanced complexity for good performance
            rf_model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10, n_jobs=1)
            gb_model = GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=6)
            
            rf_model.fit(X_train_scaled, y_train)
            gb_model.fit(X_train_scaled, y_train)
            
            # Evaluate models
            rf_pred = rf_model.predict(X_test_scaled)
            gb_pred = gb_model.predict(X_test_scaled)
            
            rf_r2 = r2_score(y_test, rf_pred)
            gb_r2 = r2_score(y_test, gb_pred)
            
            # Choose best model
            if rf_r2 > gb_r2:
                self.model = rf_model
                self.feature_importance = dict(zip(self.feature_names, rf_model.feature_importances_))
                logger.info(f"Selected RandomForest model with R² = {rf_r2:.3f}")
            else:
                self.model = gb_model
                self.feature_importance = dict(zip(self.feature_names, gb_model.feature_importances_))
                logger.info(f"Selected GradientBoosting model with R² = {gb_r2:.3f}")
            
            self.model_trained = True
            
            # Log feature importance
            logger.info(f"Feature importance: {self.feature_importance}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in sync model training: {str(e)}")
            return False

    async def _optimize_ad_parameters(
        self, 
        ad_data: Dict, 
        target_improvement: float,
        account_metrics: Dict
    ) -> Optional[Dict]:
        """Optimize ad parameters to find maximum achievable ROAS improvement."""
        try:
            current_metrics = ad_data["current_metrics"]
            current_roas = current_metrics["roas"]
            
            if current_roas <= 0:
                logger.warning(f"Ad {ad_data['ad_id']} has zero ROAS, skipping optimization")
                return None

            # Run the CPU-intensive optimization in a thread pool to avoid blocking the event loop
            optimization_result = await asyncio.to_thread(
                self._optimize_parameters_sync, 
                ad_data,
                current_roas, 
                ad_data['ad_id']
            )
            
            if optimization_result:
                # Calculate predicted revenue based on optimized parameters
                optimized_metrics = {
                    "spend": optimization_result["parameter_changes"]["spend"]["optimized"],
                    "revenue": optimization_result["predicted_roas"] * optimization_result["parameter_changes"]["spend"]["optimized"]
                }
                
                # Calculate account-level ROAS impact
                account_roas_impact = await self._calculate_account_level_roas_impact(
                    current_metrics={"spend": current_metrics["spend"], "revenue": current_metrics["revenue"]},
                    optimized_metrics=optimized_metrics,
                    account_metrics=account_metrics
                )
                
                optimization_result["account_level_roas_impact"] = account_roas_impact
                
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing ad {ad_data.get('ad_id', 'unknown')}: {str(e)}")
            return None

    def _optimize_parameters_sync(self, ad_data: Dict, current_roas: float, ad_id: str) -> Optional[Dict]:
        """Synchronous parameter optimization that runs in a thread pool"""
        try:
            current_metrics = ad_data["current_metrics"]
            
            # Validate that all required metrics are present
            required_metrics = ['spend', 'ctr', 'cpc', 'cpm', 'clicks', 'impressions', 'purchases']
            missing_metrics = [metric for metric in required_metrics if metric not in current_metrics]
            
            if missing_metrics:
                logger.error(f"Ad {ad_id} is missing required metrics: {missing_metrics}")
                # Set default values for missing metrics
                for metric in missing_metrics:
                    if metric == 'spend':
                        current_metrics[metric] = 1.0
                    elif metric in ['ctr', 'cpc', 'cpm']:
                        current_metrics[metric] = 0.1
                    elif metric == 'clicks':
                        current_metrics[metric] = 10
                    elif metric == 'impressions':
                        current_metrics[metric] = 1000
                    elif metric == 'purchases':
                        current_metrics[metric] = 1
                logger.info(f"Set default values for missing metrics in ad {ad_id}")
            
            # Define optimization bounds (realistic, tighter ranges to prevent extreme changes)
            bounds = [
                (max(0.1, current_metrics["spend"] * 0.7), current_metrics["spend"] * 2.0),      # spend: 70% to 200% (tighter control)
                (max(0.1, current_metrics["ctr"] * 0.6), current_metrics["ctr"] * 2.5),  # ctr: 60% to 250% (more realistic)
                (max(0.01, current_metrics["cpc"] * 0.5), current_metrics["cpc"] * 1.8), # cpc: 50% to 180% (prevent extreme cost changes)
                (max(0.1, current_metrics["cpm"] * 0.5), current_metrics["cpm"] * 1.8),  # cpm: 50% to 180% (consistent with cpc)
                (max(1, current_metrics["clicks"] * 0.6), current_metrics["clicks"] * 2.5), # clicks: 60% to 250% (align with ctr)
                (max(100, current_metrics["impressions"] * 0.7), current_metrics["impressions"] * 2.0), # impressions: 70% to 200% (align with spend)
                (max(0, current_metrics["purchases"] * 0.6), current_metrics["purchases"] * 2.5) # purchases: 60% to 250% (realistic conversion changes)
            ]
            
            # NEW APPROACH: Maximize ROAS instead of targeting a specific improvement
            def objective(params):
                try:
                    # Predict ROAS with new parameters
                    params_scaled = self.scaler.transform([params])
                    predicted_roas = self.model.predict(params_scaled)[0]
                    
                    # Penalty for unrealistic parameter combinations
                    spend, ctr, cpc, cpm, clicks, impressions, purchases = params
                    
                    # Consistency checks (soft constraints)
                    expected_clicks = (impressions * ctr / 100)
                    expected_spend = clicks * cpc
                    
                    # Penalty for inconsistent metrics (reduced penalties)
                    click_penalty = abs(clicks - expected_clicks) / max(clicks, expected_clicks, 1) * 2
                    spend_penalty = abs(spend - expected_spend) / max(spend, expected_spend, 1) * 1
                    
                    # Penalty for extreme changes (reduced threshold due to tighter bounds)
                    extreme_change_penalty = 0
                    
                    # Get current metric values in the same order as feature_names
                    current_values = []
                    for feature in self.feature_names:
                        if feature in current_metrics:
                            current_values.append(current_metrics[feature])
                        else:
                            # If a feature is missing, use the optimized value (no penalty)
                            logger.warning(f"Missing feature '{feature}' in current_metrics for ad {ad_id}")
                            # Find the index of this feature
                            feature_idx = self.feature_names.index(feature)
                            current_values.append(params[feature_idx])
                    
                    # Now compare with proper error handling
                    for i, (param_val, current_val) in enumerate(zip(params, current_values)):
                        if current_val > 0:
                            change_ratio = abs(param_val - current_val) / current_val
                            if change_ratio > 1.5:  # More than 150% change
                                extreme_change_penalty += change_ratio * 0.3
                    
                    # MAXIMIZE ROAS (minimize negative ROAS)
                    return -predicted_roas + click_penalty + spend_penalty + extreme_change_penalty
                    
                except Exception as e:
                    logger.error(f"Error in objective function for ad {ad_id}: {str(e)}")
                    return 1000  # High penalty for invalid parameters
            
            # Run optimization with balanced complexity for good results without hanging
            result = differential_evolution(
                objective, 
                bounds, 
                seed=42, 
                maxiter=100,  # Increased iterations for better optimization
                popsize=15,   # Balanced population size
                atol=1e-3,    # Better tolerance for quality results
                tol=1e-3,     # Better tolerance for quality results
                workers=1     # Single worker to prevent thread issues
            )
            
            # Extract optimized parameters regardless of convergence
            optimized_params = result.x
            optimized_metrics = dict(zip(self.feature_names, optimized_params))
            
            # Predict ROAS with optimized parameters
            params_scaled = self.scaler.transform([optimized_params])
            predicted_roas = self.model.predict(params_scaled)[0]
            
            # Calculate actual improvement achieved
            improvement_achieved = ((predicted_roas - current_roas) / current_roas * 100)
            
            # Lower threshold to capture more optimization opportunities  
            # Accept any positive improvement (minimum 1% to avoid noise, lowered from 2%)
            if improvement_achieved < 1.0:
                logger.info(f"Ad {ad_id}: Minimal improvement possible ({improvement_achieved:.1f}%). Ad may already be optimized.")
                return None
            
            # Calculate parameter changes
            parameter_changes = {}
            for param, current_val in current_metrics.items():
                if param in optimized_metrics:
                    new_val = optimized_metrics[param]
                    change_pct = ((new_val - current_val) / current_val * 100) if current_val > 0 else 0
                    
                    # Lower threshold to 2% for more parameter changes (was 3%)
                    if abs(change_pct) > 2:  
                        parameter_changes[param] = {
                            "current": current_val,
                            "optimized": new_val,
                            "change_percent": change_pct,
                            "change_direction": "increase" if change_pct > 0 else "decrease"
                        }
            
            # Log parameter changes for debugging
            logger.info(f"Ad {ad_id}: Found {len(parameter_changes)} parameter changes above 2% threshold")
            if parameter_changes:
                logger.info(f"Ad {ad_id}: Parameter changes: {list(parameter_changes.keys())}")
            
            # Create optimization result with proper status tracking
            optimization_result = {
                "ad_id": ad_id,
                "ad_name": ad_data.get("ad_name", f"Ad {ad_id}"),
                "current_roas": current_roas,
                "predicted_roas": predicted_roas,
                "improvement_percent": improvement_achieved,
                "parameter_changes": parameter_changes,
                "optimization_confidence": min(1.0, max(0.3, result.fun if hasattr(result, 'fun') else 0.7)),
                "feasible": True,
                "creative_metadata": ad_data.get("creative_metadata", {}),
                "campaign_id": ad_data.get("campaign_id"),
                "video_id": ad_data.get("video_id"),
                "optimization_success": True,
                "optimization_status": "converged" if (hasattr(result, 'success') and result.success) else "max_iterations",
                "optimization_message": getattr(result, 'message', 'Optimization completed')
            }
            
            logger.info(f"Ad {ad_id}: Optimization achieved {improvement_achieved:.1f}% ROAS improvement with {len(parameter_changes)} parameter changes")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error in sync parameter optimization for ad {ad_id}: {str(e)}")
            return None
    
    async def _group_recommendations_by_strategy(
        self, 
        optimization_results: List[Dict], 
        user_id: str,
        target_improvement: float = 10.0
    ) -> Dict[str, Any]:
        """Group optimization results into strategic recommendations based on all parameter changes."""
        # Group by all parameter optimization strategies (not just primary)
        ctr_improvements = []
        spend_optimizations = []
        efficiency_improvements = []  # CPC/CPM improvements
        conversion_improvements = []  # Purchase rate improvements
        
        # Track total account-level impact
        total_account_roas_impact = 0
        
        for result in optimization_results:
            parameter_changes = result["parameter_changes"]
            
            # Add account-level impact to total
            total_account_roas_impact += result.get("account_level_roas_impact", 0)
            
            # Check for CTR improvements (increase direction)
            if "ctr" in parameter_changes and parameter_changes["ctr"]["change_direction"] == "increase":
                ctr_improvements.append(result)
            
            # Check for spend optimizations (both directions - increase and decrease)
            if "spend" in parameter_changes:
                spend_optimizations.append(result)
            
            # Check for efficiency improvements (CPC/CPM with increase direction)
            if any(param in parameter_changes and parameter_changes[param]["change_direction"] == "increase" 
                   for param in ["cpc", "cpm"]):
                efficiency_improvements.append(result)
            
            # Check for conversion improvements (purchases/clicks with increase direction)
            if any(param in parameter_changes and parameter_changes[param]["change_direction"] == "increase" 
                   for param in ["purchases", "clicks"]):
                conversion_improvements.append(result)
        
        # Calculate optimization statistics
        if optimization_results:
            successful_optimizations = [r for r in optimization_results if r.get("optimization_success")]
            convergence_rate = len([r for r in optimization_results if r.get("optimization_status") == "converged"]) / len(optimization_results) * 100
            avg_improvement = np.mean([r["improvement_percent"] for r in optimization_results])
            max_improvement = max([r["improvement_percent"] for r in optimization_results])
            min_improvement = min([r["improvement_percent"] for r in optimization_results])
        else:
            convergence_rate = 0
            avg_improvement = 0
            max_improvement = 0
            min_improvement = 0
        
        # Generate detailed recommendations for each strategy
        recommendations = {
            "goal": f"Maximize ROAS improvement through adaptive ML optimization (target: {target_improvement}% improvement where achievable)",
            "optimization_summary": {
                "total_ads_analyzed": len(optimization_results),
                "successful_optimizations": len(optimization_results),
                "convergence_rate": round(convergence_rate, 1),
                "average_predicted_improvement": round(avg_improvement, 2),
                "max_improvement_achieved": round(max_improvement, 2),
                "min_improvement_achieved": round(min_improvement, 2),
                "total_account_roas_impact": round(total_account_roas_impact, 2),
                "ctr_improvement_opportunities": len(ctr_improvements),
                "spend_optimization_opportunities": len(spend_optimizations),
                "efficiency_improvement_opportunities": len(efficiency_improvements),
                "conversion_improvement_opportunities": len(conversion_improvements)
            }
        }
        
        # Generate CTR improvement recommendations
        if ctr_improvements:
            recommendations["ctr_improvements"] = await self._generate_ctr_recommendations(ctr_improvements, user_id)
        
        # Generate spend optimization recommendations
        if spend_optimizations:
            recommendations["spend_optimizations"] = await self._generate_spend_recommendations(spend_optimizations, user_id)
        
        # Generate efficiency improvement recommendations
        if efficiency_improvements:
            recommendations["efficiency_improvements"] = await self._generate_efficiency_recommendations(efficiency_improvements, user_id)
        
        # Generate conversion improvement recommendations
        if conversion_improvements:
            recommendations["conversion_improvements"] = await self._generate_conversion_recommendations(conversion_improvements, user_id)
        
        return recommendations
    

    
    async def _generate_ctr_recommendations(self, ctr_improvements: List[Dict], user_id: str) -> Dict:
        """Generate CTR improvement recommendations with creative optimization."""
        recommendations = []
        
        # Find benchmark ads with high CTR for creative analysis
        benchmark_ads = await self._find_benchmark_ads(user_id, "ctr")
        
        for ad_result in ctr_improvements:
            ctr_change = ad_result["parameter_changes"].get("ctr", {})
            current_ctr = ctr_change.get("current", 0)
            target_ctr = ctr_change.get("optimized", 0)
            
            # Get creative metadata with fallback for missing data
            current_creative = ad_result.get("creative_metadata", {})
            if not current_creative:
                current_creative = {
                    "hook": "Unknown",
                    "tone": "Unknown", 
                    "visual": "Unknown",
                    "power_phrases": "Unknown"
                }
            
            
            # Find similar high-CTR ad for creative inspiration
            benchmark_creative = await self._find_similar_high_performing_creative(
                current_creative, 
                benchmark_ads, 
                "ctr"
            )
            
            # Generate AI-powered creative recommendations
            ai_creative_suggestions = await self._generate_ai_creative_optimization(
                current_creative,
                benchmark_creative["creative"] if isinstance(benchmark_creative, dict) and "creative" in benchmark_creative else benchmark_creative,
                f"increase CTR from {current_ctr:.2f}% to {target_ctr:.2f}%"
            )
            
            # Get spend changes for context (CTR improvements often affect spend efficiency)
            spend_change = ad_result["parameter_changes"].get("spend", {})
            spend_insight = ""
            if spend_change:
                if spend_change["change_direction"] == "decrease":
                    spend_insight = f"Bonus: Spend can be reduced by {abs(spend_change['change_percent']):.1f}% (${spend_change['current']:.2f} → ${spend_change['optimized']:.2f}) while improving CTR"
                else:
                    spend_insight = f"Note: Achieving this CTR improvement may require increasing spend by {spend_change['change_percent']:.1f}% (${spend_change['current']:.2f} → ${spend_change['optimized']:.2f})"
            
            recommendations.append({
                "ad_id": ad_result["ad_id"],
                "ad_name": ad_result.get("ad_name", f"Ad {ad_result['ad_id']}"),
                "optimization_goal": f"Increase CTR by {ctr_change.get('change_percent', 0):.1f}%",
                "current_performance": {
                    "ctr": current_ctr,
                    "roas": ad_result["current_roas"],
                    "spend": spend_change.get("current", 0)
                },
                "target_performance": {
                    "ctr": target_ctr,
                    "predicted_roas": ad_result["predicted_roas"],
                    "spend": spend_change.get("optimized", spend_change.get("current", 0))
                },
                "spend_insight": spend_insight, # Include all changes                
                "current_roas": ad_result["current_roas"],
                "predicted_roas": ad_result["predicted_roas"],
                "current_creative": current_creative,
                "benchmark_creative": benchmark_creative.get("creative", {}) if isinstance(benchmark_creative, dict) else benchmark_creative,
                "benchmark_metrics": benchmark_creative.get("metrics", {}) if isinstance(benchmark_creative, dict) else {},
                "ai_optimized_creative": ai_creative_suggestions,
                "implementation_strategy": self._generate_ctr_implementation_strategy(ctr_change),
                "expected_roas_improvement": f"{ad_result['improvement_percent']:.1f}%",
                "account_level_roas_impact": f"{ad_result.get('account_level_roas_impact', 0):.2f}%"
            })
        
        return {
            "strategy": "Increase CTR through Better Creatives",
            "description": f"Optimize creative elements to improve click-through rates for {len(recommendations)} ads",
            "total_ads": len(recommendations),
            "average_ctr_improvement_needed": np.mean([r["target_performance"]["ctr"] - r["current_performance"]["ctr"] for r in recommendations]),
            "recommendations": recommendations
        }
    
    async def _generate_spend_recommendations(self, spend_optimizations: List[Dict], user_id: str) -> Dict:
        """Generate spend optimization recommendations with scaling/reducing strategies."""
        scale_up = []
        scale_down = []
        
        for ad_result in spend_optimizations:
            spend_change = ad_result["parameter_changes"].get("spend", {})
            change_direction = spend_change.get("change_direction", "")
            
            if change_direction == "increase":
                scale_up.append(ad_result)
            else:
                scale_down.append(ad_result)
        
        recommendations = {
            "strategy": "Optimize Ad Spend Allocation",
            "description": f"Adjust spending levels for {len(spend_optimizations)} ads to maximize ROAS",
            "scale_up_opportunities": len(scale_up),
            "scale_down_opportunities": len(scale_down),
            "recommendations": []
        }
        
        # Generate scale up recommendations
        for ad_result in scale_up:
            spend_change = ad_result["parameter_changes"]["spend"]
            current_spend = spend_change["current"]
            target_spend = spend_change["optimized"]
            
            # Find proof from similar successful scaling
            scaling_proof = await self._find_scaling_proof(user_id, current_spend, target_spend)
            
            # Find benchmark ads for spend
            benchmark_ads = await self._find_benchmark_ads(user_id, "spend")
            benchmark_data = {}
            if benchmark_ads:
                best_benchmark = benchmark_ads[0]
                benchmark_data = {
                    "ad_id": best_benchmark.get("ad_id", ""),
                    "ad_name": best_benchmark.get("ad_name", ""),
                    "metrics": {
                        "spend": best_benchmark.get("additional_metrics", {}).get("spend", 0),
                        "roas": best_benchmark.get("additional_metrics", {}).get("roas", 0),
                        "ctr": best_benchmark.get("additional_metrics", {}).get("ctr", 0),
                        "cpc": best_benchmark.get("additional_metrics", {}).get("cpc", 0),
                        "cpm": best_benchmark.get("additional_metrics", {}).get("cpm", 0)
                    }
                }
            
            recommendations["recommendations"].append({
                "ad_id": ad_result["ad_id"],
                "ad_name": ad_result["ad_name"],
                "action": "Scale Up",
                "current_daily_spend": f"${current_spend:.2f}",
                "recommended_daily_spend": f"${target_spend:.2f}",
                "increase_percentage": f"{spend_change['change_percent']:.1f}%",
                "reasoning": f"High ROAS of {ad_result['current_roas']:.2f} indicates strong market demand",
                "scaling_proof": scaling_proof,
                "benchmark_metrics": benchmark_data,
                "current_roas": ad_result["current_roas"],
                "predicted_roas": ad_result["predicted_roas"],
                "expected_roas_improvement": f"{ad_result['improvement_percent']:.1f}%",
                "account_level_roas_impact": f"{ad_result.get('account_level_roas_impact', 0):.2f}%",
                "monitoring_period": "7-10 days",
                "risk_level": "Low" if ad_result["current_roas"] > 2.0 else "Medium",
                "spend_ai_suggestion": await self._generate_spend_ai_suggestion(
                    ad_result, spend_change, "scale_up", user_id
                )
            })
        
        # Generate scale down recommendations
        for ad_result in scale_down:
            spend_change = ad_result["parameter_changes"]["spend"]
            current_spend = spend_change["current"]
            target_spend = spend_change["optimized"]
            
            # Find benchmark ads for spend
            benchmark_ads = await self._find_benchmark_ads(user_id, "spend")
            benchmark_data = {}
            if benchmark_ads:
                best_benchmark = benchmark_ads[0]
                benchmark_data = {
                    "ad_id": best_benchmark.get("ad_id", ""),
                    "ad_name": best_benchmark.get("ad_name", ""),
                    "metrics": {
                        "spend": best_benchmark.get("additional_metrics", {}).get("spend", 0),
                        "roas": best_benchmark.get("additional_metrics", {}).get("roas", 0),
                        "ctr": best_benchmark.get("additional_metrics", {}).get("ctr", 0),
                        "cpc": best_benchmark.get("additional_metrics", {}).get("cpc", 0),
                        "cpm": best_benchmark.get("additional_metrics", {}).get("cpm", 0)
                    }
                }
            
            recommendations["recommendations"].append({
                "ad_id": ad_result["ad_id"],
                "ad_name": ad_result["ad_name"],
                "action": "Scale Down",
                "current_daily_spend": f"${current_spend:.2f}",
                "recommended_daily_spend": f"${target_spend:.2f}",
                "decrease_percentage": f"{abs(spend_change['change_percent']):.1f}%",
                "reasoning": f"Reducing spend will improve efficiency while maintaining ROAS",
                "expected_savings": f"${(current_spend - target_spend) * 30:.2f}/month",
                "benchmark_metrics": benchmark_data,
                "current_roas": ad_result["current_roas"],
                "predicted_roas": ad_result["predicted_roas"],
                "expected_roas_improvement": f"{ad_result['improvement_percent']:.1f}%",
                "account_level_roas_impact": f"{ad_result.get('account_level_roas_impact', 0):.2f}%",
                "spend_ai_suggestion": await self._generate_spend_ai_suggestion(
                    ad_result, spend_change, "scale_down", user_id
                )
            })
        
        return recommendations
    
    async def _generate_efficiency_recommendations(self, efficiency_improvements: List[Dict], user_id: str) -> Dict:
        """Generate CPC/CPM efficiency improvement recommendations."""
        recommendations = []
        
        for ad_result in efficiency_improvements:
            parameter_changes = ad_result["parameter_changes"]
            
            # Determine primary efficiency metric - check both CPC and CPM changes
            metrics_to_check = []
            if "cpc" in parameter_changes:
                metrics_to_check.append(("cpc", "Cost Per Click", parameter_changes["cpc"]))
            if "cpm" in parameter_changes:
                metrics_to_check.append(("cpm", "Cost Per Mille", parameter_changes["cpm"]))
            
            if not metrics_to_check:
                continue
            
            # If both exist, choose the one with larger percentage change
            if len(metrics_to_check) > 1:
                metric_info = max(metrics_to_check, key=lambda x: abs(x[2]["change_percent"]))
            else:
                metric_info = metrics_to_check[0]
            
            metric, metric_name, change_data = metric_info
            
            # Find benchmark ads for this metric to provide context
            benchmark_ads = await self._find_benchmark_ads(user_id, metric)
            
            # Generate AI-powered strategies instead of static ones
            ai_strategies = await self._generate_ai_efficiency_strategies(
                ad_result, metric, change_data, benchmark_ads
            )
            
            # Get spend changes for context
            spend_change = ad_result["parameter_changes"].get("spend", {})
            spend_insight = ""
            if spend_change:
                if spend_change["change_direction"] == "decrease":
                    spend_insight = f"Bonus: Spend can be reduced by {abs(spend_change['change_percent']):.1f}% while improving {metric}"
                else:
                    spend_insight = f"Note: {metric_name} improvement may require {spend_change['change_percent']:.1f}% more spend"
            
            # Extract benchmark metrics
            benchmark_data = {}
            if benchmark_ads:
                best_benchmark = benchmark_ads[0]
                benchmark_data = {
                    "ad_id": best_benchmark.get("ad_id", ""),
                    "ad_name": best_benchmark.get("ad_name", ""),
                    "metrics": {
                        metric: best_benchmark.get("additional_metrics", {}).get(metric, 0),
                        "roas": best_benchmark.get("additional_metrics", {}).get("roas", 0),
                        "spend": best_benchmark.get("additional_metrics", {}).get("spend", 0),
                        "ctr": best_benchmark.get("additional_metrics", {}).get("ctr", 0),
                        "impressions": best_benchmark.get("additional_metrics", {}).get("impressions", 0)
                    }
                }
            
            recommendations.append({
                "ad_id": ad_result["ad_id"],
                "ad_name": ad_result["ad_name"],
                "optimization_metric": metric_name,
                "current_value": f"${change_data['current']:.2f}",
                "target_value": f"${change_data['optimized']:.2f}",
                "improvement_needed": f"{abs(change_data['change_percent']):.1f}%",
                "current_spend": spend_change.get("current", 0),
                "target_spend": spend_change.get("optimized", spend_change.get("current", 0)),
                "spend_insight": spend_insight,
                "benchmark_metrics": benchmark_data,
                "current_roas": ad_result["current_roas"],
                "predicted_roas": ad_result["predicted_roas"],
                "optimization_strategies": ai_strategies,
                "expected_roas_improvement": f"{ad_result['improvement_percent']:.1f}%",
                "account_level_roas_impact": f"{ad_result.get('account_level_roas_impact', 0):.2f}%"
            })
        
        return {
            "strategy": "Improve Ad Efficiency",
            "description": f"Optimize cost efficiency for {len(recommendations)} ads",
            "recommendations": recommendations
        }
    
    async def _generate_conversion_recommendations(self, conversion_improvements: List[Dict], user_id: str) -> Dict:
        """Generate conversion rate improvement recommendations."""
        recommendations = []
        
        for ad_result in conversion_improvements:
            parameter_changes = ad_result["parameter_changes"]
            
            if "purchases" in parameter_changes:
                purchase_change = parameter_changes["purchases"]
                
                # Find benchmark ads with high conversion rates
                benchmark_ads = await self._find_benchmark_ads(user_id, "purchases")
                
                # Generate AI-powered conversion strategies
                ai_conversion_strategies = await self._generate_ai_conversion_strategies(
                    ad_result, purchase_change, benchmark_ads
                )
                
                # Get spend changes for context
                spend_change = ad_result["parameter_changes"].get("spend", {})
                spend_insight = ""
                if spend_change:
                    if spend_change["change_direction"] == "decrease":
                        spend_insight = f"Bonus: Spend can be reduced by {abs(spend_change['change_percent']):.1f}% while improving conversions"
                    else:
                        spend_insight = f"Note: Conversion improvement may require {spend_change['change_percent']:.1f}% more spend"
                
                # Extract benchmark metrics
                benchmark_data = {}
                if benchmark_ads:
                    best_benchmark = benchmark_ads[0]
                    benchmark_data = {
                        "ad_id": best_benchmark.get("ad_id", ""),
                        "ad_name": best_benchmark.get("ad_name", ""),
                        "metrics": {
                            "purchases": best_benchmark.get("purchases", 0),
                            "roas": best_benchmark.get("additional_metrics", {}).get("roas", 0),
                            "spend": best_benchmark.get("additional_metrics", {}).get("spend", 0),
                            "ctr": best_benchmark.get("additional_metrics", {}).get("ctr", 0),
                            "clicks": best_benchmark.get("additional_metrics", {}).get("clicks", 0)
                        }
                    }
                
                recommendations.append({
                    "ad_id": ad_result["ad_id"],
                    "ad_name": ad_result["ad_name"],
                    "current_conversions": int(purchase_change["current"]),
                    "target_conversions": int(purchase_change["optimized"]),
                    "improvement_needed": f"{purchase_change['change_percent']:.1f}%",
                    "current_spend": spend_change.get("current", 0),
                    "target_spend": spend_change.get("optimized", spend_change.get("current", 0)),
                    "spend_insight": spend_insight,
                    "benchmark_metrics": benchmark_data,
                    "current_roas": ad_result["current_roas"],
                    "predicted_roas": ad_result["predicted_roas"],
                    "conversion_strategies": ai_conversion_strategies,
                    "expected_roas_improvement": f"{ad_result['improvement_percent']:.1f}%",
                    "account_level_roas_impact": f"{ad_result.get('account_level_roas_impact', 0):.2f}%"
                })
        
        return {
            "strategy": "Improve Conversion Rates",
            "description": f"Optimize conversion performance for {len(recommendations)} ads",
            "recommendations": recommendations
        }
    
    # Helper methods for generating specific recommendations
    async def _find_benchmark_ads(self, user_id: str, metric: str) -> List[Dict]:
        """Find high-performing ads to use as benchmarks with their creative metadata."""
        db = get_database()
        
        # First, find ad_ids that exist in ad_analyses collection to ensure we have creative metadata
        ad_analyses = await db.ad_analyses.find({
            "user_id": user_id,
            "ad_analysis": {"$exists": True, "$ne": {}}
        }).to_list(length=100)
        
        # Extract ad_ids and campaign_ids from analyses
        ad_ids_with_analysis = []
        for analysis in ad_analyses:
            if analysis.get("ad_id"):
                ad_ids_with_analysis.append(analysis.get("ad_id"))
            if analysis.get("campaign_id"):
                ad_ids_with_analysis.append(analysis.get("campaign_id"))
        
        # If no ads with analyses found, return empty list
        if not ad_ids_with_analysis:
            logger.warning(f"No ads with creative analyses found for user {user_id}")
            return []
        
        # Get top performing ads for the specified metric that also have creative metadata
        sort_field = f"additional_metrics.{metric}"
        if metric == "purchases":
            sort_field = metric
        
        benchmark_ads = await db.ad_metrics.find({
            "user_id": user_id,
            "ad_id": {"$in": ad_ids_with_analysis},  # Only include ads that have creative analyses
            sort_field: {"$gt": 0}
        }).sort(sort_field, -1).limit(5).to_list(length=5)
        
        # Enrich with creative metadata from ad_analyses collection
        for ad in benchmark_ads:
            ad_id = ad.get("ad_id")
            campaign_id = ad.get("campaign_id")
            
            # Try to find creative analysis by ad_id or campaign_id
            creative_analysis = await db.ad_analyses.find_one({
                "user_id": user_id,
                "$or": [
                    {"ad_id": ad_id},
                    {"campaign_id": campaign_id}
                ]
            })
            
            if creative_analysis and creative_analysis.get("ad_analysis"):
                ad["creative_metadata"] = creative_analysis["ad_analysis"]
            else:
                ad["creative_metadata"] = {
                    "hook": "Unknown",
                    "tone": "Unknown",
                    "visual": "Unknown",
                    "power_phrases": "Unknown"
                }
        
        return benchmark_ads
    
    async def _find_similar_high_performing_creative(
        self, 
        current_creative: Dict, 
        benchmark_ads: List[Dict], 
        metric: str
    ) -> Dict:
        """Find similar high-performing creative for inspiration."""
        # This is a simplified version - in practice, you'd use more sophisticated similarity matching
        if benchmark_ads:
            best_benchmark = benchmark_ads[0]
            result = {
                "creative": best_benchmark.get("creative_metadata", {}),
                "metrics": {
                    metric: best_benchmark.get("additional_metrics", {}).get(metric, 0),
                    "roas": best_benchmark.get("additional_metrics", {}).get("roas", 0),
                    "spend": best_benchmark.get("additional_metrics", {}).get("spend", 0),
                    "clicks": best_benchmark.get("additional_metrics", {}).get("clicks", 0),
                    "impressions": best_benchmark.get("additional_metrics", {}).get("impressions", 0)
                }
            }
            # Handle purchases which might be at the top level
            if metric == "purchases":
                result["metrics"]["purchases"] = best_benchmark.get("purchases", 0)
            return result
        return {"creative": {}, "metrics": {}}
    
    async def _generate_ai_creative_optimization(
        self, 
        current_creative: Dict, 
        benchmark_creative: Dict, 
        optimization_goal: str
    ) -> Dict:
        """Generate AI-powered creative optimization suggestions."""
        try:
            prompt = f"""
            Optimize ad creative to {optimization_goal}.
            
            Current Creative:
            - Hook: {current_creative.get('hook', 'Unknown')}
            - Tone: {current_creative.get('tone', 'Unknown')}
            - Visual: {current_creative.get('visual', 'Unknown')}
            - Power Phrases: {current_creative.get('power_phrases', 'Unknown')}
            
            High-Performing Benchmark:
            - Hook: {benchmark_creative.get('hook', 'Unknown')}
            - Tone: {benchmark_creative.get('tone', 'Unknown')}
            - Visual: {benchmark_creative.get('visual', 'Unknown')}
            
            IMPORTANT: Respond ONLY with valid JSON. No additional text before or after the JSON.
            
            Format your response as this exact JSON structure:
            {{
                "hook": "Optimized hook text here",
                "tone": "Optimized tone here",
                "visual": "Visual recommendation here",
                "power_phrases": "Power phrases here",
                "cta": "Call to action here",
                "reasoning": "Why these changes will {optimization_goal}"
            }}
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=400,
                temperature=0.7
            )
            
            # Log the raw response for debugging
            logger.info(f"AI Creative Optimization raw response: {response[:500]}..." if response and len(response) > 500 else f"AI Creative Optimization raw response: {response}")
            
            # Parse JSON response with improved error handling
            if response and len(response.strip()) > 10:
                import json
                import re
                
                # Try multiple approaches to extract valid JSON
                try:
                    # First, try to parse the entire response as JSON
                    return json.loads(response.strip())
                except json.JSONDecodeError:
                    try:
                        # Try to find JSON block within the response
                        json_start = response.find('{')
                        json_end = response.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = response[json_start:json_end]
                            # Clean up common JSON formatting issues
                            json_str = re.sub(r'([^"]),(\s*[}\]])', r'\1\2', json_str)  # Remove trailing commas
                            json_str = re.sub(r'([^"])\n', r'\1', json_str)  # Remove newlines in values
                            return json.loads(json_str)
                    except (json.JSONDecodeError, IndexError):
                        try:
                            # Try to extract key-value pairs manually if JSON parsing fails
                            creative_data = {}
                            
                            # Look for common patterns in the response
                            hook_match = re.search(r'"hook":\s*"([^"]*)"', response, re.IGNORECASE)
                            if hook_match:
                                creative_data["hook"] = hook_match.group(1)
                            
                            tone_match = re.search(r'"tone":\s*"([^"]*)"', response, re.IGNORECASE)
                            if tone_match:
                                creative_data["tone"] = tone_match.group(1)
                            
                            visual_match = re.search(r'"visual":\s*"([^"]*)"', response, re.IGNORECASE)
                            if visual_match:
                                creative_data["visual"] = visual_match.group(1)
                            
                            reasoning_match = re.search(r'"reasoning":\s*"([^"]*)"', response, re.IGNORECASE)
                            if reasoning_match:
                                creative_data["reasoning"] = reasoning_match.group(1)
                            
                            # If we extracted at least some data, return it
                            if creative_data:
                                # Fill in missing fields with defaults
                                creative_data.setdefault("hook", "Optimized hook based on top performers")
                                creative_data.setdefault("tone", "Professional and engaging")
                                creative_data.setdefault("visual", "High-impact product demonstration")
                                creative_data.setdefault("power_phrases", "Limited time, proven results")
                                creative_data.setdefault("cta", "Shop Now")
                                creative_data.setdefault("reasoning", f"Optimized to {optimization_goal}")
                                return creative_data
                        except Exception as parse_error:
                            logger.warning(f"Failed to parse AI response manually: {str(parse_error)}")
            
            # Fallback
            logger.warning(f"Using fallback creative optimization for goal: {optimization_goal}")
            return {
                "hook": "Optimized hook based on top performers",
                "tone": "Professional and engaging", 
                "visual": "High-impact product demonstration",
                "power_phrases": "Limited time, proven results",
                "cta": "Shop Now",
                "reasoning": f"Optimized to {optimization_goal}"
            }
            
        except Exception as e:
            logger.error(f"Error generating AI creative optimization: {str(e)}")
            return {"error": "Could not generate AI suggestions"}
    
    def _generate_ctr_implementation_strategy(self, ctr_change: Dict) -> List[str]:
        """Generate specific implementation strategies for CTR improvement."""
        improvement_needed = ctr_change.get("change_percent", 0)
        
        strategies = []
        
        if improvement_needed > 50:
            strategies.extend([
                "Complete creative overhaul needed",
                "Test multiple hook variations",
                "Implement urgency and scarcity elements"
            ])
        elif improvement_needed > 25:
            strategies.extend([
                "Optimize primary hook and visual",
                "Add compelling power phrases",
                "Test different audience targeting"
            ])
        else:
            strategies.extend([
                "Minor creative adjustments",
                "A/B test current vs optimized version",
                "Monitor performance closely"
            ])
        
        return strategies
    
    async def _find_scaling_proof(self, user_id: str, current_spend: float, target_spend: float) -> Dict:
        """Find proof/examples of successful scaling from user's account."""
        # This would analyze historical data to find similar scaling successes
        return {
            "example": f"Similar ad scaled from ${current_spend:.0f} to ${target_spend:.0f} with 15% ROAS improvement",
            "confidence": "High",
            "historical_data": "Based on 3 similar scaling examples in your account"
        }
    
    async def _generate_ai_efficiency_strategies(
        self, 
        ad_result: Dict, 
        metric: str, 
        change_data: Dict, 
        benchmark_ads: List[Dict]
    ) -> List[str]:
        """Generate AI-powered efficiency improvement strategies."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            # Prepare benchmark data for context
            benchmark_info = []
            for bench_ad in benchmark_ads[:3]:  # Top 3 for context
                creative = bench_ad.get("creative_metadata", {})
                metrics = bench_ad.get("additional_metrics", {})
                benchmark_info.append(f"- {creative.get('hook', 'Unknown')} (tone: {creative.get('tone', 'Unknown')}, {metric.upper()}: ${metrics.get(metric, 0):.2f})")
            
            benchmark_context = "\n".join(benchmark_info) if benchmark_info else "No benchmark data available"
            
            # Get ad's creative metadata for context
            current_creative = ad_result.get("creative_metadata", {})
            
            prompt = f"""
            Generate a specific, actionable AI suggestion for optimizing {metric.upper()} (Cost Per {'Click' if metric == 'cpc' else 'Mille'}) for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}
            - Creative Hook: {current_creative.get('hook', 'Unknown')}
            - Creative Tone: {current_creative.get('tone', 'Unknown')}
            - Visual Style: {current_creative.get('visual', 'Unknown')}
            
            Top Performing {metric.upper()} Benchmarks:
            {benchmark_context}

            Parameter Change Required:
            - Metric: {metric.upper()}
            - Current Value: ${change_data['current']:.2f}
            - Target Value: ${change_data['optimized']:.2f}
            - Change Required: {change_data['change_direction']} by {abs(change_data['change_percent']):.1f}%

            Provide a concise, actionable suggestion (2-3 sentences) that specifically addresses how to achieve this {metric.upper()} improvement. Use the benchmark data to suggest specific creative or strategic changes. Include specific tactics, not generic advice.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                # Convert single response to list of strategies
                strategies = [s.strip() for s in response.split('\n') if s.strip() and len(s.strip()) > 10]
                if strategies:
                    return strategies[:3]  # Return up to 3 strategies
                else:
                    return [response.strip()]
            else:
                return [self._get_fallback_suggestion(metric, change_data['change_direction'], change_data['change_percent'])]
                
        except Exception as e:
            logger.error(f"Error generating AI suggestion for {metric}: {str(e)}")
            return [self._get_fallback_suggestion(metric, change_data['change_direction'], change_data['change_percent'])]
    
    def _get_fallback_suggestion(self, param: str, change_direction: str, change_percent: float) -> str:
        """Fallback suggestions when AI fails."""
        fallback_suggestions = {
            "ctr": f"{'Optimize creative hook and visual elements' if change_direction == 'increase' else 'Review audience targeting to improve relevance'} to {change_direction} CTR by {abs(change_percent):.1f}%",
            "spend": f"{'Scale budget gradually while monitoring ROAS' if change_direction == 'increase' else 'Reduce spend while maintaining performance'} by {abs(change_percent):.1f}%",
            "cpc": f"{'Refine audience targeting and improve ad relevance' if change_direction == 'decrease' else 'Consider premium placements or broader targeting'} to {change_direction} CPC by {abs(change_percent):.1f}%",
            "cpm": f"{'Improve ad quality score and audience targeting' if change_direction == 'decrease' else 'Expand reach with broader audiences'} to {change_direction} CPM by {abs(change_percent):.1f}%",
            "clicks": f"{'Enhance call-to-action and creative appeal' if change_direction == 'increase' else 'Focus on quality over quantity in targeting'} to {change_direction} clicks by {abs(change_percent):.1f}%",
            "impressions": f"{'Increase budget or broaden audience' if change_direction == 'increase' else 'Narrow targeting for more qualified impressions'} by {abs(change_percent):.1f}%",
            "purchases": f"{'Optimize landing page and offer strength' if change_direction == 'increase' else 'Focus on higher-intent audiences'} to {change_direction} conversions by {abs(change_percent):.1f}%"
        }
        
        return fallback_suggestions.get(param, f"Optimize {param} through strategic adjustments to {change_direction} by {abs(change_percent):.1f}%")
    
    def _get_parameter_priority(self, param: str, change_percent: float) -> str:
        """Determine priority level based on parameter and change magnitude."""
        if change_percent > 50:
            return "High"
        elif change_percent > 25:
            return "Medium"
        else:
            return "Low"
    
    def _get_implementation_difficulty(self, param: str) -> str:
        """Determine implementation difficulty for each parameter."""
        difficulty_map = {
            "ctr": "Medium",  # Requires creative changes
            "spend": "Easy",   # Just budget adjustment
            "cpc": "Hard",     # Complex bidding/targeting optimization
            "cpm": "Hard",     # Complex audience/quality optimization
            "clicks": "Medium", # Creative and targeting changes
            "impressions": "Easy", # Budget/audience expansion
            "purchases": "Hard"  # Conversion optimization (creative + landing page)
        }
        return difficulty_map.get(param, "Medium")
    
    def _get_parameter_timeline(self, param: str) -> str:
        """Expected timeline to see results for each parameter."""
        timeline_map = {
            "ctr": "3-7 days",      # Quick creative feedback
            "spend": "1-3 days",    # Immediate budget effects
            "cpc": "7-14 days",     # Bidding optimization time
            "cpm": "7-14 days",     # Audience optimization time
            "clicks": "3-7 days",   # Creative appeal feedback
            "impressions": "1-3 days", # Quick reach expansion
            "purchases": "7-21 days"   # Conversion optimization takes longer
        }
        return timeline_map.get(param, "7-14 days")

    async def _generate_ai_conversion_strategies(
        self, 
        ad_result: Dict, 
        purchase_change: Dict, 
        benchmark_ads: List[Dict]
    ) -> List[str]:
        """Generate AI-powered conversion improvement strategies."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            creative_metadata = ad_result.get("creative_metadata", {})
            
            # Prepare benchmark data for context
            benchmark_info = []
            for bench_ad in benchmark_ads[:3]:
                creative = bench_ad.get("creative_metadata", {})
                purchases = bench_ad.get("purchases", 0)
                benchmark_info.append(f"- {creative.get('hook', 'Unknown')} (conversions: {purchases})")
            
            benchmark_context = "\n".join(benchmark_info) if benchmark_info else "No benchmark data available"
            
            prompt = f"""
            Generate specific, actionable strategies for improving conversion rates for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}
            - Creative Hook: {creative_metadata.get('hook', 'Unknown')}
            - Creative Tone: {creative_metadata.get('tone', 'Unknown')}

            Top Converting Ad Benchmarks:
            {benchmark_context}

            Conversion Change Required:
            - Current Conversions: {int(purchase_change['current'])}
            - Target Conversions: {int(purchase_change['optimized'])}
            - Improvement Needed: {purchase_change['change_percent']:.1f}%

            Provide 3-5 specific, actionable strategies (one per line) for improving conversion rates. Focus on:
            1. Creative optimization
            2. Audience refinement
            3. Offer enhancement
            4. Landing page optimization
            5. Call-to-action improvements

            Format as a simple list, one strategy per line.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=300,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                # Split response into individual strategies
                strategies = [s.strip() for s in response.split('\n') if s.strip() and len(s.strip()) > 10]
                return strategies[:5]  # Limit to 5 strategies
            else:
                return self._get_fallback_conversion_strategies(purchase_change)
                
        except Exception as e:
            logger.error(f"Error generating AI conversion strategies: {str(e)}")
            return self._get_fallback_conversion_strategies(purchase_change)
    
    def _get_fallback_conversion_strategies(self, purchase_change: Dict) -> List[str]:
        """Fallback conversion strategies when AI fails."""
        improvement = purchase_change['change_percent']
        
        strategies = [
            f"Optimize landing page and offer strength to increase conversions by {improvement:.1f}%",
            "Focus on clearer value proposition and reduced friction in purchase process",
            "Test stronger call-to-action buttons and urgency elements",
            "Refine audience targeting to focus on higher-intent customers",
            "A/B test different creative hooks that emphasize product benefits"
        ]
        
        return strategies

    async def _generate_ctr_ai_suggestion(
        self, 
        ad_result: Dict, 
        ctr_change: Dict, 
        creative_metadata: Dict, 
        benchmark_creative: Dict
    ) -> str:
        """Generate AI-powered CTR improvement suggestion."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            prompt = f"""
            Generate a specific, actionable AI suggestion for improving CTR (Click-Through Rate) for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}
            - Creative Hook: {creative_metadata.get('hook', 'Unknown')}
            - Creative Tone: {creative_metadata.get('tone', 'Unknown')}

            High-Performing Benchmark:
            - Hook: {benchmark_creative.get('hook', 'Unknown')}
            - Tone: {benchmark_creative.get('tone', 'Unknown')}

            CTR Change Required:
            - Current CTR: {ctr_change['current']:.3f}%
            - Target CTR: {ctr_change['optimized']:.3f}%
            - Improvement Needed: {ctr_change['change_percent']:.1f}%

            Provide a concise, actionable suggestion (2-3 sentences) that specifically addresses how to achieve this CTR improvement. Include specific tactics, not generic advice.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                return response.strip()
            else:
                return self._get_fallback_suggestion("ctr", ctr_change['change_direction'], ctr_change['change_percent'])
                
        except Exception as e:
            logger.error(f"Error generating CTR AI suggestion: {str(e)}")
            return self._get_fallback_suggestion("ctr", ctr_change['change_direction'], ctr_change['change_percent'])

    async def _generate_efficiency_ai_suggestion(
        self, 
        ad_result: Dict, 
        metric: str, 
        change_data: Dict, 
        benchmark_ads: List[Dict]
    ) -> str:
        """Generate AI-powered efficiency improvement suggestion."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            # Get benchmark context
            benchmark_info = []
            for bench_ad in benchmark_ads[:2]:
                creative = bench_ad.get("creative_metadata", {})
                metrics = bench_ad.get("additional_metrics", {})
                benchmark_info.append(f"- {creative.get('hook', 'Unknown')} ({metric.upper()}: ${metrics.get(metric, 0):.2f})")
            
            benchmark_context = "\n".join(benchmark_info) if benchmark_info else "No benchmark data available"
            
            prompt = f"""
            Generate a specific, actionable AI suggestion for optimizing {metric.upper()} for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}

            Top Performing {metric.upper()} Benchmarks:
            {benchmark_context}

            Change Required:
            - Current {metric.upper()}: ${change_data['current']:.2f}
            - Target {metric.upper()}: ${change_data['optimized']:.2f}
            - Improvement Needed: {abs(change_data['change_percent']):.1f}%

            Provide a concise, actionable suggestion (2-3 sentences) that specifically addresses how to achieve this {metric.upper()} improvement.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                return response.strip()
            else:
                return self._get_fallback_suggestion(metric, change_data['change_direction'], change_data['change_percent'])
                
        except Exception as e:
            logger.error(f"Error generating {metric} AI suggestion: {str(e)}")
            return self._get_fallback_suggestion(metric, change_data['change_direction'], change_data['change_percent'])

    async def _generate_conversion_ai_suggestion(
        self, 
        ad_result: Dict, 
        purchase_change: Dict, 
        benchmark_ads: List[Dict]
    ) -> str:
        """Generate AI-powered conversion improvement suggestion."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            # Get benchmark context
            benchmark_info = []
            for bench_ad in benchmark_ads[:2]:
                creative = bench_ad.get("creative_metadata", {})
                purchases = bench_ad.get("purchases", 0)
                benchmark_info.append(f"- {creative.get('hook', 'Unknown')} (conversions: {purchases})")
            
            benchmark_context = "\n".join(benchmark_info) if benchmark_info else "No benchmark data available"
            
            prompt = f"""
            Generate a specific, actionable AI suggestion for improving conversions for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}

            Top Converting Benchmarks:
            {benchmark_context}

            Conversion Change Required:
            - Current Conversions: {int(purchase_change['current'])}
            - Target Conversions: {int(purchase_change['optimized'])}
            - Improvement Needed: {purchase_change['change_percent']:.1f}%

            Provide a concise, actionable suggestion (2-3 sentences) that specifically addresses how to achieve this conversion improvement.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                return response.strip()
            else:
                return self._get_fallback_suggestion("purchases", purchase_change['change_direction'], purchase_change['change_percent'])
                
        except Exception as e:
            logger.error(f"Error generating conversion AI suggestion: {str(e)}")
            return self._get_fallback_suggestion("purchases", purchase_change['change_direction'], purchase_change['change_percent'])

    def _generate_fallback_recommendations(self, ad_data: List[Dict], target_improvement: float) -> Dict:
        """Generate basic recommendations when ML optimization fails."""
        return {
            "goal": f"Achieve {target_improvement}% ROAS improvement",
            "message": "Insufficient data for ML optimization. Using rule-based recommendations.",
            "basic_recommendations": [
                "Collect more performance data (minimum 20 ads with 3+ days of data each)",
                "Focus on improving top-performing ads first",
                "Test creative variations on ads with good ROAS but low CTR"
            ],
            "data_status": {
                "ads_found": len(ad_data),
                "minimum_required": 20,
                "recommendation": "Run ads for at least 1-2 weeks to gather sufficient data"
            }
        }

    
    async def _generate_spend_ai_suggestion(
        self, 
        ad_result: Dict, 
        spend_change: Dict, 
        action_type: str, 
        user_id: str
    ) -> str:
        """Generate AI suggestion for spend optimization."""
        try:
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            
            creative_metadata = ad_result.get("creative_metadata", {})
            
            prompt = f"""
            Generate a specific, actionable AI suggestion for {action_type.replace('_', ' ')} ad spend for this Facebook ad:

            Current Ad Context:
            - Ad Name: {ad_result.get('ad_name', 'Unknown')}
            - Current ROAS: {ad_result['current_roas']:.2f}
            - Creative Hook: {creative_metadata.get('hook', 'Unknown')}
            - Creative Tone: {creative_metadata.get('tone', 'Unknown')}

            Spend Change Required:
            - Current Daily Spend: ${spend_change['current']:.2f}
            - Target Daily Spend: ${spend_change['optimized']:.2f}
            - Change: {spend_change['change_direction']} by {abs(spend_change['change_percent']):.1f}%
            - Action: {action_type.replace('_', ' ').title()}

            Provide a concise, actionable suggestion (2-3 sentences) for how to safely and effectively implement this spend change while maintaining or improving performance.
            """
            
            response = await openai_service.get_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            
            if response and len(response.strip()) > 10:
                return response.strip()
            else:
                if action_type == "scale_up":
                    return f"Gradually increase spend by {spend_change['change_percent']:.1f}% while monitoring ROAS closely. Scale in 20-30% increments every 3-5 days to maintain performance."
                else:
                    return f"Reduce spend by {abs(spend_change['change_percent']):.1f}% while optimizing targeting to maintain conversion volume. Focus budget on highest-performing audience segments."
                
        except Exception as e:
            logger.error(f"Error generating spend AI suggestion: {str(e)}")
            if action_type == "scale_up":
                return f"Gradually increase spend by {spend_change['change_percent']:.1f}% while monitoring ROAS closely."
            else:
                return f"Reduce spend by {abs(spend_change['change_percent']):.1f}% while maintaining targeting efficiency."

# Create global instance
ml_optimization_service = MLOptimizationService()
