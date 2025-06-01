import logging
from typing import List, Dict, Any
from datetime import datetime
from app.core.AI_Agent.Agent.Analyze_all_Ads import run_ad_analysis_graph
from app.models.ad_analysis import AdAnalysis, AdAnalysisDetail, AdSetTargeting
from app.core.database import get_database

logger = logging.getLogger(__name__)

class AIAgentService:
    """Service to handle AI Agent operations and database integration."""
    
    def __init__(self):
        self.db = get_database()
    
    async def analyze_ads_with_ai_agent(
        self, 
        user_id: str, 
        access_token: str, 
        account_id: str
    ) -> List[Dict[str, Any]]:
        """
        Run the AI Agent to analyze ads and save results to database.
        
        Args:
            user_id: The user ID
            access_token: Facebook access token
            account_id: Facebook ad account ID
            
        Returns:
            List of stored ad analysis results
        """
        try:
            logger.info(f"Starting AI Agent analysis for user {user_id}")
            
            # Run the AI Agent
            analysis_results = await run_ad_analysis_graph(
                user_id=user_id,
                access_token=access_token,
                account_id=account_id
            )
            
            if not analysis_results:
                logger.warning(f"No analysis results returned from AI Agent for user {user_id}")
                return []
            
            logger.info(f"AI Agent returned {len(analysis_results)} analysis results")
            
            # Check for existing analyses to avoid duplicates
            existing_video_ids = []
            if analysis_results:
                video_ids = [result.get("video_id") for result in analysis_results if result.get("video_id")]
                if video_ids:
                    existing_docs = await self.db.ad_analyses.find({
                        "user_id": user_id,
                        "video_id": {"$in": video_ids}
                    }).to_list(length=None)
                    existing_video_ids = [doc.get("video_id") for doc in existing_docs]
                    logger.info(f"Found {len(existing_video_ids)} existing analyses to skip")
            
            # Store results in database
            stored_analyses = []
            for result in analysis_results:
                try:
                    video_id = result.get("video_id")
                    
                    # Skip if already exists
                    if video_id and video_id in existing_video_ids:
                        logger.debug(f"Skipping duplicate analysis for video_id: {video_id}")
                        continue
                    
                    # Convert AI Agent result to AdAnalysis format
                    ad_analysis_data = self._convert_ai_result_to_ad_analysis(result)
                    
                    if not ad_analysis_data:
                        logger.warning(f"Could not convert AI result to ad analysis format: {result}")
                        continue
                    
                    # Create AdAnalysis object
                    ad_analysis = AdAnalysis(
                        user_id=user_id,
                        **ad_analysis_data
                    )
                    
                    # Insert into database
                    insert_result = await self.db.ad_analyses.insert_one(ad_analysis.model_dump(by_alias=True))
                    
                    # Get the inserted document
                    stored_analysis = await self.db.ad_analyses.find_one({"_id": insert_result.inserted_id})
                    stored_analyses.append(stored_analysis)
                    
                    logger.debug(f"Stored analysis for video_id: {video_id}")
                    
                except Exception as e:
                    logger.error(f"Error storing individual analysis result: {e}", exc_info=True)
                    continue
            
            logger.info(f"Successfully stored {len(stored_analyses)} new ad analyses")
            return stored_analyses
            
        except Exception as e:
            logger.error(f"Error in AI Agent analysis: {e}", exc_info=True)
            raise
    
    def _convert_ai_result_to_ad_analysis(self, ai_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert AI Agent result to AdAnalysis format.
        
        Args:
            ai_result: Result from AI Agent
            
        Returns:
            Dictionary in AdAnalysis format
        """
        try:
            # Extract ad_analysis from AI result
            ad_analysis_detail = None
            if ai_result.get("ad_analysis"):
                ad_analysis_detail = AdAnalysisDetail(
                    hook=ai_result["ad_analysis"].get("hook"),
                    tone=ai_result["ad_analysis"].get("tone"),
                    power_phrases=ai_result["ad_analysis"].get("power_phrases"),
                    visual=ai_result["ad_analysis"].get("visual")
                )
            
            # Extract adset_targeting if present
            adset_targeting = None
            if ai_result.get("adset_targeting"):
                adset_targeting = AdSetTargeting(**ai_result["adset_targeting"])
            
            # Build the ad analysis data
            ad_analysis_data = {
                "video_id": ai_result.get("video_id"),
                "ad_id": ai_result.get("ad_id"),
                "campaign_id": ai_result.get("campaign_id"),
                "campaign_name": ai_result.get("campaign_name"),
                "adset_id": ai_result.get("adset_id"),
                "adset_name": ai_result.get("adset_name"),
                "adset_targeting": adset_targeting,
                "ad_title": ai_result.get("ad_title"),
                "ad_message": ai_result.get("ad_message"),
                "ad_status": ai_result.get("ad_status"),
                "video_url": ai_result.get("video_url"),
                "audio_description": ai_result.get("audio_description"),
                "video_description": ai_result.get("video_description"),
                "ad_analysis": ad_analysis_detail,
                "created_at": ai_result.get("created_at", datetime.utcnow())
            }
            
            # Remove None values
            ad_analysis_data = {k: v for k, v in ad_analysis_data.items() if v is not None}
            
            return ad_analysis_data
            
        except Exception as e:
            logger.error(f"Error converting AI result to ad analysis format: {e}", exc_info=True)
            return None 