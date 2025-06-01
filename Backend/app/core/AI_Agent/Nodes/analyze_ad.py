import os
import json
import re
import logging
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client with settings
client = OpenAI(api_key=settings.openai_api_key)

def get_user_ad_analysis_dir(user_id: str) -> Path:
    """
    Create and return user-specific ad analysis directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific ad analysis directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/analyze_ad.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific ad analysis directory: Backend/ad_analysis_<user_id>/
    user_analysis_dir = backend_dir / f"ad_analysis_{user_id}"
    user_analysis_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using ad analysis directory: {user_analysis_dir}")
    return user_analysis_dir

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

def analyze_combined_ad(transcription: str, visual_summary: str) -> Dict[str, str]:
    prompt = AD_ANALYSIS_PROMPT.format(
        transcription=transcription,
        visual_summary=visual_summary
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        raw_text = response.choices[0].message.content or ""
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("[⚠️] Raw OpenAI response not valid JSON. Attempting cleanup...")
            cleaned = clean_json_string(raw_text)
            return json.loads(cleaned)
    except Exception as e:
        logger.error(f"[❌] Final ad analysis error: {e}", exc_info=True)
        return {}

async def final_ad_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    transcription_results = state.get("transcription_analysis", [])
    frame_results = state.get("frame_analysis", [])
    user_id = state.get("user_id")
    
    if not transcription_results or not frame_results:
        logger.warning("[⚠️] Missing inputs — skipping ad analysis.")
        return {"final_ad_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for ad analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific ad analysis directory
    ad_analysis_dir = get_user_ad_analysis_dir(user_id)

    logger.info(f"[🧠] Starting final analysis for {len(transcription_results)} transcriptions and {len(frame_results)} frame analyses...")

    combined_results = []

    for transcript in transcription_results:
        try:
            video_name = Path(transcript.get("file", "")).stem
            transcript_text = transcript.get("analysis", "")
            
            if not video_name or not transcript_text:
                logger.warning(f"[⚠️] Missing video name or transcript text in: {transcript}")
                continue

            matching_frame = next(
                (item for item in frame_results if Path(item.get("video", "")).stem == video_name),
                None
            )
            
            if not matching_frame:
                logger.warning(f"[⚠️] No matching frame analysis found for video: {video_name}")
                continue

            visual_text = " | ".join(matching_frame.get("analysis", {}).values())
            logger.info(f"[🧠] Running final analysis for: {video_name}")
            
            result = analyze_combined_ad(transcript_text, visual_text)

            if result:
                output_path = ad_analysis_dir / f"{video_name}_final.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"[✅] Saved: {output_path.name}")
                combined_results.append({
                    "video": video_name,
                    "final_analysis": result
                })
            else:
                error_msg = f"Could not generate analysis for {video_name}"
                logger.error(error_msg)
                # Note: accumulate errors but don't return early

        except Exception as e:
            error_msg = f"Error processing final analysis for {transcript.get('file', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Note: accumulate errors but don't return early

    logger.info(f"[🧠] Completed final analysis for {len(combined_results)} videos")
    return {"final_ad_analysis": combined_results}
