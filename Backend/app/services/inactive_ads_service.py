import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.database import get_database
from app.models.ad_analysis import InactiveAdAnalysis
from bson import ObjectId

logger = logging.getLogger(__name__)

class InactiveAdsService:
    """Service to handle inactive ads operations."""
    
    def __init__(self):
        self.db = get_database()
    
    async def get_inactive_ads(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get inactive ads for a user.
        
        Args:
            user_id: The user ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of inactive ad analysis records
        """
        try:
            cursor = self.db.inactive_ads_analyses.find({"user_id": user_id}).skip(skip).limit(limit)
            inactive_ads = await cursor.to_list(length=limit)
            return inactive_ads
        except Exception as e:
            logger.error(f"Error fetching inactive ads: {e}", exc_info=True)
            return []
    
    async def get_inactive_ad_by_id(self, user_id: str, ad_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific inactive ad by ID.
        
        Args:
            user_id: The user ID
            ad_id: The ad ID
            
        Returns:
            Inactive ad analysis record or None if not found
        """
        try:
            inactive_ad = await self.db.inactive_ads_analyses.find_one({
                "user_id": user_id,
                "_id": ObjectId(ad_id)
            })
            return inactive_ad
        except Exception as e:
            logger.error(f"Error fetching inactive ad by ID: {e}", exc_info=True)
            return None
    
    async def restore_inactive_ad(self, user_id: str, ad_id: str) -> bool:
        """
        Restore an inactive ad to the active ads collection.
        
        Args:
            user_id: The user ID
            ad_id: The ad ID to restore
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the inactive ad
            inactive_ad = await self.db.inactive_ads_analyses.find_one({
                "user_id": user_id,
                "_id": ObjectId(ad_id)
            })
            
            if not inactive_ad:
                logger.warning(f"Inactive ad {ad_id} not found for user {user_id}")
                return False
            
            # Remove the moved_to_inactive_at field
            if "moved_to_inactive_at" in inactive_ad:
                del inactive_ad["moved_to_inactive_at"]
            
            # Insert into active ads collection
            await self.db.ad_analyses.insert_one(inactive_ad)
            
            # Delete from inactive ads collection
            await self.db.inactive_ads_analyses.delete_one({
                "user_id": user_id,
                "_id": ObjectId(ad_id)
            })
            
            logger.info(f"Successfully restored inactive ad {ad_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error restoring inactive ad: {e}", exc_info=True)
            return False
    
    async def delete_inactive_ad(self, user_id: str, ad_id: str) -> bool:
        """
        Permanently delete an inactive ad.
        
        Args:
            user_id: The user ID
            ad_id: The ad ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.db.inactive_ads_analyses.delete_one({
                "user_id": user_id,
                "_id": ObjectId(ad_id)
            })
            
            if result.deleted_count == 0:
                logger.warning(f"Inactive ad {ad_id} not found for user {user_id}")
                return False
            
            logger.info(f"Successfully deleted inactive ad {ad_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting inactive ad: {e}", exc_info=True)
            return False
    
    async def count_inactive_ads(self, user_id: str) -> int:
        """
        Count the number of inactive ads for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of inactive ads
        """
        try:
            count = await self.db.inactive_ads_analyses.count_documents({"user_id": user_id})
            return count
        except Exception as e:
            logger.error(f"Error counting inactive ads: {e}", exc_info=True)
            return 0 