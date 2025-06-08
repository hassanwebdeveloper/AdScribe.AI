import os
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

def get_user_video_dir(user_id: str) -> Path:
    """
    Create and return user-specific video directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific video directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/transcribe_video.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific video directory: Backend/videos_<user_id>/
    user_video_dir = backend_dir / f"videos_{user_id}"
    user_video_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using video directory: {user_video_dir}")
    return user_video_dir

async def transcribe_video(video_path: Path, cancellation_token=None) -> str:
    """
    Transcribes an Urdu video using Whisper via OpenAI service with rate limiting and error handling.
    """
    # Check for cancellation before making request
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info(f"Job cancelled before transcribing {video_path.name}")
        return None
        
    try:
        prompt = "This is a Pakistani Urdu advertisement. You may find words like Oud-al-abraj, outlet, purchase, online etc. Transcribe the spoken content in Urdu script."
        
        # Use the robust OpenAI service with rate limiting
        result = await openai_service._make_transcription(
            audio_file_path=str(video_path),
            model="whisper-1",
            language="ur",
            prompt=prompt,
            cancellation_token=cancellation_token
        )
        
        return result
    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info(f"Transcription cancelled for {video_path.name}")
            return None
        else:
            logger.error(f"❌ Failed to transcribe {video_path.name}: {e}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"❌ Failed to transcribe {video_path.name}: {e}", exc_info=True)
        return None

async def transcribe_all_videos(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node to transcribe all videos and return results in memory only.
    """
    # Check for cancellation at the start
    cancellation_token = state.get("cancellation_token")
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled during transcribe_all_videos")
        return {"errors": ["Job was cancelled"]}
    
    results = []
    video_paths = state.get("downloaded_videos", [])
    user_id = state.get("user_id")
    analyzed_video_ids = state.get("analyzed_video_ids", [])
    progress_callback = state.get("progress_callback")

    if not video_paths:
        logger.warning("[⚠️] No video paths found in state. Skipping transcription.")
        return {"transcriptions": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for transcription"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    logger.info(f"[🎙️] Starting transcription of {len(video_paths)} videos...")
    
    if progress_callback:
        await progress_callback(76, f"Starting video transcription ({len(video_paths)} videos)...")

    for i, video_file in enumerate(video_paths):
        try:
            # Check for cancellation before each transcription
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled during video transcription (video {i+1}/{len(video_paths)})")
                return {"errors": ["Job was cancelled"]}
            
            video_file = Path(video_file)
            
            # Extract video ID from filename (assuming format: video_{id}.mp4)
            video_id = video_file.stem.replace("video_", "")
            
            # Skip if already analyzed
            if video_id in analyzed_video_ids:
                logger.info(f"[⏩] Skipping {video_file.name} (already analyzed)")
                
                if progress_callback:
                    transcribe_progress = 76 + (i + 1) / len(video_paths) * 8  # 76-84% range
                    await progress_callback(int(transcribe_progress), f"Transcription {i + 1}/{len(video_paths)} (skipped)")
                continue

            logger.info(f"[🎙️] Transcribing: {video_file.name}")
            
            if progress_callback:
                transcribe_progress = 76 + i / len(video_paths) * 8  # 76-84% range
                await progress_callback(int(transcribe_progress), f"Transcribing video {i + 1}/{len(video_paths)}...")
            
            # Check for cancellation before starting transcription
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before transcribing {video_file.name}")
                return {"errors": ["Job was cancelled"]}
            
            text = await transcribe_video(video_file, cancellation_token)

            if text:
                results.append({
                    "video_id": video_id,
                    "file": video_file.name, 
                    "text": text
                })
                logger.info(f"[✅] Transcribed: {video_file.name}")
                
                if progress_callback:
                    transcribe_progress = 76 + (i + 1) / len(video_paths) * 8  # 76-84% range
                    await progress_callback(int(transcribe_progress), f"Transcribed video {i + 1}/{len(video_paths)}")
            else:
                error_msg = f"Failed to transcribe {video_file.name}"
                logger.error(error_msg)

        except Exception as e:
            error_msg = f"Error processing video {video_file}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[🎙️] Completed transcription of {len(results)} videos")
    
    if progress_callback:
        await progress_callback(84, f"Completed video transcription ({len(results)} videos)")
    
    return {"transcriptions": results}
