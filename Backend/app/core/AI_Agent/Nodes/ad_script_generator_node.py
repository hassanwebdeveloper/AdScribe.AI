"""
Ad Script Generator Node for LangGraph AI Agent

This node generates ad scripts using best-performing ad analysis data and Urdu prompt template.
"""

from typing import Dict, List, Any
import logging
from app.services.dynamic_prompt_service import dynamic_prompt_service

# Set up logging
logger = logging.getLogger(__name__)

class AdScriptGeneratorNode:
    """
    Node responsible for generating ad scripts using best ad analysis data.
    """
    
    def __init__(self):
        """Initialize the ad script generator node."""
        pass
    
    async def generate_ad_script(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate ad script using the best ad analysis data with the specified Urdu prompt.
        
        Args:
            state: Agent state containing user_message, ad_analyses, and other data
            
        Returns:
            Updated state with generated ad script
        """
        try:
            ad_analyses = state.get("ad_analyses", [])
            if not ad_analyses:
                state["final_response"] = "Sorry, no ad analysis data available for script generation."
                return state
            
            # Use the first (best) ad analysis
            best_ad = ad_analyses[0]
            
            # Extract required data
            ad_title = best_ad.get("video_title", "N/A")
            metrics = best_ad.get("metrics", {})
            roas = metrics.get("roas", "N/A")
            ctr = metrics.get("ctr", "N/A")
            conversions = metrics.get("conversions", "N/A")
            revenue = metrics.get("revenue", "N/A")
            audio_description = best_ad.get("audio_description", "N/A")
            video_description = best_ad.get("video_description", "N/A")
            
            # Extract detailed ad analysis components
            ad_analysis = best_ad.get("ad_analysis", {})
            best_ad_hook = ad_analysis.get("hook", "N/A")
            best_ad_tone = ad_analysis.get("tone", "N/A")
            best_ad_power_phrases = ad_analysis.get("power_phrases", "N/A")
            best_ad_visual = ad_analysis.get("visual", "N/A")
            best_ad_product = ad_analysis.get("product", "N/A")
            best_ad_product_type = ad_analysis.get("product_type", "N/A")
            
            # Get product information from state if available
            product_info = state.get("product_info", {})
            target_product = product_info.get("product", "Perfume") if product_info else "Perfume"
            target_product_type = product_info.get("product_type", "Cosmetic") if product_info else "Cosmetic"
            
            # Prepare variables for the prompt template
            prompt_variables = {
                "target_product": target_product,
                "target_product_type": target_product_type,
                "best_ad_hook": best_ad_hook,
                "best_ad_tone": best_ad_tone,
                "best_ad_power_phrases": best_ad_power_phrases,
                "best_ad_visual": best_ad_visual,
                "best_ad_product": best_ad_product,
                "best_ad_product_type": best_ad_product_type,
                "ad_title": ad_title,
                "roas": roas,
                "ctr": ctr,
                "conversions": conversions,
                "revenue": revenue,
                "audio_description": audio_description,
                "video_description": video_description,
                "user_message": state["user_message"]
            }
            
            # Use dynamic prompt service to generate the ad script with conversation context
            ad_script = await dynamic_prompt_service.make_chat_completion_with_context(
                prompt_key="ad_script_generator",
                user_message=state["user_message"],
                previous_messages=state.get("previous_messages"),
                system_prompt_variables=prompt_variables
            )
            
            if ad_script:
                state["final_response"] = ad_script
            else:
                state["final_response"] = "Sorry, I encountered an error while generating the ad script."
                state["error"] = "Failed to generate ad script using dynamic prompt service"
            
            logger.info(f"Generated ad script successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error generating ad script: {str(e)}")
            state["final_response"] = f"Sorry, I encountered an error while generating the ad script: {str(e)}"
            state["error"] = f"Ad script generation error: {str(e)}"
            return state