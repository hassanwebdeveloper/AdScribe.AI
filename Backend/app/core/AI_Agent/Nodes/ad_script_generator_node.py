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
            
            # Construct the prompt with actual data
            ad_script_prompt = f"""
Aap aik expert Urdu ad script writer hain. Aapka kaam hai aik zabardast Facebook video ad script likhna based on best-performing ad.

Target Product: {target_product}
Target Product Type: {target_product_type}

Pehle bataayein ke best ad ka hook, background, ya tone kya tha jo successful raha hai.

Phir nayi script likhein Roman Urdu mein is structure mein for "{target_product}" ({target_product_type}):

Hook (5 seconds): Best ad ka hook tha: "{best_ad_hook}" aur tone tha: "{best_ad_tone}". Is successful hook strategy ko {target_product} ke liye adapt karo. Power words ka istamaal karo jaise best ad mein use hue the: "{best_ad_power_phrases}". Hook mein {target_product} ki main benefit ya unique selling point highlight karo jo customer ka scroll roke.

Interest & Desire: Best ad ke tone aur style "{best_ad_tone}" ko follow karte hue, {target_product} ki main benefits aur features ki tareef karo. Best ad ke successful power phrases "{best_ad_power_phrases}" ko {target_product} ke context mein modify karke use karo. Quality, durability, aur value for money ke baare mein batao jo customer ko convince kare.

Risk Reversal: Best ad ki trust-building approach ko follow karte hue, {target_product} ke liye money back guarantee provide karo. Customer ko confidence dilao ke agar product expectations meet na kare to paisay wapis milenge.

Call to Action: Best ad ke successful CTA pattern ko {target_product} ke liye adapt karo. Strong aur immediate action-driving CTA banao.

Best ad se connection: Best ad ke successful elements (Hook: "{best_ad_hook}", Tone: "{best_ad_tone}", Power Phrases: "{best_ad_power_phrases}", Visual: "{best_ad_visual}") ko {target_product} ke liye kaise adapt kar rahe hain, yeh explain karo.

Target Product: {target_product}
Target Product Type: {target_product_type}
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

BEST AD KE SUCCESSFUL COMPONENTS (Jo aap ko follow karne hain):
HOOK (5 seconds): {best_ad_hook}
TONE: {best_ad_tone}
POWER PHRASES: {best_ad_power_phrases}
VISUAL ELEMENTS: {best_ad_visual}
PRODUCT: {best_ad_product}
PRODUCT TYPE: {best_ad_product_type}

User Request: {state["user_message"]}
"""
            
            # Add previous messages context if available
            messages = [{"role": "system", "content": ad_script_prompt}]
            
            # Add previous conversation context
            if state.get("previous_messages"):
                for msg in state["previous_messages"]:
                    # Map 'bot' role to 'assistant' for OpenAI API compatibility
                    role = msg.get("role", "user")
                    if role == "bot":
                        role = "assistant"
                    
                    messages.append({
                        "role": role,
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