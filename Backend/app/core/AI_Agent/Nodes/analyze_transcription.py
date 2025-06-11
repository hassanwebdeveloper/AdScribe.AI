import os
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.openai_service import openai_service
from app.services.dynamic_prompt_service import dynamic_prompt_service

logger = logging.getLogger(__name__)

async def analyze_transcript_text(text: str, cancellation_token=None) -> str:
    """
    Sends transcription text to GPT for structured analysis using dynamic prompt service.
    Returns a clean bullet list string.
    """
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled before transcription analysis")
        return None

    try:
        # Use dynamic prompt service for transcription analysis
        prompt_variables = {"text": text}
        
        result = await dynamic_prompt_service.make_chat_completion(
            prompt_key="transcription_analysis",
            prompt_variables=prompt_variables
        )
        
        return result.strip() if result else None
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info("Transcription analysis cancelled")
            return None
        else:
            logger.error(f"❌ Error analyzing transcription: {e}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"❌ Error analyzing transcription: {e}", exc_info=True)
        return None

async def extract_product_from_transcript(text: str, cancellation_token=None) -> dict:
    """
    Extract product name and product type from the transcription text.
    """
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled before product extraction from transcript")
        return {"product": "", "product_type": ""}
        
    try:
        # Use dynamic prompt service for product extraction
        prompt_variables = {"text": text}
        
        result = await dynamic_prompt_service.make_chat_completion(
            prompt_key="product_extraction_transcript",
            prompt_variables=prompt_variables
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
                logger.warning(f"Failed to parse product JSON: {result}")
                return {"product": "", "product_type": ""}
        else:
            return {"product": "", "product_type": ""}
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info("Product extraction from transcript cancelled")
            return {"product": "", "product_type": ""}
        else:
            logger.error(f"❌ Error extracting product from transcript: {e}", exc_info=True)
            return {"product": "", "product_type": ""}
    except Exception as e:
        logger.error(f"❌ Error extracting product from transcript: {e}", exc_info=True)
        return {"product": "", "product_type": ""}

async def analyze_all_transcriptions(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node that analyzes each transcription and returns results in memory only.
    """
    # Check for cancellation at the start
    cancellation_token = state.get("cancellation_token")
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled during analyze_all_transcriptions")
        return {"errors": ["Job was cancelled"]}
    
    results = []
    transcriptions = state.get("transcriptions", [])
    user_id = state.get("user_id")
    analyzed_video_ids = state.get("analyzed_video_ids", [])

    if not transcriptions:
        logger.warning("[⚠️] No transcriptions found in state. Skipping analysis.")
        return {"transcription_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for transcription analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    logger.info(f"[🧠] Starting analysis of {len(transcriptions)} transcriptions...")

    for i, item in enumerate(transcriptions):
        try:
            # Check for cancellation before each transcription analysis
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled during transcription analysis (item {i+1}/{len(transcriptions)})")
                return {"errors": ["Job was cancelled"]}
            
            video_id = item.get("video_id")
            filename = item.get("file")
            text = item.get("text")

            if not video_id or not filename or not text:
                logger.warning(f"[⚠️] Missing data in item: {item}")
                continue

            # Skip if already analyzed
            if video_id in analyzed_video_ids:
                logger.info(f"[⏩] Skipping {filename} (already analyzed)")
                continue

            logger.info(f"[🧠] Analyzing transcription: {filename}")
            
            # Check for cancellation before calling OpenAI API
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before analyzing transcription {filename}")
                return {"errors": ["Job was cancelled"]}
            
            analysis_text = await analyze_transcript_text(text, cancellation_token)
            
            # Also extract product information from the transcription
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before product extraction for {filename}")
                return {"errors": ["Job was cancelled"]}
            
            product_info = await extract_product_from_transcript(text, cancellation_token)

            if analysis_text:
                results.append({
                    "video_id": video_id,
                    "file": filename,
                    "analysis": analysis_text,
                    "product_info": product_info  # Add product information
                })
                logger.info(f"[✅] Analyzed transcription and extracted product info: {filename}")
            else:
                error_msg = f"Failed to analyze transcription for {filename}"
                logger.error(error_msg)

        except Exception as e:
            error_msg = f"Error processing transcription {item.get('file', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[🧠] Completed analysis of {len(results)} transcriptions")
    return {"transcription_analysis": results}
