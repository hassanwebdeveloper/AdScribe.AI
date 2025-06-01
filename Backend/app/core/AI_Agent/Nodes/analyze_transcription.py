import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client with settings
client = OpenAI(api_key=settings.openai_api_key)

def get_user_transcription_analysis_dir(user_id: str) -> Path:
    """
    Create and return user-specific transcription analysis directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific transcription analysis directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/analyze_transcription.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific transcription analysis directory: Backend/transcription_analysis_<user_id>/
    user_analysis_dir = backend_dir / f"transcription_analysis_{user_id}"
    user_analysis_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using transcription analysis directory: {user_analysis_dir}")
    return user_analysis_dir

def analyze_transcript_text(text: str) -> str:
    """
    Sends transcription text to GPT for structured analysis (e.g. tone, hook, CTA).
    Returns a clean bullet list string.
    """
    prompt = f"""
Aap aik marketing strategist hain jo aik ad ki Urdu transcript ka jaiza le rahe hain. Aapko yeh batana hai ke is ad mein kon kon se selling techniques use hui hain. Jaise ke:

- Emotional kahani sunana
- Social proof (reviews ya testimonials ka zikr)
- Urgency (limited time ya "abhi khareedain" ka lafz)
- Risk reversal (e.g. "agar pasand na aaye to paisay wapas")
- Viewer se direct connection ("aap ke liye", "aap jaise log")
- Mukabla ya farq dikhana (e.g. "doosri brands se behtar")

Bullets mein jawaab dein — sirf unhi cheezon ka zikr karein jo is transcript mein hain.

Transcript:
{text}
"""

    system_prompt = "You are a helpful assistant that gives only keywords as a return, in English, with one point per line using dashes. Do not include markdown or JSON."

    try:

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ Error analyzing transcription: {e}", exc_info=True)
        return None

async def analyze_all_transcriptions(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node that analyzes each transcription in state["transcriptions"]
    and saves analysis as plain .txt file (one per transcription).
    """
    results = []
    transcriptions = state.get("transcriptions", [])
    user_id = state.get("user_id")

    if not transcriptions:
        logger.warning("[⚠️] No transcriptions found in state. Skipping analysis.")
        return {"transcription_analysis": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for transcription analysis"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific transcription analysis directory
    analysis_dir = get_user_transcription_analysis_dir(user_id)

    logger.info(f"[🧠] Starting analysis of {len(transcriptions)} transcriptions...")

    for item in transcriptions:
        try:
            filename = item.get("file")
            text = item.get("text")

            if not filename or not text:
                logger.warning(f"[⚠️] Missing data in item: {item}")
                continue

            analysis_path = analysis_dir / f"{Path(filename).stem}_analysis.txt"
            if analysis_path.exists():
                logger.debug(f"[⏩] Skipping {filename} (already analyzed)")
                with open(analysis_path, "r", encoding="utf-8") as f:
                    analysis = f.read()
                results.append({
                    "file": filename,
                    "analysis": analysis
                })
                continue

            logger.info(f"[🧠] Analyzing transcription: {filename}")
            analysis_text = analyze_transcript_text(text)

            if analysis_text:
                with open(analysis_path, "w", encoding="utf-8") as f:
                    f.write(analysis_text)
                logger.info(f"[✅] Saved analysis: {analysis_path.name}")
                results.append({
                    "file": filename,
                    "analysis": analysis_text
                })
            else:
                error_msg = f"Failed to analyze transcription for {filename}"
                logger.error(error_msg)
                # Note: accumulate errors but don't return early

        except Exception as e:
            error_msg = f"Error processing transcription {item.get('file', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Note: accumulate errors but don't return early

    logger.info(f"[🧠] Completed analysis of {len(results)} transcriptions")
    return {"transcription_analysis": results}
