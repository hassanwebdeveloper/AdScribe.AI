import os
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

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

async def analyze_frame_from_base64(frame_b64: str, frame_name: str, cancellation_token=None) -> str:
    """
    Analyzes a single frame from base64 data using OpenAI service with rate limiting.

    Args:
        frame_b64 (str): Base64 encoded image data.
        frame_name (str): Name of the frame for logging.
        cancellation_token: Cancellation token to check for job cancellation.

    Returns:
        str: Analysis result for the image.
    """
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info(f"Job cancelled before analyzing frame {frame_name}")
        return "Cancelled"
        
    try:
        # Use the robust OpenAI service with rate limiting
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}}
                ]
            }
        ]
        
        result = await openai_service._make_chat_completion(
            messages=messages,
            model="gpt-4o",
            max_tokens=50,
            cancellation_token=cancellation_token
        )
        
        return result.strip() if result else "Error"
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info(f"Frame analysis cancelled for {frame_name}")
            return "Cancelled"
        else:
            logger.error(f"[❌] Error analyzing frame {frame_name}: {e}", exc_info=True)
            return "Error"
    except Exception as e:
        logger.error(f"[❌] Error analyzing frame {frame_name}: {e}", exc_info=True)
        return "Error"

async def analyze_all_frames(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node to analyze all frames and return analysis in memory only.
    """
    # Check for cancellation at the start
    cancellation_token = state.get("cancellation_token")
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled during analyze_all_frames")
        return {"errors": ["Job was cancelled"]}
    
    frame_analysis_results = []

    extracted_frames = state.get("extracted_frames", [])
    user_id = state.get("user_id")
    analyzed_video_ids = state.get("analyzed_video_ids", [])
    
    if not extracted_frames:
        logger.warning("[⚠️] No extracted frames found in state. Skipping frame analysis.")
        return {"frame_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for frame analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    logger.info(f"[🎞️] Starting analysis of frames from {len(extracted_frames)} videos...")

    for j, frame_data in enumerate(extracted_frames):
        try:
            # Check for cancellation before each video
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled during frame analysis (video {j+1}/{len(extracted_frames)})")
                return {"errors": ["Job was cancelled"]}
            
            video_id = frame_data.get("video_id")
            video_name = frame_data.get("video", "")
            frames = frame_data.get("frames", [])
            
            if not video_id or not video_name or not frames:
                logger.warning(f"[⚠️] Missing data in frame_data: {frame_data}")
                continue

            # Skip if already analyzed
            if video_id in analyzed_video_ids:
                logger.info(f"[⏩] Skipping {video_name} (already analyzed)")
                continue

            # Use video name without extension as folder name
            folder_name = Path(video_name).stem

            logger.info(f"[🎞️] Analyzing frames for: {folder_name}")
            analysis = {}

            for i, frame_b64 in enumerate(frames):
                # Check for cancellation before each frame
                if cancellation_token and cancellation_token.get("cancelled", False):
                    logger.info(f"Job cancelled during frame analysis (frame {i+1}/{len(frames)} of {folder_name})")
                    return {"errors": ["Job was cancelled"]}
                
                frame_name = f"frame_{i+1}.jpg"
                logger.debug(f"[🧠] Analyzing: {frame_name}")
                
                # Check for cancellation before calling OpenAI API
                if cancellation_token and cancellation_token.get("cancelled", False):
                    logger.info(f"Job cancelled before analyzing frame {frame_name} of {folder_name}")
                    return {"errors": ["Job was cancelled"]}
                
                result = await analyze_frame_from_base64(frame_b64, frame_name, cancellation_token)
                analysis[frame_name] = result

            logger.info(f"[✅] Analyzed frames for: {folder_name}")
            frame_analysis_results.append({
                "video_id": video_id,
                "video": folder_name,
                "analysis": analysis
            })

        except Exception as e:
            error_msg = f"Error processing frames for video {frame_data.get('video', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[🎞️] Completed frame analysis for {len(frame_analysis_results)} videos")
    return {"frame_analysis": frame_analysis_results}



