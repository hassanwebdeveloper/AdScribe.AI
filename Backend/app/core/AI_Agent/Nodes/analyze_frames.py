import os
import json
import base64
import logging
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client with settings
client = OpenAI(api_key=settings.openai_api_key)

def get_user_frame_analysis_dir(user_id: str) -> Path:
    """
    Create and return user-specific frame analysis directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific frame analysis directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/analyze_frames.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific frame analysis directory: Backend/frame_analysis_<user_id>/
    user_analysis_dir = backend_dir / f"frame_analysis_{user_id}"
    user_analysis_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using frame analysis directory: {user_analysis_dir}")
    return user_analysis_dir

# Prompt
ANALYSIS_PROMPT = (
    "I want you to give me a single word that represents a characteristic of this advertising image to characterize it. "
    "Give me only the position of the person, and necessarily what they are doing (example: sitting with the object in their hands, "
    "standing explaining, crouching looking at the object) or a characteristic of the background (example: outside, package in the background, red background)."
)

def encode_image_to_base64(image_path: Path) -> str:
    """
    Converts an image to a base64 encoded string.

    Args:
        image_path (Path): Path to the image file.

    Returns:
        str: Base64 encoded string of the image.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_frame(image_path: Path) -> str:
    """
    Analyzes a single frame using GPT-4o and returns the analysis result.

    Args:
        image_path (Path): Path to the image file to analyze.

    Returns:
        str: Analysis result for the image.
    """
    try:
        image_b64 = encode_image_to_base64(image_path)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                }
            ],
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[❌] Error analyzing {image_path.name}: {e}", exc_info=True)
        return "Error"

def analyze_frame_from_base64(frame_b64: str, frame_name: str) -> str:
    """
    Analyzes a single frame from base64 data using GPT-4o and returns the analysis result.

    Args:
        frame_b64 (str): Base64 encoded image data.
        frame_name (str): Name of the frame for logging.

    Returns:
        str: Analysis result for the image.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}}
                    ]
                }
            ],
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[❌] Error analyzing frame {frame_name}: {e}", exc_info=True)
        return "Error"

async def analyze_all_frames(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node to analyze all frames from extracted_frames state
    and skip videos that already have frame analysis.
    """
    frame_analysis_results = []

    extracted_frames = state.get("extracted_frames", [])
    user_id = state.get("user_id")
    
    if not extracted_frames:
        logger.warning("[⚠️] No extracted frames found in state. Skipping frame analysis.")
        return {"frame_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for frame analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific frame analysis directory
    analysis_dir = get_user_frame_analysis_dir(user_id)

    logger.info(f"[🎞️] Starting analysis of frames from {len(extracted_frames)} videos...")

    for frame_data in extracted_frames:
        try:
            video_name = frame_data.get("video", "")
            frames = frame_data.get("frames", [])
            
            if not video_name or not frames:
                logger.warning(f"[⚠️] Missing video name or frames in data: {frame_data}")
                continue

            # Use video name without extension as folder name
            folder_name = Path(video_name).stem
            output_path = analysis_dir / f"{folder_name}_analysis.json"

            # ✅ Skip if analysis file already exists
            if output_path.exists():
                logger.debug(f"[⏩] Skipping {folder_name} — already analyzed.")
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_analysis = json.load(f)
                frame_analysis_results.append({
                    "video": folder_name,
                    "analysis": existing_analysis
                })
                continue

            logger.info(f"[🎞️] Analyzing frames for: {folder_name}")
            analysis = {}

            for i, frame_b64 in enumerate(frames):
                frame_name = f"frame_{i+1}.jpg"
                logger.debug(f"[🧠] Analyzing: {frame_name}")
                result = analyze_frame_from_base64(frame_b64, frame_name)
                analysis[frame_name] = result

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)

            logger.info(f"[✅] Saved: {output_path.name}")
            frame_analysis_results.append({
                "video": folder_name,
                "analysis": analysis
            })

        except Exception as e:
            error_msg = f"Error processing frames for video {frame_data.get('video', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Note: accumulate errors but don't return early

    logger.info(f"[🎞️] Completed frame analysis for {len(frame_analysis_results)} videos")
    return {"frame_analysis": frame_analysis_results}



