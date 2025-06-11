import os
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.openai_service import openai_service
from app.services.dynamic_prompt_service import dynamic_prompt_service

logger = logging.getLogger(__name__)

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

async def analyze_frame(image_path: Path) -> str:
    """
    Analyzes a single frame using dynamic prompt service and returns the analysis result.

    Args:
        image_path (Path): Path to the image file to analyze.

    Returns:
        str: Analysis result for the image.
    """
    try:
        image_b64 = encode_image_to_base64(image_path)
        
        # Get the prompt text from dynamic prompt service
        prompt_text, model, temperature, max_tokens = await dynamic_prompt_service.get_prompt_and_settings("frame_analysis")
        
        if not prompt_text:
            prompt_text = "I want you to give me a single word that represents a characteristic of this advertising image to characterize it. Give me only the position of the person, and necessarily what they are doing (example: sitting with the object in their hands, standing explaining, crouching looking at the object) or a characteristic of the background (example: outside, package in the background, red background)."
        
        # Use dynamic prompt service client
        response = await dynamic_prompt_service.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                }
            ],
            max_tokens=max_tokens or 50,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[❌] Error analyzing {image_path.name}: {e}", exc_info=True)
        return "Error"

async def analyze_frame_from_base64(frame_b64: str, frame_name: str, cancellation_token=None) -> str:
    """
    Analyzes a single frame from base64 data using dynamic prompt service.

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
        # Get the prompt text from dynamic prompt service
        prompt_text, model, temperature, max_tokens = await dynamic_prompt_service.get_prompt_and_settings("frame_analysis")
        
        if not prompt_text:
            prompt_text = "I want you to give me a single word that represents a characteristic of this advertising image to characterize it. Give me only the position of the person, and necessarily what they are doing (example: sitting with the object in their hands, standing explaining, crouching looking at the object) or a characteristic of the background (example: outside, package in the background, red background)."
        
        # Use the robust OpenAI service with rate limiting
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}}
                ]
            }
        ]
        
        result = await openai_service._make_chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens or 50,
            temperature=temperature,
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

            # Keep track of seen results to avoid duplicates
            seen_results = set()
            
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
                
                # Only include result if we haven't seen it before
                if result not in seen_results:
                    analysis[frame_name] = result
                    seen_results.add(result)

            logger.info(f"[✅] Analyzed frames for: {folder_name}")
            
            # Also extract product information from the frames
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before product extraction for {folder_name}")
                return {"errors": ["Job was cancelled"]}
            
            product_info = await extract_product_from_frames(frames, folder_name, cancellation_token)
            
            frame_analysis_results.append({
                "video_id": video_id,
                "video": folder_name,
                "analysis": analysis,
                "product_info": product_info  # Add product information
            })

        except Exception as e:
            error_msg = f"Error processing frames for video {frame_data.get('video', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[🎞️] Completed frame analysis for {len(frame_analysis_results)} videos")
    return {"frame_analysis": frame_analysis_results}

async def extract_product_from_frames(frames: list, video_name: str, cancellation_token=None) -> dict:
    """
    Extract product name and product type from the video frames.
    """
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info(f"Job cancelled before product extraction from frames for {video_name}")
        return {"product": "", "product_type": ""}
    
    if not frames:
        return {"product": "", "product_type": ""}
    
    # Use the first few frames for product analysis (max 3 to avoid too many API calls)
    sample_frames = frames
    
    try:
        # Get the prompt text from dynamic prompt service
        prompt_text, model, temperature, max_tokens = await dynamic_prompt_service.get_prompt_and_settings("product_extraction_frames")
        
        if not prompt_text:
            prompt_text = """Analyze these advertisement video frames and extract the product information:

1. What is the exact product name being advertised? (Look for any text, brand names, or product labels visible in the frames)
2. What category does this product belong to? (e.g., islamic product, cosmetic, fashion, tech, food, health, education, clothing, jewelry, electronics, etc.)

Return only a JSON with "product" and "product_type" fields."""
        
        # Prepare messages with multiple frames
        message_content = [{"type": "text", "text": prompt_text}]
        
        for i, frame_b64 in enumerate(sample_frames):
            message_content.append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}
            })
        
        messages = [{"role": "user", "content": message_content}]
        
        result = await openai_service._make_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            cancellation_token=cancellation_token
        )
        
        if result:
            try:
                import json
                # Clean the result if it has markdown formatting
                cleaned_result = result.strip().removeprefix("```json").removesuffix("```").strip()
                product_info = json.loads(cleaned_result)
                return {
                    "product": product_info.get("product", ""),
                    "product_type": product_info.get("product_type", "")
                }
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse product JSON from frames: {result}")
                return {"product": "", "product_type": ""}
        else:
            return {"product": "", "product_type": ""}
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info(f"Product extraction from frames cancelled for {video_name}")
            return {"product": "", "product_type": ""}
        else:
            logger.error(f"❌ Error extracting product from frames for {video_name}: {e}", exc_info=True)
            return {"product": "", "product_type": ""}
    except Exception as e:
        logger.error(f"❌ Error extracting product from frames for {video_name}: {e}", exc_info=True)
        return {"product": "", "product_type": ""}



