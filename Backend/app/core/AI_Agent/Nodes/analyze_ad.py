import os
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

# Prompt template
AD_ANALYSIS_PROMPT = (
    "STEP 1: Analyze the ad insights below.\n\n"
    "Ad Transcript Summary: {transcription}\n"
    "Visual Summary: {visual_summary}\n\n"
    "Now answer these clearly:\n"
    "1. What is the **main hook line or pattern** used in this ad? Why did it work?\n"
    "2. What is the **tone** of the ad (e.g., emotional, confident, hype)?\n"
    "3. What **power phrases or emotional angles** stood out?\n"
    "4. What **gestures, expressions, or camera angles or visual thing** were impactful?\n\n"
    "Important: If you include any Urdu phrases, always write them in **Roman Urdu** (Urdu written in English script like 'agar pasand na aaye to paise wapas') instead of using Urdu script. Do NOT use Urdu alphabet or Nastaliq script.\n\n"
    "Please reply in only the following JSON format:\n"
    '{{\n  "hook":"...",\n  "tone":"...",\n  "power_phrases":"...",\n  "visual":"..."\n}}'
)

def clean_json_string(text: str) -> str:
    # Remove leading/trailing whitespace and code block markers
    text = text.strip().removeprefix("```json").removesuffix("```").strip()

    # Remove line breaks in values (e.g., caused by word-wrap)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)  # handle hyphenated breaks
    text = re.sub(r'\n+', ' ', text)             # replace remaining newlines with space

    # Strip trailing commas before closing braces
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    return text

async def analyze_combined_ad(transcription: str, visual_summary: str, cancellation_token=None) -> Dict[str, str]:
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled before ad analysis")
        return {}
        
    prompt = AD_ANALYSIS_PROMPT.format(
        transcription=transcription,
        visual_summary=visual_summary
    )
    
    try:
        # Use the robust OpenAI service with rate limiting
        messages = [{"role": "user", "content": prompt}]
        
        result = await openai_service._make_chat_completion(
            messages=messages,
            model="gpt-4o",
            temperature=0.4,
            cancellation_token=cancellation_token
        )
        
        if not result:
            return {}
        
        raw_text = result.strip()
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("[⚠️] Raw OpenAI response not valid JSON. Attempting cleanup...")
            cleaned = clean_json_string(raw_text)
            return json.loads(cleaned)
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info("Ad analysis cancelled")
            return {}
        else:
            logger.error(f"[❌] Final ad analysis error: {e}", exc_info=True)
            return {}
    except Exception as e:
        logger.error(f"[❌] Final ad analysis error: {e}", exc_info=True)
        return {}

async def final_ad_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    # Check for cancellation at the start
    cancellation_token = state.get("cancellation_token")
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled during final_ad_analysis")
        return {"errors": ["Job was cancelled"]}
    
    transcription_results = state.get("transcription_analysis", [])
    frame_results = state.get("frame_analysis", [])
    user_id = state.get("user_id")
    analyzed_video_ids = state.get("analyzed_video_ids", [])
    
    if not transcription_results or not frame_results:
        logger.warning("[⚠️] Missing inputs — skipping ad analysis.")
        return {"final_ad_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for ad analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    logger.info(f"[🧠] Starting final analysis for {len(transcription_results)} transcriptions and {len(frame_results)} frame analyses...")

    combined_results = []

    for i, transcript in enumerate(transcription_results):
        try:
            # Check for cancellation before each final analysis
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled during final analysis (transcript {i+1}/{len(transcription_results)})")
                return {"errors": ["Job was cancelled"]}
            
            video_id = transcript.get("video_id")
            video_name = Path(transcript.get("file", "")).stem
            transcript_text = transcript.get("analysis", "")
            
            if not video_id or not video_name or not transcript_text:
                logger.warning(f"[⚠️] Missing data in transcript: {transcript}")
                continue

            # Skip if already analyzed
            if video_id in analyzed_video_ids:
                logger.info(f"[⏩] Skipping {video_name} (already analyzed)")
                continue

            matching_frame = next(
                (item for item in frame_results if item.get("video_id") == video_id),
                None
            )
            
            if not matching_frame:
                logger.warning(f"[⚠️] No matching frame analysis found for video: {video_name}")
                continue

            visual_text = " | ".join(matching_frame.get("analysis", {}).values())
            logger.info(f"[🧠] Running final analysis for: {video_name}")
            
            # Check for cancellation before calling OpenAI API
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before final analysis of {video_name}")
                return {"errors": ["Job was cancelled"]}
            
            result = await analyze_combined_ad(transcript_text, visual_text, cancellation_token)

            if result:
                # Get product information from transcription and frame analysis
                transcription_product_info = transcript.get("product_info", {})
                frame_product_info = matching_frame.get("product_info", {})
                
                # Aggregate product information
                product_info = aggregate_product_info(transcription_product_info, frame_product_info)
                
                # Add product information to the result
                result.update(product_info)
                
                combined_results.append({
                    "video_id": video_id,
                    "video": video_name,
                    "final_analysis": result
                })
                logger.info(f"[✅] Completed analysis for: {video_name}")
            else:
                error_msg = f"Could not generate analysis for {video_name}"
                logger.error(error_msg)

        except Exception as e:
            error_msg = f"Error processing final analysis for {transcript.get('file', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[🧠] Completed final analysis for {len(combined_results)} videos")
    return {"final_ad_analysis": combined_results}

def aggregate_product_info(transcription_info: dict, frame_info: dict) -> dict:
    """
    Aggregate product information from transcription and frame analysis.
    Prioritize transcription data as it's more reliable for product names.
    """
    # Start with transcription product info
    product = transcription_info.get("product", "").strip()
    product_type = transcription_info.get("product_type", "").strip()
    
    # If transcription didn't find product info, use frame info
    if not product and frame_info.get("product"):
        product = frame_info.get("product", "").strip()
    
    if not product_type and frame_info.get("product_type"):
        product_type = frame_info.get("product_type", "").strip()   
    
    return {
        "product": product or "",
        "product_type": product_type or ""
    }
