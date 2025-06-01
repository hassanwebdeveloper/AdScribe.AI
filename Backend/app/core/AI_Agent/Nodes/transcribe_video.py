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

def get_user_transcript_dir(user_id: str) -> Path:
    """
    Create and return user-specific transcript directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific transcript directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/transcribe_video.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific transcript directory: Backend/transcripts_<user_id>/
    user_transcript_dir = backend_dir / f"transcripts_{user_id}"
    user_transcript_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using transcript directory: {user_transcript_dir}")
    return user_transcript_dir

def transcribe_video(video_path: Path) -> str:
    """
    Transcribes an Urdu video using Whisper and returns the transcription text.
    """
    try:

        with open(video_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=f,
                # language="ur",
                prompt="This is a Pakistani Urdu advertisement. You may find words like Oud-al-abraj, outlet, purchase, online etc. Transcribe the spoken content in Urdu script."
            )
        return response.text.strip()
    except Exception as e:
        logger.error(f"❌ Failed to transcribe {video_path.name}: {e}", exc_info=True)
        return None

async def transcribe_all_videos(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node to transcribe all videos and update the state with results.
    """
    results = []
    video_paths = state.get("downloaded_videos", [])
    user_id = state.get("user_id")

    if not video_paths:
        logger.warning("[⚠️] No video paths found in state. Skipping transcription.")
        return {"transcriptions": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for transcription"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific transcript directory
    transcript_dir = get_user_transcript_dir(user_id)

    logger.info(f"[🎙️] Starting transcription of {len(video_paths)} videos...")

    for video_file in video_paths:
        try:
            video_file = Path(video_file)
            transcript_path = transcript_dir / f"{video_file.stem}.txt"

            if transcript_path.exists():
                logger.debug(f"[⏩] Skipping {video_file.name} (already transcribed)")
                with open(transcript_path, "r", encoding="utf-8") as f:
                    results.append({
                        "file": video_file.name,
                        "text": f.read().strip()
                    })
                continue

            logger.info(f"[🎙️] Transcribing: {video_file.name}")
            text = transcribe_video(video_file)

            if text:
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"[✅] Saved transcription: {transcript_path.name}")
                results.append({"file": video_file.name, "text": text})
            else:
                error_msg = f"Failed to transcribe {video_file.name}"
                logger.error(error_msg)
                # Note: accumulate errors but don't return early

        except Exception as e:
            error_msg = f"Error processing video {video_file}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Note: accumulate errors but don't return early

    logger.info(f"[🎙️] Completed transcription of {len(results)} videos")
    return {"transcriptions": results}
