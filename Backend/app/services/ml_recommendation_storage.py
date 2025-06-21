import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database import get_database

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
        optimization_results: Dict[str, Any],  # Now expects the full recommendations dict
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
            
            # Create recommendation batch document with the full structure
            batch_doc = {
                "user_id": user_id,
                "goal": goal,
                "target_improvement": target_improvement,
                "ml_optimization_enabled": ml_enabled,
                "optimization_summary": optimization_summary,
                "optimization_results": optimization_results,
                "generated_at": datetime.utcnow(),
                "status": "active",
                # For easier frontend access, also flatten the strategy recommendations
                "ctr_improvements": optimization_results.get("ctr_improvements"),
                "spend_optimizations": optimization_results.get("spend_optimizations"),
                "efficiency_improvements": optimization_results.get("efficiency_improvements"),
                "conversion_improvements": optimization_results.get("conversion_improvements")
            }
            
            # Save to database
            result = await db.ml_recommendations.insert_one(batch_doc)
            batch_id = str(result.inserted_id)
            
            logger.info(f"Saved ML recommendation batch {batch_id} for user {user_id} with {len(optimization_results)} recommendations")
            return batch_id
            
        except Exception as e:
            logger.error(f"Error saving ML recommendations: {str(e)}")
            raise
    
    async def get_recommendations_by_batch_id(self, batch_id: str, user_id: str) -> Optional[Dict]:
        """Get recommendations by batch ID"""
        try:
            db = await self.get_db()
            
            batch_doc = await db.ml_recommendations.find_one({
                "_id": batch_id,
                "user_id": user_id
            })
            
            return batch_doc
            
        except Exception as e:
            logger.error(f"Error retrieving recommendations batch {batch_id}: {str(e)}")
            return None
    
    async def get_latest_recommendations(self, user_id: str) -> Optional[Dict]:
        """Get latest recommendations for a user"""
        try:
            db = await self.get_db()
            
            batch_doc = await db.ml_recommendations.find_one(
                {"user_id": user_id},
                sort=[("generated_at", -1)]
            )
            
            return batch_doc
            
        except Exception as e:
            logger.error(f"Error retrieving latest recommendations for user {user_id}: {str(e)}")
            return None

    async def get_recommendations_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get historical recommendations for a user, with full recommendation data."""
        try:
            db = await self.get_db()
            
            # Get recent recommendation batches with full data
            batches = await db.ml_recommendations.find(
                {"user_id": user_id},
                sort=[("generated_at", -1)]
            ).limit(limit).to_list(length=limit)
            
            # Convert ObjectIds to strings and return full batch data
            history = []
            for batch in batches:
                batch["_id"] = str(batch["_id"])
                
                # Return the full batch with all recommendation data
                # This includes both the flattened structure and optimization_results
                history.append(batch)
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving recommendations history for user {user_id}: {str(e)}")
            return [] 