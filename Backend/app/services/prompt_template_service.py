from typing import List, Optional, Dict, Any
import re
import logging
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.models.prompt_template import PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate

logger = logging.getLogger(__name__)

class PromptTemplateService:
    """Service for managing prompt templates"""
    
    @staticmethod
    def extract_variables_from_prompt(prompt_text: str) -> List[str]:
        """Extract variables from prompt text (e.g., {variable_name})"""
        variables = re.findall(r'\{([^}]+)\}', prompt_text)
        return list(set(variables))  # Remove duplicates
    
    @staticmethod
    async def create_prompt_template(template_data: PromptTemplateCreate) -> PromptTemplate:
        """Create a new prompt template"""
        db = get_database()
        
        # Auto-extract variables if not provided
        if not template_data.variables:
            template_data.variables = PromptTemplateService.extract_variables_from_prompt(template_data.prompt_text)
        
        # Prepare document
        template_dict = template_data.dict()
        template_dict['created_at'] = datetime.utcnow()
        template_dict['updated_at'] = datetime.utcnow()
        template_dict['is_active'] = True
        
        try:
            result = await db.prompt_templates.insert_one(template_dict)
            
            # Fetch the created document
            created_doc = await db.prompt_templates.find_one({"_id": result.inserted_id})
            created_doc["_id"] = str(created_doc["_id"])
            
            return PromptTemplate(**created_doc)
        except DuplicateKeyError:
            raise ValueError(f"Prompt template with key '{template_data.prompt_key}' already exists")
    
    @staticmethod
    async def get_prompt_template(prompt_key: str) -> Optional[PromptTemplate]:
        """Get a prompt template by key"""
        db = get_database()
        
        doc = await db.prompt_templates.find_one({"prompt_key": prompt_key, "is_active": True})
        if doc:
            doc["_id"] = str(doc["_id"])
            return PromptTemplate(**doc)
        return None
    
    @staticmethod
    async def get_all_prompt_templates() -> List[PromptTemplate]:
        """Get all prompt templates"""
        db = get_database()
        
        cursor = db.prompt_templates.find({"is_active": True}).sort("category", 1).sort("prompt_name", 1)
        templates = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            templates.append(PromptTemplate(**doc))
        
        return templates
    
    @staticmethod
    async def update_prompt_template(prompt_key: str, update_data: PromptTemplateUpdate) -> Optional[PromptTemplate]:
        """Update a prompt template"""
        db = get_database()
        
        # Prepare update data
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        # Auto-extract variables if prompt_text is being updated
        if update_data.prompt_text:
            update_dict['variables'] = PromptTemplateService.extract_variables_from_prompt(update_data.prompt_text)
        
        update_dict['updated_at'] = datetime.utcnow()
        
        result = await db.prompt_templates.update_one(
            {"prompt_key": prompt_key},
            {"$set": update_dict}
        )
        
        if result.matched_count > 0:
            # Return updated document
            doc = await db.prompt_templates.find_one({"prompt_key": prompt_key})
            doc["_id"] = str(doc["_id"])
            return PromptTemplate(**doc)
        
        return None
    
    @staticmethod
    async def delete_prompt_template(prompt_key: str) -> bool:
        """Soft delete a prompt template"""
        db = get_database()
        
        result = await db.prompt_templates.update_one(
            {"prompt_key": prompt_key},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        
        return result.matched_count > 0
    
    @staticmethod
    async def initialize_default_prompts():
        """Initialize default prompts from the existing codebase"""
        db = get_database()
        
        # Check if prompts already exist
        existing_count = await db.prompt_templates.count_documents({})
        if existing_count > 0:
            logger.info("Prompt templates already exist, skipping initialization")
            return
        
        default_prompts = [
            {
                "prompt_key": "video_transcription",
                "prompt_name": "Video Transcription",
                "prompt_text": "This is a Pakistani Urdu advertisement. You may find words like Oud-al-abraj, outlet, purchase, online etc. Transcribe the spoken content in Urdu script.",
                "model": "whisper-1",
                "temperature": 0.0,
                "max_tokens": None,
                "description": "Transcribes Urdu video advertisements with specific context and terminology",
                "category": "transcription"
            },
            {
                "prompt_key": "ml_creative_optimization",
                "prompt_name": "Creative Optimization Engine",
                "prompt_text": "Optimize ad creative to {optimization_goal}.\n\nCurrent Creative:\n- Hook: {current_hook}\n- Tone: {current_tone}\n- Visual: {current_visual}\n- Power Phrases: {current_power_phrases}\n\nHigh-Performing Benchmark:\n- Hook: {benchmark_hook}\n- Tone: {benchmark_tone}\n- Visual: {benchmark_visual}\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text before or after the JSON.\n\nFormat your response as this exact JSON structure:\n{{\n    \"hook\": \"Optimized hook text here\",\n    \"tone\": \"Optimized tone here\",\n    \"visual\": \"Visual recommendation here\",\n    \"power_phrases\": \"Power phrases here\",\n    \"cta\": \"Call to action here\",\n    \"reasoning\": \"Why these changes will {optimization_goal}\"\n}}",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 400,
                "description": "Generates optimized creative recommendations based on benchmarks for ML optimization",
                "category": "ml_optimization"
            },
            {
                "prompt_key": "ml_efficiency_strategies",
                "prompt_name": "Ad Efficiency Strategy Generator",
                "prompt_text": "Generate efficiency improvement strategies for optimizing {metric} for this Facebook ad.\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n- Visual Style: {visual_style}\n- Current Targeting: {current_targeting_summary}\n\nTop Performing {metric} Benchmarks:\n{benchmark_context}\n\nParameter Change Required:\n- Metric: {metric}\n- Current Value: ${current_value}\n- Target Value: ${target_value}\n- Change Required: {change_direction} by {change_percent}%\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text.\n\nProvide specific, actionable strategies in the following JSON format:\n{{\n    \"bidding_strategy\": \"Specific bidding optimization approach\",\n    \"audience_refinement\": \"Audience targeting improvements, if targeting_changes is included in the response then must add audience_refinement in the response\", \n    \"ad_placement_optimization\": \"Placement recommendations\",\n    \"creative_improvements\": \"Creative changes based on benchmarks\",\n    \"budget_pacing\": \"Budget adjustment recommendations\",\n    \"recommended_target_audience\": \"Audience similar to top performers, if targeting_changes is included in the response then must add recommended_target_audience in the response\",\n    \"targeting_changes\": {{\n        \"geo_locations\": {{\n            \"countries\": [\"US\", \"CA\"],\n            \"places\": [\n                {{\n                    \"name\": \"Location name\",\n                    \"country\": \"Country code\",\n                    \"radius\": 10\n                }}\n            ]\n        }},\n        \"age_min\": 25,\n        \"age_max\": 55,\n        \"genders\": [1, 2],\n        \"targeting_automation\": {{\n            \"advantage_audience\": true\n        }},\n        \"interests\": [\"interest1\", \"interest2\"],\n        \"behaviors\": [\"behavior1\", \"behavior2\"],\n        \"custom_audiences\": [\"audience1\", \"audience2\"],\n        \"excluded_audiences\": [\"excluded1\", \"excluded2\"]\n    }}\n}}\n\nNote: Only include targeting_changes fields that need modification. Use the same structure as current targeting. For geo_locations, include either countries array OR places array, not both.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 600,
                "description": "Generates efficiency strategies as JSON with proper targeting_changes format",
                "category": "ml_optimization"
            },
            {
                "prompt_key": "ml_conversion_strategies",
                "prompt_name": "Conversion Rate Strategy Generator",
                "prompt_text": "Generate conversion improvement strategies for this Facebook ad.\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n- Current Targeting: {current_targeting_summary}\n\nTop Converting Benchmarks:\n{benchmark_context}\n\nConversion Change Required:\n- Current Conversions: {current_conversions}\n- Target Conversions: {target_conversions}\n- Improvement Needed: {improvement_percent}%\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text.\n\nProvide specific, actionable strategies in the following JSON format:\n{{\n    \"creative_optimization\": \"Creative changes to improve conversions\",\n    \"audience_refinement\": \"Audience targeting for higher intent, if targeting_changes is included in the response then must add audience_refinement in the response\",\n    \"offer_enhancement\": \"Offer and value proposition improvements\",\n    \"landing_page_optimization\": \"Landing page recommendations\",\n    \"call_to_action_improvements\": \"CTA optimization suggestions\",\n    \"recommended_target_audience\": \"Audience similar to top converters, if targeting_changes is included in the response then must add recommended_target_audience in the response\",\n    \"targeting_changes\": {{\n        \"geo_locations\": {{\n            \"countries\": [\"US\", \"CA\"],\n            \"places\": [\n                {{\n                    \"name\": \"Location name\",\n                    \"country\": \"Country code\",\n                    \"radius\": 10\n                }}\n            ]\n        }},\n        \"age_min\": 25,\n        \"age_max\": 55,\n        \"genders\": [1, 2],\n        \"targeting_automation\": {{\n            \"advantage_audience\": true\n        }},\n        \"interests\": [\"interest1\", \"interest2\"],\n        \"behaviors\": [\"behavior1\", \"behavior2\"],\n        \"custom_audiences\": [\"audience1\", \"audience2\"],\n        \"excluded_audiences\": [\"excluded1\", \"excluded2\"]\n    }}\n}}\n\nNote: Only include targeting_changes fields that need modification. Use the same structure as current targeting. For geo_locations, include either countries array OR places array, not both.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 600,
                "description": "Generates conversion strategies as JSON with proper targeting_changes format",
                "category": "ml_optimization"
            },
            {
                "prompt_key": "ml_spend_suggestions",
                "prompt_name": "Budget Optimization Advisor",
                "prompt_text": "Generate a specific, actionable AI suggestion for {action_type} ad spend for this Facebook ad:\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n\nSpend Change Required:\n- Current Daily Spend: ${current_spend}\n- Target Daily Spend: ${target_spend}\n- Change: {change_direction} by {change_percent}%\n- Action: {action_title}\n\nProvide a concise, actionable suggestion (2-3 sentences) for how to safely and effectively implement this spend change while maintaining or improving performance.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 150,
                "description": "Generates spend optimization suggestions for ML optimization",
                "category": "ml_optimization"
            },
            {
                "prompt_key": "ad_script_generator",
                "prompt_name": "Ad Script Generator",
                "prompt_text": """Aap aik expert Urdu ad script writer hain. Aapka kaam hai aik zabardast Facebook video ad script likhna based on best-performing ad.

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

User Request: {user_message}""",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 2000,
                "description": "Generates ad scripts based on best-performing ad analysis",
                "category": "ad_generation"
            },
            {
                "prompt_key": "general_response",
                "prompt_name": "General Response",
                "prompt_text": "You are a helpful AI assistant. Respond to the user's query in a helpful and informative manner.",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 1000,
                "description": "General purpose response for non-specific queries",
                "category": "general"
            },
            {
                "prompt_key": "text_classifier",
                "prompt_name": "Text Classifier",
                "prompt_text": """You are a text classifier that determines the intent of user queries.

Classes:
{classes_description}

Classification Guidelines:
- Analyze the user query carefully and determine which category it best fits into
- If the query doesn't clearly fit into any specific category, classify it as "{default_class}"
- Only respond with the exact class name from the list above

User Query: "{user_message}"

Respond with only the classification (class name):""",
                "model": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": 20,
                "description": "Classifies user queries into different categories",
                "category": "classification"
            },
            {
                "prompt_key": "transcription_analysis",
                "prompt_name": "Transcription Analysis",
                "prompt_text": """Aap aik marketing strategist hain jo aik ad ki Urdu transcript ka jaiza le rahe hain. Aapko yeh batana hai ke is ad mein kon kon se selling techniques use hui hain. Jaise ke:

- Emotional kahani sunana
- Social proof (reviews ya testimonials ka zikr)
- Urgency (limited time ya "abhi khareedain" ka lafz)
- Risk reversal (e.g. "agar pasand na aaye to paisay wapas")
- Viewer se direct connection ("aap ke liye", "aap jaise log")
- Mukabla ya farq dikhana (e.g. "doosri brands se behtar")

Bullets mein jawaab dein — sirf unhi cheezon ka zikr karein jo is transcript mein hain.

Transcript:
{text}""",
                "model": "gpt-4o",
                "temperature": 0.5,
                "max_tokens": None,
                "description": "Analyzes advertising transcripts for marketing techniques",
                "category": "analysis"
            },
            {
                "prompt_key": "product_extraction_transcript",
                "prompt_name": "Product Extraction from Transcript",
                "prompt_text": """Analyze this advertisement transcript and extract the product information:

1. What is the exact product name being advertised? (Give the specific name/brand if mentioned, otherwise describe the product briefly)
2. What category does this product belong to? (e.g., islamic product, cosmetic, fashion, tech, food, health, education, clothing, jewelry, electronics, etc.)

Return only a JSON with "product" and "product_type" fields.

Transcript:
{text}""",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": None,
                "description": "Extracts product information from transcripts",
                "category": "analysis"
            },
            {
                "prompt_key": "frame_analysis",
                "prompt_name": "Frame Analysis",
                "prompt_text": "I want you to give me a single word that represents a characteristic of this advertising image to characterize it. Give me only the position of the person, and necessarily what they are doing (example: sitting with the object in their hands, standing explaining, crouching looking at the object) or a characteristic of the background (example: outside, package in the background, red background).",
                "model": "gpt-4o",
                "temperature": 0.4,
                "max_tokens": 50,
                "description": "Analyzes individual video frames for visual characteristics",
                "category": "analysis"
            },
            {
                "prompt_key": "product_extraction_frames",
                "prompt_name": "Product Extraction from Frames",
                "prompt_text": """Analyze these advertisement video frames and extract the product information:

1. What is the exact product name being advertised? (Look for any text, brand names, or product labels visible in the frames)
2. What category does this product belong to? (e.g., islamic product, cosmetic, fashion, tech, food, health, education, clothing, jewelry, electronics, etc.)

Return only a JSON with "product" and "product_type" fields.""",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": None,
                "description": "Extracts product information from video frames",
                "category": "analysis"
            },
            {
                "prompt_key": "ad_analysis",
                "prompt_name": "Ad Analysis",
                "prompt_text": """STEP 1: Analyze the ad insights below.

Ad Transcript Summary: {transcription}
Visual Summary: {visual_summary}

Now answer these clearly:
1. What is the **main hook line or pattern** used in this ad? Why did it work?
2. What is the **tone** of the ad (e.g., emotional, confident, hype)?
3. What **power phrases or emotional angles** stood out?
4. What **gestures, expressions, or camera angles or visual thing** were impactful?

Important: If you include any Urdu phrases, always write them in **Roman Urdu** (Urdu written in English script like 'agar pasand na aaye to paise wapas') instead of using Urdu script. Do NOT use Urdu alphabet or Nastaliq script.

Please reply in only the following JSON format:
{{"hook":"...","tone":"...","power_phrases":"...","visual":"..."}}""",
                "model": "gpt-4o",
                "temperature": 0.4,
                "max_tokens": None,
                "description": "Analyzes complete ads combining transcript and visual data",
                "category": "analysis"
            }
        ]
        
        # Insert default prompts
        for prompt_data in default_prompts:
            template_create = PromptTemplateCreate(**prompt_data)
            try:
                await PromptTemplateService.create_prompt_template(template_create)
                logger.info(f"Created default prompt: {prompt_data['prompt_key']}")
            except Exception as e:
                logger.error(f"Failed to create default prompt {prompt_data['prompt_key']}: {e}")
        
        logger.info("Default prompt templates initialized")
    
    @staticmethod
    async def initialize_default_prompt_by_key(prompt_key: str) -> bool:
        """Initialize a specific default prompt by its key"""
        db = get_database()
        
        # Define all default prompts
        all_default_prompts = {
            "video_transcription": {
                "prompt_key": "video_transcription",
                "prompt_name": "Video Transcription",
                "prompt_text": "This is a Pakistani Urdu advertisement. You may find words like Oud-al-abraj, outlet, purchase, online etc. Transcribe the spoken content in Urdu script.",
                "model": "whisper-1",
                "temperature": 0.0,
                "max_tokens": None,
                "description": "Transcribes Urdu video advertisements with specific context and terminology",
                "category": "transcription"
            },
            "ml_creative_optimization": {
                "prompt_key": "ml_creative_optimization",
                "prompt_name": "Creative Optimization Engine",
                "prompt_text": "Optimize ad creative to {optimization_goal}.\n\nCurrent Creative:\n- Hook: {current_hook}\n- Tone: {current_tone}\n- Visual: {current_visual}\n- Power Phrases: {current_power_phrases}\n\nHigh-Performing Benchmark:\n- Hook: {benchmark_hook}\n- Tone: {benchmark_tone}\n- Visual: {benchmark_visual}\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text before or after the JSON.\n\nFormat your response as this exact JSON structure:\n{{\n    \"hook\": \"Optimized hook text here\",\n    \"tone\": \"Optimized tone here\",\n    \"visual\": \"Visual recommendation here\",\n    \"power_phrases\": \"Power phrases here\",\n    \"cta\": \"Call to action here\",\n    \"reasoning\": \"Why these changes will {optimization_goal}\"\n}}",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 400,
                "description": "Generates optimized creative recommendations based on benchmarks for ML optimization",
                "category": "ml_optimization"
            },
            "ml_efficiency_strategies": {
                "prompt_key": "ml_efficiency_strategies",
                "prompt_name": "Ad Efficiency Strategy Generator",
                "prompt_text": "Generate efficiency improvement strategies for optimizing {metric} for this Facebook ad.\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n- Visual Style: {visual_style}\n- Current Targeting: {current_targeting_summary}\n\nTop Performing {metric} Benchmarks:\n{benchmark_context}\n\nParameter Change Required:\n- Metric: {metric}\n- Current Value: ${current_value}\n- Target Value: ${target_value}\n- Change Required: {change_direction} by {change_percent}%\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text.\n\nProvide specific, actionable strategies in the following JSON format:\n{{\n    \"bidding_strategy\": \"Specific bidding optimization approach\",\n    \"audience_refinement\": \"Audience targeting improvements, if targeting_changes is included in the response then must add audience_refinement in the response\", \n    \"ad_placement_optimization\": \"Placement recommendations\",\n    \"creative_improvements\": \"Creative changes based on benchmarks\",\n    \"budget_pacing\": \"Budget adjustment recommendations\",\n    \"recommended_target_audience\": \"Audience similar to top performers, if targeting_changes is included in the response then must add recommended_target_audience in the response\",\n    \"targeting_changes\": {{\n        \"geo_locations\": {{\n            \"countries\": [\"US\", \"CA\"],\n            \"places\": [\n                {{\n                    \"name\": \"Location name\",\n                    \"country\": \"Country code\",\n                    \"radius\": 10\n                }}\n            ]\n        }},\n        \"age_min\": 25,\n        \"age_max\": 55,\n        \"genders\": [1, 2],\n        \"targeting_automation\": {{\n            \"advantage_audience\": true\n        }},\n        \"interests\": [\"interest1\", \"interest2\"],\n        \"behaviors\": [\"behavior1\", \"behavior2\"],\n        \"custom_audiences\": [\"audience1\", \"audience2\"],\n        \"excluded_audiences\": [\"excluded1\", \"excluded2\"]\n    }}\n}}\n\nNote: Only include targeting_changes fields that need modification. Use the same structure as current targeting. For geo_locations, include either countries array OR places array, not both.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 600,
                "description": "Generates efficiency strategies as JSON with proper targeting_changes format",
                "category": "ml_optimization"
            },
            "ml_conversion_strategies": {
                "prompt_key": "ml_conversion_strategies",
                "prompt_name": "Conversion Rate Strategy Generator",
                "prompt_text": "Generate conversion improvement strategies for this Facebook ad.\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n- Current Targeting: {current_targeting_summary}\n\nTop Converting Benchmarks:\n{benchmark_context}\n\nConversion Change Required:\n- Current Conversions: {current_conversions}\n- Target Conversions: {target_conversions}\n- Improvement Needed: {improvement_percent}%\n\nIMPORTANT: Respond ONLY with valid JSON. No additional text.\n\nProvide specific, actionable strategies in the following JSON format:\n{{\n    \"creative_optimization\": \"Creative changes to improve conversions\",\n    \"audience_refinement\": \"Audience targeting for higher intent, if targeting_changes is included in the response then must add audience_refinement in the response\",\n    \"offer_enhancement\": \"Offer and value proposition improvements\",\n    \"landing_page_optimization\": \"Landing page recommendations\",\n    \"call_to_action_improvements\": \"CTA optimization suggestions\",\n    \"recommended_target_audience\": \"Audience similar to top converters, if targeting_changes is included in the response then must add recommended_target_audience in the response\",\n    \"targeting_changes\": {{\n        \"geo_locations\": {{\n            \"countries\": [\"US\", \"CA\"],\n            \"places\": [\n                {{\n                    \"name\": \"Location name\",\n                    \"country\": \"Country code\",\n                    \"radius\": 10\n                }}\n            ]\n        }},\n        \"age_min\": 25,\n        \"age_max\": 55,\n        \"genders\": [1, 2],\n        \"targeting_automation\": {{\n            \"advantage_audience\": true\n        }},\n        \"interests\": [\"interest1\", \"interest2\"],\n        \"behaviors\": [\"behavior1\", \"behavior2\"],\n        \"custom_audiences\": [\"audience1\", \"audience2\"],\n        \"excluded_audiences\": [\"excluded1\", \"excluded2\"]\n    }}\n}}\n\nNote: Only include targeting_changes fields that need modification. Use the same structure as current targeting. For geo_locations, include either countries array OR places array, not both.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 600,
                "description": "Generates conversion strategies as JSON with proper targeting_changes format",
                "category": "ml_optimization"
            },
            "ml_spend_suggestions": {
                "prompt_key": "ml_spend_suggestions",
                "prompt_name": "Budget Optimization Advisor",
                "prompt_text": "Generate a specific, actionable AI suggestion for {action_type} ad spend for this Facebook ad:\n\nCurrent Ad Context:\n- Ad Name: {ad_name}\n- Current ROAS: {current_roas}\n- Creative Hook: {creative_hook}\n- Creative Tone: {creative_tone}\n\nSpend Change Required:\n- Current Daily Spend: ${current_spend}\n- Target Daily Spend: ${target_spend}\n- Change: {change_direction} by {change_percent}%\n- Action: {action_title}\n\nProvide a concise, actionable suggestion (2-3 sentences) for how to safely and effectively implement this spend change while maintaining or improving performance.",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 150,
                "description": "Generates spend optimization suggestions for ML optimization",
                "category": "ml_optimization"
            },
            "ad_script_generator": {
                "prompt_key": "ad_script_generator",
                "prompt_name": "Ad Script Generator",
                "prompt_text": """Aap aik expert Urdu ad script writer hain. Aapka kaam hai aik zabardast Facebook video ad script likhna based on best-performing ad.

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

User Request: {user_message}""",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 2000,
                "description": "Generates ad scripts based on best-performing ad analysis",
                "category": "ad_generation"
            },
            "general_response": {
                "prompt_key": "general_response",
                "prompt_name": "General Response",
                "prompt_text": "You are a helpful AI assistant. Respond to the user's query in a helpful and informative manner.",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 1000,
                "description": "General purpose response for non-specific queries",
                "category": "general"
            },
            "text_classifier": {
                "prompt_key": "text_classifier",
                "prompt_name": "Text Classifier",
                "prompt_text": """You are a text classifier that determines the intent of user queries.

Classes:
{classes_description}

Classification Guidelines:
- Analyze the user query carefully and determine which category it best fits into
- If the query doesn't clearly fit into any specific category, classify it as "{default_class}"
- Only respond with the exact class name from the list above

User Query: "{user_message}"

Respond with only the classification (class name):""",
                "model": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": 20,
                "description": "Classifies user queries into different categories",
                "category": "classification"
            },
            "transcription_analysis": {
                "prompt_key": "transcription_analysis",
                "prompt_name": "Transcription Analysis",
                "prompt_text": """Aap aik marketing strategist hain jo aik ad ki Urdu transcript ka jaiza le rahe hain. Aapko yeh batana hai ke is ad mein kon kon se selling techniques use hui hain. Jaise ke:

- Emotional kahani sunana
- Social proof (reviews ya testimonials ka zikr)
- Urgency (limited time ya "abhi khareedain" ka lafz)
- Risk reversal (e.g. "agar pasand na aaye to paisay wapas")
- Viewer se direct connection ("aap ke liye", "aap jaise log")
- Mukabla ya farq dikhana (e.g. "doosri brands se behtar")

Bullets mein jawaab dein — sirf unhi cheezon ka zikr karein jo is transcript mein hain.

Transcript:
{text}""",
                "model": "gpt-4o",
                "temperature": 0.5,
                "max_tokens": None,
                "description": "Analyzes advertising transcripts for marketing techniques",
                "category": "analysis"
            },
            "product_extraction_transcript": {
                "prompt_key": "product_extraction_transcript",
                "prompt_name": "Product Extraction from Transcript",
                "prompt_text": """Analyze this advertisement transcript and extract the product information:

1. What is the exact product name being advertised? (Give the specific name/brand if mentioned, otherwise describe the product briefly)
2. What category does this product belong to? (e.g., islamic product, cosmetic, fashion, tech, food, health, education, clothing, jewelry, electronics, etc.)

Return only a JSON with "product" and "product_type" fields.

Transcript:
{text}""",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": None,
                "description": "Extracts product information from transcripts",
                "category": "analysis"
            },
            "frame_analysis": {
                "prompt_key": "frame_analysis",
                "prompt_name": "Frame Analysis",
                "prompt_text": "I want you to give me a single word that represents a characteristic of this advertising image to characterize it. Give me only the position of the person, and necessarily what they are doing (example: sitting with the object in their hands, standing explaining, crouching looking at the object) or a characteristic of the background (example: outside, package in the background, red background).",
                "model": "gpt-4o",
                "temperature": 0.4,
                "max_tokens": 50,
                "description": "Analyzes individual video frames for visual characteristics",
                "category": "analysis"
            },
            "product_extraction_frames": {
                "prompt_key": "product_extraction_frames",
                "prompt_name": "Product Extraction from Frames",
                "prompt_text": """Analyze these advertisement video frames and extract the product information:

1. What is the exact product name being advertised? (Look for any text, brand names, or product labels visible in the frames)
2. What category does this product belong to? (e.g., islamic product, cosmetic, fashion, tech, food, health, education, clothing, jewelry, electronics, etc.)

Return only a JSON with "product" and "product_type" fields.""",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": None,
                "description": "Extracts product information from video frames",
                "category": "analysis"
            },
            "ad_analysis": {
                "prompt_key": "ad_analysis",
                "prompt_name": "Ad Analysis",
                "prompt_text": """STEP 1: Analyze the ad insights below.

Ad Transcript Summary: {transcription}
Visual Summary: {visual_summary}

Now answer these clearly:
1. What is the **main hook line or pattern** used in this ad? Why did it work?
2. What is the **tone** of the ad (e.g., emotional, confident, hype)?
3. What **power phrases or emotional angles** stood out?
4. What **gestures, expressions, or camera angles or visual thing** were impactful?

Important: If you include any Urdu phrases, always write them in **Roman Urdu** (Urdu written in English script like 'agar pasand na aaye to paise wapas') instead of using Urdu script. Do NOT use Urdu alphabet or Nastaliq script.

Please reply in only the following JSON format:
{{"hook":"...","tone":"...","power_phrases":"...","visual":"..."}}""",
                "model": "gpt-4o",
                "temperature": 0.4,
                "max_tokens": None,
                "description": "Analyzes complete ads combining transcript and visual data",
                "category": "analysis"
            }
        }
        
        # Check if the prompt_key exists in our defaults
        if prompt_key not in all_default_prompts:
            logger.warning(f"No default prompt found for key: {prompt_key}")
            return False
        
        try:
            # Delete existing prompt if it exists
            await db.prompt_templates.delete_one({"prompt_key": prompt_key})
            
            # Create the default prompt
            prompt_data = all_default_prompts[prompt_key]
            template_create = PromptTemplateCreate(**prompt_data)
            await PromptTemplateService.create_prompt_template(template_create)
            
            logger.info(f"Reinitialized default prompt: {prompt_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reinitialize default prompt {prompt_key}: {e}")
            return False 