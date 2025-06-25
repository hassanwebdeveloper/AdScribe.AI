import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.core.database import get_database
from app.models.ml_recommendation import (
    MLRecommendationBatch, 
    MLAdRecommendation, 
    ParameterChange,
    MLRecommendationSummary
)

logger = logging.getLogger(__name__)


class MLRecommendationStorageService:
    """Service for storing and retrieving ML recommendations"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database connection lazily"""
        if self.db is None:
            self.db = get_database()
        return self.db
    
    async def save_recommendations(
        self, 
        user_id: str, 
        optimization_results: List[Dict], 
        optimization_summary: Dict[str, Any],
        goal: str,
        target_improvement: float,
        ml_enabled: bool = True
    ) -> str:
        """
        Save ML recommendations to database and return batch ID
        """
        try:
            db = await self.get_db()
            
            # Convert optimization results to MLAdRecommendation objects
            ad_recommendations = []
            for result in optimization_results:
                # Convert parameter changes to ParameterChange objects
                parameter_changes = []
                for param_name, change_data in result.get("parameter_changes", {}).items():
                    # Determine impact level based on change percentage
                    change_pct = abs(change_data["change_percent"])
                    if change_pct >= 20:
                        impact_level = "high"
                    elif change_pct >= 10:
                        impact_level = "medium"
                    else:
                        impact_level = "low"
                    
                    parameter_changes.append(ParameterChange(
                        parameter=param_name,
                        current_value=change_data["current"],
                        optimized_value=change_data["optimized"],
                        change_percent=change_data["change_percent"],
                        change_direction=change_data["change_direction"],
                        impact_level=impact_level
                    ))
                
                # Create MLAdRecommendation
                ad_rec = MLAdRecommendation(
                    ad_id=result["ad_id"],
                    ad_name=result.get("ad_name", f"Ad {result['ad_id']}"),
                    campaign_id=result.get("campaign_id"),
                    video_id=result.get("video_id"),
                    current_roas=result["current_roas"],
                    predicted_roas=result["predicted_roas"],
                    improvement_percent=result["improvement_percent"],
                    primary_strategy=self._identify_primary_strategy(result.get("parameter_changes", {})),
                    optimization_confidence=result.get("optimization_confidence", 0.7),
                    optimization_status=result.get("optimization_status", "completed"),
                    parameter_changes=parameter_changes,
                    creative_metadata=result.get("creative_metadata"),
                    implementation_strategies=result.get("implementation_strategies", []),
                    ai_creative_suggestions=result.get("ai_creative_suggestions"),
                    benchmark_creative=result.get("benchmark_creative")
                )
                
                ad_recommendations.append(ad_rec)
            
            # Create recommendation batch
            batch = MLRecommendationBatch(
                user_id=user_id,
                goal=goal,
                target_improvement=target_improvement,
                ml_optimization_enabled=ml_enabled,
                total_ads_analyzed=optimization_summary.get("total_ads_analyzed", 0),
                successful_optimizations=optimization_summary.get("successful_optimizations", 0),
                convergence_rate=optimization_summary.get("convergence_rate", 0),
                average_predicted_improvement=optimization_summary.get("average_predicted_improvement", 0),
                max_improvement_achieved=optimization_summary.get("max_improvement_achieved", 0),
                min_improvement_achieved=optimization_summary.get("min_improvement_achieved", 0),
                ctr_improvement_opportunities=optimization_summary.get("ctr_improvement_opportunities", 0),
                spend_optimization_opportunities=optimization_summary.get("spend_optimization_opportunities", 0),
                efficiency_improvement_opportunities=optimization_summary.get("efficiency_improvement_opportunities", 0),
                conversion_improvement_opportunities=optimization_summary.get("conversion_improvement_opportunities", 0),
                ad_recommendations=ad_recommendations,
                completed_at=datetime.utcnow()
            )
            
            # Save to database
            batch_dict = batch.model_dump(by_alias=True)
            await db.ml_recommendations.insert_one(batch_dict)
            
            logger.info(f"Saved ML recommendation batch {batch.id} for user {user_id} with {len(ad_recommendations)} recommendations")
            return batch.id
            
        except Exception as e:
            logger.error(f"Error saving ML recommendations: {str(e)}")
            raise
    
    async def get_recommendations_by_batch_id(self, batch_id: str, user_id: str) -> Optional[MLRecommendationBatch]:
        """Get recommendations by batch ID"""
        try:
            db = await self.get_db()
            
            batch_doc = await db.ml_recommendations.find_one({
                "_id": batch_id,
                "user_id": user_id
            })
            
            if batch_doc:
                return MLRecommendationBatch(**batch_doc)
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving recommendations batch {batch_id}: {str(e)}")
            return None
    
    async def get_latest_recommendations(self, user_id: str) -> Optional[MLRecommendationBatch]:
        """Get latest recommendations for a user"""
        try:
            db = await self.get_db()
            
            batch_doc = await db.ml_recommendations.find_one(
                {"user_id": user_id},
                sort=[("generated_at", -1)]
            )
            
            if batch_doc:
                return MLRecommendationBatch(**batch_doc)
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving latest recommendations for user {user_id}: {str(e)}")
            return None
    
    async def get_recommendation_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[MLRecommendationSummary]:
        """Get recommendation history summaries for a user"""
        try:
            db = await self.get_db()
            
            cursor = db.ml_recommendations.find(
                {"user_id": user_id},
                {
                    "_id": 1,
                    "user_id": 1,
                    "goal": 1,
                    "total_ads_analyzed": 1,
                    "average_predicted_improvement": 1,
                    "generated_at": 1,
                    "status": 1,
                    "ad_recommendations": {"$size": "$ad_recommendations"}  # Count of recommendations
                }
            ).sort("generated_at", -1).limit(limit)
            
            batches = await cursor.to_list(length=limit)
            
            summaries = []
            for batch in batches:
                summaries.append(MLRecommendationSummary(
                    batch_id=batch["_id"],
                    user_id=batch["user_id"],
                    goal=batch["goal"],
                    total_ads_analyzed=batch["total_ads_analyzed"],
                    total_opportunities=batch.get("ad_recommendations", 0),
                    average_improvement=batch["average_predicted_improvement"],
                    generated_at=batch["generated_at"],
                    status=batch["status"]
                ))
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error retrieving recommendation history for user {user_id}: {str(e)}")
            return []
    
    async def update_recommendation_status(
        self, 
        batch_id: str, 
        ad_id: str, 
        status: str, 
        user_id: str
    ) -> bool:
        """Update the status of a specific ad recommendation"""
        try:
            db = await self.get_db()
            
            result = await db.ml_recommendations.update_one(
                {
                    "_id": batch_id,
                    "user_id": user_id,
                    "ad_recommendations.ad_id": ad_id
                },
                {"$set": {"ad_recommendations.$.status": status}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating recommendation status: {str(e)}")
            return False
    
    async def archive_old_recommendations(self, days_old: int = 30) -> int:
        """Archive recommendations older than specified days"""
        try:
            db = await self.get_db()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            result = await db.ml_recommendations.update_many(
                {
                    "generated_at": {"$lt": cutoff_date},
                    "status": "active"
                },
                {"$set": {"status": "archived"}}
            )
            
            logger.info(f"Archived {result.modified_count} old recommendation batches")
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error archiving old recommendations: {str(e)}")
            return 0
    
    def _identify_primary_strategy(self, parameter_changes: Dict) -> str:
        """Identify the primary optimization strategy based on parameter changes."""
        if not parameter_changes:
            return "none"
        
        # Find the parameter with the largest absolute change
        max_change = 0
        primary_param = None
        
        for param, change_data in parameter_changes.items():
            abs_change = abs(change_data["change_percent"])
            if abs_change > max_change:
                max_change = abs_change
                primary_param = param
        
        # Map parameters to strategies
        if primary_param == "ctr":
            return "ctr"
        elif primary_param in ["spend", "impressions"]:
            return "spend"
        elif primary_param in ["cpc", "cpm"]:
            return "efficiency"
        elif primary_param in ["purchases", "clicks"]:
            return "conversion"
        else:
            return "mixed" 