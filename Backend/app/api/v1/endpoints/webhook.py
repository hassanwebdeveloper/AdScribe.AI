from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.security import get_current_user_email
from app.core.deps import get_current_user
from app.services.user_service import get_user_by_email
from app.models.user import User
# import httpx  # No longer needed for n8n calls
import os
import re
import json
import logging
from dotenv import load_dotenv
from app.core.database import get_database
from app.core.AI_Agent.Agent.Ad_Script_Generator_Agent import ad_script_generator_agent

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# AI Agent is used instead of N8N webhook
# N8N_WEBHOOK_URL = settings.N8N_WEBHOOK_URL  # No longer needed

router = APIRouter()

class DateRange(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    daysToAnalyze: Optional[str] = None

class UserInfo(BaseModel):
    fbGraphApiKey: Optional[str] = None
    fbAdAccountId: Optional[str] = None

class ProductInfo(BaseModel):
    product: Optional[str] = None
    product_type: Optional[str] = None

class Message(BaseModel):
    role: str
    content: str

class WebhookRequest(BaseModel):
    userMessage: str
    previousMessages: List[Message] = []
    dateRange: Optional[DateRange] = None
    userInfo: Optional[UserInfo] = None
    productInfo: Optional[ProductInfo] = None

@router.post("/chat")
async def process_webhook(
    request: WebhookRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Process a chat message using the LangGraph AI Agent
    and returning the response.
    
    This endpoint processes user queries with intelligent routing
    for ad script generation or general responses.
    """
    # Initialize the agent response
    if not ad_script_generator_agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ad Script Generator Agent not properly initialized"
        )
    
    # Clean the user message from any existing date range information
    # This pattern will match formats like (Analysis date range: YYYY-MM-DD to YYYY-MM-DD) or (Analysis period: YYYY-MM-DD to YYYY-MM-DD)
    cleaned_message = re.sub(r'\s*\(Analysis (?:date range|period): \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\)\s*', '', request.userMessage)
    
    # Debug logging
    logger.info(f"Original user message: '{request.userMessage}'")
    logger.info(f"Cleaned user message: '{cleaned_message}'")
    
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        logger.info(f"Date range: {request.dateRange.startDate} to {request.dateRange.endDate}")
    else:
        logger.info("No date range provided")
    
    # Get the date range information to include it with the message
    date_range_info = ""
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        date_range_info = f"(Analysis date range: {request.dateRange.startDate} to {request.dateRange.endDate})"
    
    # Get the current date range or use default
    start_date = request.dateRange.startDate if request.dateRange and request.dateRange.startDate else None
    end_date = request.dateRange.endDate if request.dateRange and request.dateRange.endDate else None
    
    # Use default dates if not specified
    if not start_date or not end_date:
        # Use last 30 days as default
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Find best ad using frequency approach
    best_ad_id = None
    result = None
    
    try:
        # Use the get_best_performing_ad function from prediction router
        from app.routers.prediction import get_best_performing_ad
        
        logger.info(f"Finding best ad using frequency approach and filtering to only analyzed ads")
        
        # Call the function directly (it has the same parameters as the router endpoint)
        result = await get_best_performing_ad(
            start_date=start_date,
            end_date=end_date,
            days_to_predict=7,
            use_time_series=False,  # Use frequency approach
            force_refresh=False,    # Don't force refresh
            use_only_analyzed_ads=True,  # Only use ads that have entries in ad_analyses
            current_user=current_user
        )
        
        # Extract the best ad ID if available
        if result["success"] and result["best_ad"]:
            best_ad_id = result["best_ad"]["ad_id"]
            logger.info(f"Found best ad with ID: {best_ad_id}")
        else:
            logger.warning("No best ad found in prediction results")
    except Exception as e:
        logger.error(f"Error finding best ad: {str(e)}", exc_info=True)
        best_ad_id = None
        result = None
    
    # Retrieve ad analyses from the database
    db = get_database()
    ad_analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).to_list(length=100)
    
    if not ad_analyses or len(ad_analyses) == 0:
        logger.warning(f"No ad analyses found for user {current_user.id}")
        ad_analyses = []
    
    # If we have a best ad, we need to find related video analyses
    # Create a mapping from ad_id to video_id
    ad_to_video_mapping = {}
    
    # Try to find ad_id to video_id mappings from ad_metrics collection
    if best_ad_id:
        try:
            # First, see if the ad_id is directly present in the historical data
            if result and result.get("historical") and len(result["historical"]) > 0:
                first_historical = result["historical"][0]
                if "ad_id" in first_historical and first_historical["ad_id"] == best_ad_id:
                    logger.info(f"Found direct match in historical data for best ad {best_ad_id}")
                    
                    # Now check if this matches one of our ad_analyses by video_id
                    for analysis in ad_analyses:
                        if analysis.get("video_id") == best_ad_id:
                            ad_to_video_mapping[best_ad_id] = best_ad_id
                            logger.info(f"Found direct mapping: video_id {best_ad_id} is the same as ad_id")
                            break
            
            # Only proceed with the other approaches if we haven't found a mapping yet
            if not ad_to_video_mapping:
                # Simplify the approach - first check if there's a direct match between ad_id and video_id
                for analysis in ad_analyses:
                    ad_id = analysis.get("ad_id") 
                    campaign_id = analysis.get("campaign_id")
                    video_id = analysis.get("video_id")
                    
                    # Direct match with ad_id if it exists
                    if ad_id and ad_id == best_ad_id and video_id:
                        ad_to_video_mapping[best_ad_id] = video_id
                        logger.info(f"Found direct video_id {video_id} match for best ad {best_ad_id}")
                        break
                    
                    # If no direct match, try matching via campaign_id
                    if not ad_to_video_mapping and campaign_id and video_id:
                        # See if we can find the campaign_id in the ad_metrics collection
                        ad_metrics = await db.ad_metrics.find({"user_id": str(current_user.id), "ad_id": best_ad_id, "campaign_id": campaign_id}).limit(1).to_list(length=1)
                        if ad_metrics and len(ad_metrics) > 0:
                            ad_to_video_mapping[best_ad_id] = video_id
                            logger.info(f"Found campaign match video_id {video_id} for best ad {best_ad_id}")
                            break
                
                # If no mapping found yet, try the fallback approach with campaign_id lookup
                if not ad_to_video_mapping:
                    # Query ad_metrics to get the campaign_id for the best ad
                    ad_metrics = await db.ad_metrics.find({"user_id": str(current_user.id), "ad_id": best_ad_id}).limit(1).to_list(length=1)
                    
                    if ad_metrics and len(ad_metrics) > 0:
                        campaign_id = ad_metrics[0].get("campaign_id")
                        
                        # Then find video_ids in ad_analyses that match this campaign_id
                        if campaign_id:
                            for analysis in ad_analyses:
                                if analysis.get("campaign_id") == campaign_id and analysis.get("video_id"):
                                    ad_to_video_mapping[best_ad_id] = analysis.get("video_id")
                                    logger.info(f"Found campaign_id match video_id {analysis.get('video_id')} for best ad {best_ad_id}")
                                    break
                                    
        except Exception as e:
            logger.error(f"Error mapping ad_id to video_id: {str(e)}")
            
    # If still no mapping found, just use the first ad analysis's video_id
    if best_ad_id and not ad_to_video_mapping and ad_analyses and len(ad_analyses) > 0:
        first_video_id = ad_analyses[0].get("video_id")
        if first_video_id:
            ad_to_video_mapping[best_ad_id] = first_video_id
            logger.info(f"No mapping found, using first available video_id {first_video_id} for best ad {best_ad_id}")
    
    # Extract relevant data from ad analyses (video_id, audio_description, video_description)
    ad_analyses_data = []
    video_ids = []
    
    # If we have a best ad and found a mapping to video_id, filter to only include that one
    best_video_id = ad_to_video_mapping.get(best_ad_id) if best_ad_id else None
    
    # Flag to track if we found any matching ad analyses
    found_matching_analyses = False
    
    # Get best ad metrics if available
    best_ad_metrics = {}
    if best_ad_id and result and result.get("best_ad"):
        best_ad_metrics = result["best_ad"].get("average_metrics", {})
        logger.info(f"Found best ad metrics: {best_ad_metrics}")
        
        # Get the best ad's historical data if available
        best_ad_historical = result.get("historical", [])
        if best_ad_historical and len(best_ad_historical) > 0:
            # Extract additional information from historical data
            first_historical = best_ad_historical[0]
            if "ad_name" in first_historical:
                logger.info(f"Best ad name from historical data: {first_historical['ad_name']}")
    else:
        logger.warning("No best ad metrics found to include in payload")
    
    for analysis in ad_analyses:
        video_id = analysis.get("video_id")
        
        # Skip if no video_id is present
        if video_id is None:
            continue
            
        # Filter for best video if we have one
        if best_video_id and video_id != best_video_id:
            continue
            
        # We found a match
        found_matching_analyses = True
        
        # Create the ad analysis data with additional fields
        ad_data = {
            "video_id": video_id,
            "audio_description": analysis.get("audio_description") or "",
            "video_description": analysis.get("video_description") or "",
            "video_url": analysis.get("video_url") or "",
            "ad_description": analysis.get("ad_message") or "",
            "video_title": analysis.get("ad_title") or "",  # Add video title from ad_title
            "ad_analysis": analysis.get("ad_analysis", {})  # Add detailed analysis components
        }
        
        # Add best ad metrics to the ad analysis data
        if best_ad_metrics:
            ad_data["metrics"] = best_ad_metrics
        
        ad_analyses_data.append(ad_data)
        video_ids.append(video_id)
    
    # If we didn't find any matching analyses but have ad analyses available, use the first one as fallback
    if not found_matching_analyses and ad_analyses and len(ad_analyses) > 0:
        for analysis in ad_analyses:
            video_id = analysis.get("video_id")
            if video_id is not None:
                # Create the ad analysis data with additional fields
                ad_data = {
                    "video_id": video_id,
                    "audio_description": analysis.get("audio_description") or "",
                    "video_description": analysis.get("video_description") or "",
                    "video_url": analysis.get("video_url") or "",
                    "ad_description": analysis.get("ad_message") or "",
                    "video_title": analysis.get("ad_title") or "",  # Add video title from ad_title
                    "ad_analysis": analysis.get("ad_analysis", {})  # Add detailed analysis components
                }
                
                # Add best ad metrics to the ad analysis data
                if best_ad_metrics:
                    ad_data["metrics"] = best_ad_metrics
                
                ad_analyses_data.append(ad_data)
                video_ids.append(video_id)
                logger.info(f"Using fallback ad analysis with video_id {video_id}")
                break
    
    if best_video_id and found_matching_analyses:
        logger.info(f"Filtered to {len(ad_analyses_data)} ad analyses for best ad video_id {best_video_id}")
    elif found_matching_analyses:
        logger.info(f"No specific video mapping found, using {len(ad_analyses_data)} ad analyses")
    else:
        logger.info(f"Using fallback ad analysis, total: {len(ad_analyses_data)}")
    
    # Create the payload for the AI Agent
    payload = {
        "userMessage": cleaned_message,  # Use the cleaned message without the date range
        "previousMessages": [
            {"role": msg.role, "content": msg.content}
            for msg in request.previousMessages
        ],
        "dateRange": request.dateRange.model_dump() if request.dateRange else {},
        "userInfo": {
            "fbGraphApiKey": current_user.fb_graph_api_key,
            "fbAdAccountId": current_user.fb_ad_account_id,
        },
        "analysisContext": date_range_info,  # Add date range as separate field
        "adAnalyses": ad_analyses_data,  # Already filtered to include only the best ad's analysis
        "videoIds": video_ids  # Add just the video IDs as a separate object (also filtered to best ad)
    }
    
    # Log payload structure for debugging (excluding sensitive data)
    logger.info(f"Sending payload with {len(ad_analyses_data)} ad analyses")
    if ad_analyses_data:
        first_ad = ad_analyses_data[0]
        logger.info(f"First ad has fields: {list(first_ad.keys())}")
        if "metrics" in first_ad:
            logger.info(f"Metrics included: {list(first_ad['metrics'].keys())}")
    
    # Note: We don't include a separate 'bestAd' property as requested,
    # since the adAnalyses array contains only the best ad's data
    
    try:
        # Process the request using LangGraph AI Agent instead of N8N
        logger.info("Processing request with LangGraph AI Agent")
        
        # Convert previous messages to the format expected by the agent
        previous_messages = []
        for msg in request.previousMessages:
            previous_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Call the Ad Script Generator Agent
        agent_response = await ad_script_generator_agent.process_request(
            user_message=cleaned_message,
            previous_messages=previous_messages,
            ad_analyses=ad_analyses_data,
            product_info=request.productInfo.model_dump() if request.productInfo else None
        )
        
        logger.info(f"Ad Script Generator Agent response: {agent_response}")
        
        # Extract the output from agent response
        output_content = agent_response.get("output", "No response generated")
        
        # Construct the final response with output
        result["output"] = output_content
        
        # Create ad content from database if we have ad analyses data
        ad_content = None
        if ad_analyses_data and len(ad_analyses_data) > 0:
            try:
                # Get the first (and should be only) ad analysis
                ad_analysis = ad_analyses_data[0]
                
                # Get title from multiple potential sources
                title = ad_analysis.get("video_title", "")
                if not title and best_ad_id and result and result.get("best_ad"):
                    # Try to get title from best_ad data
                    title = result["best_ad"].get("ad_title", "")
                    if not title:
                        title = result["best_ad"].get("ad_name", "")
                        
                    # If still no title, try from historical data
                    if not title and result.get("historical") and len(result["historical"]) > 0:
                        first_historical = result["historical"][0]
                        title = first_historical.get("ad_name", "")
                        if not title:
                            title = first_historical.get("ad_title", "")
                
                if not title:
                    title = "Ad"
                    
                logger.info(f"Using title: {title} for ad content")
                
                # Create ad content from database information
                ad_content = {
                    "title": title or "Ad",
                    "description": ad_analysis.get("ad_description") or "",
                    "video_url": ad_analysis.get("video_url") or "",
                    "is_active": True,  # Default to active
                    "purchases": 0      # Default to 0
                }
                
                # Add metrics if available
                if "metrics" in ad_analysis:
                    ad_metrics = ad_analysis["metrics"]
                    # Calculate total purchases from historical data if available
                    if result and result.get("historical"):
                        total_purchases = 0
                        for historical_point in result["historical"]:
                            if historical_point.get("ad_id") == best_ad_id:
                                total_purchases += int(historical_point.get("conversions", 0))
                        ad_content["purchases"] = total_purchases
                        logger.info(f"Calculated total purchases for best ad: {total_purchases}")
                    else:
                        # Fallback to metrics if historical data not available
                        if "conversions" in ad_metrics:
                            try:
                                ad_content["purchases"] = int(float(ad_metrics["conversions"]))
                            except (ValueError, TypeError):
                                ad_content["purchases"] = 0
                    
                    if "revenue" in ad_metrics:
                        try:
                            ad_content["revenue"] = float(ad_metrics["revenue"])
                        except (ValueError, TypeError):
                            ad_content["revenue"] = 0.0
                    
                    # Add more metrics that might be useful
                    if "roas" in ad_metrics:
                        try:
                            ad_content["roas"] = float(ad_metrics["roas"])
                        except (ValueError, TypeError):
                            ad_content["roas"] = 0.0
                    
                    if "ctr" in ad_metrics:
                        try:
                            ad_content["ctr"] = float(ad_metrics["ctr"])
                        except (ValueError, TypeError):
                            ad_content["ctr"] = 0.0
                
                # Add video descriptions if available
                video_desc = ad_analysis.get("video_description")
                if video_desc:
                    ad_content["video_description"] = video_desc
                
                audio_desc = ad_analysis.get("audio_description") 
                if audio_desc:
                    ad_content["audio_description"] = audio_desc
                    
                # Add video ID for reference
                video_id_val = ad_analysis.get("video_id")
                if video_id_val:
                    ad_content["video_id"] = video_id_val
                    
                logger.info(f"Created ad content from database: {ad_content}")
            except Exception as e:
                logger.error(f"Error creating ad content from database: {str(e)}", exc_info=True)
                # Create a basic fallback ad if all else fails
                ad_content = {
                    "title": "Ad",
                    "description": "Advertisement",
                    "video_url": "",
                    "is_active": True,
                    "purchases": 0,
                    "video_description": "",
                    "audio_description": ""
                }
        
        # Add ad content to result if available
        if ad_content:
            result["ad"] = ad_content
            logger.info(f"Added ad content to result: {ad_content}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing request with Ad Script Generator Agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )

@router.post("/callback", response_model=Dict[str, Any])
async def webhook_callback(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handle webhook callbacks from external services
    """
    # ... existing code ... 