"""
Ad Script Generator Node for LangGraph AI Agent

This node generates ad scripts using best-performing ad analysis data and Urdu prompt template.
"""

from typing import Dict, List, Any
from openai import AsyncOpenAI
import logging
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)

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
            
            # Construct the prompt with actual data
            ad_script_prompt = f"""
Aap aik expert Urdu ad script writer hain. Aapka kaam hai aik zabardast Facebook video ad script likhna based on best-performing ad.

Pehle bataayein ke best ad ka hook, background, ya tone kya tha.

Phir nayi script likhein Roman Urdu mein is structure mein:

Hook (5 seconds): Aisi line ya scene jo log ka scroll roke aur power words ka istamaal karo idhar like "zabardast, long lasting aur intihai sasta" aur "yah ayesi khushbu hay jo aik bar aap lagain gay phir aap isko khud talaash karain gay" aur "yah attar laga kar aap agar kisi mahfil main chalay gaye to log mur kar zaroor aapko daikhain gay" etc. Sirf yah walay power words nahi balkay is tarah kay aur bhi. use at least 1 sentence of a power word in hook.

Interest & Desire: Attar ki long lasting ki tareef, at least 6-8 ghanta aapkay sath rahay ga. Beast mode projection day ga (is type kay sentences) use karo. Attar kay wooden packaging ki tareef jo buhut shahana packaging hay jo aap gift dainay main bhi use kar sakhtay hain.

Risk Reversal: Idhar lazmi money back guarantee daini hay customer ko, customer use karay, long lasting check karay na pasand aaye to paisay wapis.

Call to Action: "Abhi click karein aur order place karein"

Issi tarah jo video ad aap nay analyze kia hay us say link bhi dain kah yah aap nay us ad main bola hay is ko is andaz main change karain.

Product: Perfume
Audience: Mard aur Khawateen, 20 se 60 saal
Objective: Sales generate karna

Best ad ka data:
AD TITLE: {ad_title}
ROAS (Return on Ad Spend): {roas}
CTR (Click Through Rate): {ctr}
Conversion Volume (Purchases or Leads): {conversions}
Revenue: {revenue}
AUDIO DESCRIPTION: {audio_description}
VIDEO DESCRIPTION: {video_description}

User Request: {state["user_message"]}
"""
            
            # Add previous messages context if available
            messages = [{"role": "system", "content": ad_script_prompt}]
            
            # Add previous conversation context
            if state.get("previous_messages"):
                for msg in state["previous_messages"]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current user message
            messages.append({
                "role": "user", 
                "content": state["user_message"]
            })
            
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000,
                temperature=0.7
            )
            
            ad_script = response.choices[0].message.content
            state["final_response"] = ad_script
            
            logger.info(f"Generated ad script successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error generating ad script: {str(e)}")
            state["final_response"] = f"Sorry, I encountered an error while generating the ad script: {str(e)}"
            state["error"] = f"Ad script generation error: {str(e)}"
            return state