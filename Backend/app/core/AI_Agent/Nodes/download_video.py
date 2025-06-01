import os
import httpx
import logging
from pathlib import Path
from typing import Dict, Any

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
    # Current: Backend/app/core/AI_Agent/Nodes/download_video.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific video directory: Backend/videos_<user_id>/
    user_video_dir = backend_dir / f"videos_{user_id}"
    user_video_dir.mkdir(exist_ok=True)
    
    logger.info(f"[📁] Using video directory: {user_video_dir}")
    return user_video_dir

def is_valid_mp4(file_path: Path) -> bool:
    """Check if the file exists and is a non-zero MP4 file."""
    return file_path.exists() and file_path.stat().st_size > 0 and file_path.suffix == ".mp4"

async def download_videos(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Downloads Facebook ad videos only if not already present in user-specific folder.
    
    Args:
        state (dict): LangGraph state, must include 'video_urls' and 'user_id'.

    Returns:
        dict: Updated state with 'downloaded_videos'.
    """
    video_list = state.get("video_urls", [])
    user_id = state.get("user_id")
    saved_paths = []

    if not video_list:
        logger.warning("[⚠️] No video URLs in state. Skipping download.")
        return {"downloaded_videos": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for video download"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific video directory
    user_video_dir = get_user_video_dir(user_id)

    async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for video downloads
        for video in video_list:
            video_id = video.get("video_id")
            source_url = video.get("source")

            if not video_id or not source_url:
                logger.debug(f"[SKIP] Missing data: video_id={video_id}, source_url={source_url}")
                continue

            # Skip if there was an error getting the video URL
            if "error" in video:
                logger.warning(f"[SKIP] Video {video_id} had error: {video['error']}")
                continue

            # Use user-specific directory for filename
            filename = user_video_dir / f"video_{video_id}.mp4"

            # --- Skip if already downloaded ---
            if is_valid_mp4(filename):
                logger.info(f"[✅] Video already exists, skipping download: {filename.name}")
                saved_paths.append(str(filename))
                continue

            # --- Download if not cached ---
            try:
                logger.info(f"[📥] Downloading video {video_id} to {user_video_dir.name}...")
                response = await client.get(source_url, timeout=60.0)
                response.raise_for_status()

                with open(filename, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

                # Verify the download
                if is_valid_mp4(filename):
                    logger.info(f"[💾] Successfully downloaded: {filename.name}")
                    saved_paths.append(str(filename))
                else:
                    logger.error(f"[❌] Downloaded file is invalid: {filename}")
                    # Clean up invalid file
                    if filename.exists():
                        filename.unlink()

            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error downloading video_id={video_id}: {e.response.status_code}"
                logger.error(error_msg)
                return {"errors": [error_msg]}
            except httpx.RequestError as e:
                error_msg = f"Request error downloading video_id={video_id}: {str(e)}"
                logger.error(error_msg)
                return {"errors": [error_msg]}
            except Exception as e:
                error_msg = f"Unexpected error downloading video_id={video_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"errors": [error_msg]}

    logger.info(f"[📁] Processed {len(saved_paths)} videos in user directory: {user_video_dir.name}")
    return {"downloaded_videos": saved_paths}
