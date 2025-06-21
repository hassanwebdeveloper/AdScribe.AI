import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import asyncio
from app.core.database import get_database
from app.models.recommendation import PerformanceMetrics, CreativeMetadata

logger = logging.getLogger(__name__)


class MLPredictionService:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.encoders = {}
        self.feature_columns = []
        self.target_metrics = ['roas', 'ctr', 'cpc', 'conversion_rate']
        
    async def train_models(self, user_id: str, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Train ML models for predicting ad performance.
        
        Args:
            user_id: User ID to train models for
            force_retrain: Force retraining even if models exist
        
        Returns:
            Training results with model performance metrics
        """
        logger.info(f"Training ML models for user {user_id}")
        
        try:
            # Get training data
            training_data = await self._prepare_training_data(user_id)
            
            if len(training_data) < 50:  # Minimum data required
                logger.warning(f"Insufficient data for training ({len(training_data)} samples). Need at least 50.")
                return {
                    "success": False,
                    "message": "Insufficient data for training. Need at least 50 ad samples.",
                    "sample_count": len(training_data)
                }
            
            # Prepare features and targets
            features_df, targets_df = self._prepare_features_and_targets(training_data)
            
            if features_df.empty or targets_df.empty:
                return {
                    "success": False,
                    "message": "No valid features or targets found in data"
                }
            
            # Train models for each target metric
            training_results = {}
            
            for metric in self.target_metrics:
                if metric not in targets_df.columns:
                    continue
                
                logger.info(f"Training model for {metric}")
                
                # Prepare data for this metric
                X = features_df.copy()
                y = targets_df[metric].copy()
                
                # Remove rows with missing target values
                valid_mask = ~y.isna()
                X = X[valid_mask]
                y = y[valid_mask]
                
                if len(X) < 30:  # Minimum samples per metric
                    continue
                
                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                
                # Scale features
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                
                # Train multiple models and choose best
                models_to_try = {
                    'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
                    'gradient_boosting': GradientBoostingRegressor(n_estimators=100, random_state=42)
                }
                
                best_model = None
                best_score = float('-inf')
                best_model_name = None
                
                for model_name, model in models_to_try.items():
                    # Train model
                    model.fit(X_train_scaled, y_train)
                    
                    # Evaluate
                    y_pred = model.predict(X_test_scaled)
                    score = r2_score(y_test, y_pred)
                    mae = mean_absolute_error(y_test, y_pred)
                    
                    logger.info(f"{model_name} for {metric}: R² = {score:.3f}, MAE = {mae:.3f}")
                    
                    if score > best_score:
                        best_score = score
                        best_model = model
                        best_model_name = model_name
                
                # Store best model and scaler
                self.models[metric] = best_model
                self.scalers[metric] = scaler
                
                # Get feature importance
                if hasattr(best_model, 'feature_importances_'):
                    feature_importance = dict(zip(X.columns, best_model.feature_importances_))
                else:
                    feature_importance = {}
                
                training_results[metric] = {
                    'model_type': best_model_name,
                    'r2_score': best_score,
                    'mae': mean_absolute_error(y_test, best_model.predict(X_test_scaled)),
                    'feature_importance': feature_importance,
                    'sample_count': len(X)
                }
            
            # Save models to disk (optional)
            await self._save_models(user_id)
            
            logger.info(f"Successfully trained {len(training_results)} models for user {user_id}")
            
            return {
                "success": True,
                "models_trained": list(training_results.keys()),
                "training_results": training_results,
                "total_samples": len(training_data)
            }
            
        except Exception as e:
            logger.error(f"Error training models for user {user_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Error training models: {str(e)}"
            }
    
    async def predict_performance(
        self, 
        user_id: str,
        ad_data: Dict[str, Any],
        scenario_changes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Predict ad performance using trained ML models.
        
        Args:
            user_id: User ID
            ad_data: Ad data including creative metadata and current performance
            scenario_changes: Optional changes to test different scenarios
        
        Returns:
            Performance predictions
        """
        try:
            # Load models if not in memory
            if not self.models:
                await self._load_models(user_id)
            
            if not self.models:
                logger.warning(f"No trained models found for user {user_id}")
                return {"success": False, "message": "No trained models available"}
            
            # Prepare features
            features = self._prepare_single_ad_features(ad_data, scenario_changes)
            
            if features is None:
                return {"success": False, "message": "Could not prepare features from ad data"}
            
            # Make predictions
            predictions = {}
            feature_importance = {}
            
            for metric, model in self.models.items():
                if metric not in self.scalers:
                    continue
                
                try:
                    # Scale features
                    scaler = self.scalers[metric]
                    features_scaled = scaler.transform([features])
                    
                    # Predict
                    prediction = model.predict(features_scaled)[0]
                    predictions[metric] = float(prediction)
                    
                    # Get feature importance for this prediction
                    if hasattr(model, 'feature_importances_'):
                        importance_dict = dict(zip(self.feature_columns, model.feature_importances_))
                        feature_importance[metric] = importance_dict
                
                except Exception as e:
                    logger.error(f"Error predicting {metric}: {str(e)}")
                    continue
            
            return {
                "success": True,
                "predictions": predictions,
                "feature_importance": feature_importance,
                "ad_id": ad_data.get("ad_id")
            }
            
        except Exception as e:
            logger.error(f"Error in performance prediction: {str(e)}")
            return {"success": False, "message": f"Prediction error: {str(e)}"}
    
    async def _prepare_training_data(self, user_id: str) -> List[Dict[str, Any]]:
        """Prepare training data from database."""
        db = get_database()
        
        # Get ad metrics with performance data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # Last 90 days
        
        # Aggregate ad performance
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "collected_at": {"$gte": start_date, "$lte": end_date}
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
                    "sample_count": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "sample_count": {"$gte": 5}  # At least 5 data points
                }
            }
        ]
        
        ad_metrics = await db.ad_metrics.aggregate(pipeline).to_list(length=1000)
        
        # Get creative metadata
        ad_analyses = await db.ad_analyses.find({"user_id": user_id}).to_list(length=1000)
        
        # Create mapping
        creative_map = {}
        for analysis in ad_analyses:
            ad_id = analysis.get("ad_id") or analysis.get("campaign_id")
            if ad_id and analysis.get("ad_analysis"):
                creative_map[ad_id] = analysis["ad_analysis"]
        
        # Combine data
        training_data = []
        for metric in ad_metrics:
            ad_id = metric["_id"]
            
            # Calculate derived metrics
            conversion_rate = metric["avg_purchases"] / metric["avg_clicks"] if metric["avg_clicks"] > 0 else 0
            
            data_point = {
                "ad_id": ad_id,
                "ad_name": metric["ad_name"],
                "campaign_id": metric["campaign_id"],
                "video_id": metric["video_id"],
                "performance": {
                    "roas": metric["avg_roas"],
                    "ctr": metric["avg_ctr"],
                    "cpc": metric["avg_cpc"],
                    "cpm": metric["avg_cpm"],
                    "spend": metric["avg_spend"],
                    "revenue": metric["avg_revenue"],
                    "clicks": metric["avg_clicks"],
                    "impressions": metric["avg_impressions"],
                    "purchases": metric["avg_purchases"],
                    "conversion_rate": conversion_rate
                },
                "creative": creative_map.get(ad_id, {}),
                "sample_count": metric["sample_count"]
            }
            
            training_data.append(data_point)
        
        return training_data
    
    def _prepare_features_and_targets(self, training_data: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare features and targets for ML training."""
        
        features_list = []
        targets_list = []
        
        for data_point in training_data:
            # Extract creative features
            creative = data_point.get("creative", {})
            performance = data_point.get("performance", {})
            
            # Creative features
            features = {
                # Hook type (categorical -> numeric)
                "hook_emotional": 1 if "emotional" in str(creative.get("hook", "")).lower() else 0,
                "hook_question": 1 if "?" in str(creative.get("hook", "")) else 0,
                "hook_problem": 1 if any(word in str(creative.get("hook", "")).lower() for word in ["problem", "struggle", "issue"]) else 0,
                
                # Tone features
                "tone_emotional": 1 if "emotional" in str(creative.get("tone", "")).lower() else 0,
                "tone_urgent": 1 if "urgent" in str(creative.get("tone", "")).lower() else 0,
                "tone_professional": 1 if "professional" in str(creative.get("tone", "")).lower() else 0,
                
                # Visual features
                "visual_standing": 1 if "standing" in str(creative.get("visual", "")).lower() else 0,
                "visual_sitting": 1 if "sitting" in str(creative.get("visual", "")).lower() else 0,
                "visual_moving": 1 if "moving" in str(creative.get("visual", "")).lower() else 0,
                
                # Power elements
                "has_urgency": 1 if "urgency" in str(creative.get("power_phrases", "")).lower() else 0,
                "has_social_proof": 1 if "social proof" in str(creative.get("power_phrases", "")).lower() else 0,
                "has_risk_reversal": 1 if "risk reversal" in str(creative.get("power_phrases", "")).lower() else 0,
                
                # Performance-based features (current state)
                "current_spend": performance.get("spend", 0),
                "current_impressions": performance.get("impressions", 0),
                "current_clicks": performance.get("clicks", 0),
                
                # Derived features
                "spend_per_impression": performance.get("spend", 0) / max(performance.get("impressions", 1), 1),
                "click_rate_category": 1 if performance.get("ctr", 0) > 0.01 else 0,  # Above 1% CTR
            }
            
            # Target metrics
            targets = {
                "roas": performance.get("roas", 0),
                "ctr": performance.get("ctr", 0),
                "cpc": performance.get("cpc", 0),
                "conversion_rate": performance.get("conversion_rate", 0)
            }
            
            features_list.append(features)
            targets_list.append(targets)
        
        # Convert to DataFrames
        features_df = pd.DataFrame(features_list)
        targets_df = pd.DataFrame(targets_list)
        
        # Store feature columns
        self.feature_columns = list(features_df.columns)
        
        # Handle missing values
        features_df = features_df.fillna(0)
        targets_df = targets_df.fillna(0)
        
        return features_df, targets_df
    
    def _prepare_single_ad_features(
        self, 
        ad_data: Dict[str, Any],
        scenario_changes: Optional[Dict[str, Any]] = None
    ) -> Optional[List[float]]:
        """Prepare features for a single ad prediction."""
        
        try:
            creative = ad_data.get("creative_metadata", {})
            performance = ad_data.get("performance_metrics", {})
            
            # Apply scenario changes if provided
            if scenario_changes:
                if "creative_changes" in scenario_changes:
                    creative.update(scenario_changes["creative_changes"])
                if "performance_changes" in scenario_changes:
                    performance.update(scenario_changes["performance_changes"])
            
            # Create features (same as training)
            features = {
                "hook_emotional": 1 if "emotional" in str(creative.get("hook_content", "")).lower() else 0,
                "hook_question": 1 if "?" in str(creative.get("hook_content", "")) else 0,
                "hook_problem": 1 if any(word in str(creative.get("hook_content", "")).lower() for word in ["problem", "struggle", "issue"]) else 0,
                
                "tone_emotional": 1 if creative.get("tone_category", "").lower() == "emotional" else 0,
                "tone_urgent": 1 if creative.get("tone_category", "").lower() == "urgent" else 0,
                "tone_professional": 1 if creative.get("tone_category", "").lower() == "professional" else 0,
                
                "visual_standing": 1 if "standing" in str(creative.get("visual_style", "")).lower() else 0,
                "visual_sitting": 1 if "sitting" in str(creative.get("visual_style", "")).lower() else 0,
                "visual_moving": 1 if "moving" in str(creative.get("visual_style", "")).lower() else 0,
                
                "has_urgency": 1 if "Urgency" in creative.get("power_elements", []) else 0,
                "has_social_proof": 1 if "Social Proof" in creative.get("power_elements", []) else 0,
                "has_risk_reversal": 1 if "Risk Reversal" in creative.get("power_elements", []) else 0,
                
                "current_spend": performance.get("spend", 0),
                "current_impressions": performance.get("impressions", 0),
                "current_clicks": performance.get("clicks", 0),
                
                "spend_per_impression": performance.get("spend", 0) / max(performance.get("impressions", 1), 1),
                "click_rate_category": 1 if performance.get("ctr", 0) > 0.01 else 0,
            }
            
            # Convert to list in same order as training
            if not self.feature_columns:
                return None
            
            features_list = [features.get(col, 0) for col in self.feature_columns]
            return features_list
            
        except Exception as e:
            logger.error(f"Error preparing single ad features: {str(e)}")
            return None
    
    async def _save_models(self, user_id: str):
        """Save trained models to disk."""
        try:
            import os
            model_dir = f"models/{user_id}"
            os.makedirs(model_dir, exist_ok=True)
            
            for metric, model in self.models.items():
                model_path = f"{model_dir}/{metric}_model.joblib"
                scaler_path = f"{model_dir}/{metric}_scaler.joblib"
                
                joblib.dump(model, model_path)
                joblib.dump(self.scalers[metric], scaler_path)
            
            # Save feature columns
            features_path = f"{model_dir}/feature_columns.joblib"
            joblib.dump(self.feature_columns, features_path)
            
            logger.info(f"Models saved for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving models: {str(e)}")
    
    async def _load_models(self, user_id: str):
        """Load trained models from disk."""
        try:
            import os
            model_dir = f"models/{user_id}"
            
            if not os.path.exists(model_dir):
                return
            
            # Load feature columns
            features_path = f"{model_dir}/feature_columns.joblib"
            if os.path.exists(features_path):
                self.feature_columns = joblib.load(features_path)
            
            # Load models and scalers
            for metric in self.target_metrics:
                model_path = f"{model_dir}/{metric}_model.joblib"
                scaler_path = f"{model_dir}/{metric}_scaler.joblib"
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    self.models[metric] = joblib.load(model_path)
                    self.scalers[metric] = joblib.load(scaler_path)
            
            logger.info(f"Models loaded for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}") 