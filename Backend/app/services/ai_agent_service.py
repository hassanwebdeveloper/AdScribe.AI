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
    
    async def get_analyzed_video_ids(self, user_id: str) -> List[str]:
        """
        Fetch list of video IDs that have already been analyzed for the user.
        
        Args:
            user_id: The user ID to fetch analyzed video IDs for
            
        Returns:
            List of video IDs that are already analyzed
        """
        try:
            logger.info(f"Fetching analyzed video IDs for user {user_id}")
            
            # Query the ad_analyses collection for this user
            cursor = self.db.ad_analyses.find(
                {"user_id": user_id},
                {"video_id": 1, "_id": 0}  # Only return video_id field
            )
            
            analyses = await cursor.to_list(length=None)
            
            # Extract video IDs, filtering out None/empty values
            video_ids = [
                analysis["video_id"] 
                for analysis in analyses 
                if analysis.get("video_id") is not None and analysis.get("video_id").strip()
            ]
            
            # Remove duplicates while preserving order
            unique_video_ids = list(dict.fromkeys(video_ids))
            
            logger.info(f"Found {len(unique_video_ids)} already analyzed video IDs for user {user_id}")
            if unique_video_ids:
                logger.debug(f"Analyzed video IDs: {unique_video_ids[:10]}{'...' if len(unique_video_ids) > 10 else ''}")
                
            return unique_video_ids
            
        except Exception as e:
            logger.error(f"Error fetching analyzed video IDs for user {user_id}: {e}", exc_info=True)
            return []  # Return empty list on error to avoid breaking the flow

    async def analyze_ads_with_ai_agent(
        self, 
        user_id: str, 
        access_token: str, 
        account_id: str,
        progress_callback = None,
        cancellation_token = None
    ) -> List[Dict[str, Any]]:
        """
        Run AI Agent analysis with database integration.
        Fetches already analyzed video IDs and skips re-analysis.
        
        Args:
            user_id: The user ID
            access_token: Facebook access token
            account_id: Facebook ad account ID
            progress_callback: Optional callback function to report progress
            cancellation_token: Optional cancellation token
            
        Returns:
            List of stored ad analysis results
        """
        try:
            logger.info(f"Starting AI Agent analysis for user {user_id}")
            
            if progress_callback:
                await progress_callback(15, "Fetching previously analyzed videos...")
            
            # Fetch already analyzed video IDs from database
            analyzed_video_ids = await self.get_analyzed_video_ids(user_id)
            logger.info(f"Will skip {len(analyzed_video_ids)} already analyzed videos")
            
            if progress_callback:
                await progress_callback(20, "Starting AI Agent analysis...")
            
            # Run the AI Agent with analyzed video IDs to skip
            analysis_results = await run_ad_analysis_graph(
                user_id=user_id,
                access_token=access_token,
                account_id=account_id,
                analyzed_video_ids=analyzed_video_ids,  # Pass the analyzed video IDs
                progress_callback=progress_callback,  # Pass progress callback
                cancellation_token=cancellation_token  # Pass cancellation token
            )
            
            if not analysis_results:
                logger.warning(f"No new analysis results returned from AI Agent for user {user_id}")
                if progress_callback:
                    await progress_callback(100, "No new ads found to analyze")
                return []
            
            logger.info(f"AI Agent returned {len(analysis_results)} new analysis results")
            
            if progress_callback:
                await progress_callback(90, "Storing analysis results in database...")
            
            # Store new results in database
            stored_analyses = []
            for i, result in enumerate(analysis_results):
                try:
                    video_id = result.get("video_id")
                    
                    # Double check - skip if video_id is already in analyzed list
                    if video_id and video_id in analyzed_video_ids:
                        logger.debug(f"Double-check skip: video_id {video_id} already analyzed")
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
                    
                    logger.debug(f"Stored new analysis for video_id: {video_id}")
                    
                    # Report progress for storing results
                    if progress_callback:
                        store_progress = 90 + (i + 1) / len(analysis_results) * 8  # 90-98%
                        await progress_callback(int(store_progress), f"Stored analysis {i + 1}/{len(analysis_results)}")
                    
                except Exception as e:
                    logger.error(f"Error storing individual analysis result: {e}", exc_info=True)
                    continue
            
            logger.info(f"Successfully stored {len(stored_analyses)} new ad analyses")
            
            if progress_callback:
                await progress_callback(100, f"Analysis completed! Processed {len(stored_analyses)} ads.")
            
            return stored_analyses
            
        except Exception as e:
            logger.error(f"Error in AI Agent analysis: {e}", exc_info=True)
            if progress_callback:
                await progress_callback(0, f"Error in analysis: {str(e)}")
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