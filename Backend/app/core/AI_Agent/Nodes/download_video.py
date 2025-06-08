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
    # Check for cancellation at the start (both mechanisms)
    cancellation_token = state.get("cancellation_token")
    if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
        logger.info("Job cancelled during download_videos")
        return {"errors": ["Job was cancelled"]}
    
    video_list = state.get("video_urls", [])
    user_id = state.get("user_id")
    progress_callback = state.get("progress_callback")
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
    
    if progress_callback:
        await progress_callback(50, f"Starting video downloads ({len(video_list)} videos)...")

    async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for video downloads
        for i, video in enumerate(video_list):
            # Check for cancellation before each video download (both mechanisms)
            if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                logger.info(f"Job cancelled during video download (video {i+1}/{len(video_list)})")
                return {"errors": ["Job was cancelled"]}
            
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
                
                # Report progress for skipped videos too
                if progress_callback:
                    download_progress = 50 + (i + 1) / len(video_list) * 25  # 50-75% range
                    await progress_callback(int(download_progress), f"Video {i + 1}/{len(video_list)} (cached)")
                continue

            # --- Download if not cached ---
            try:
                logger.info(f"[📥] Downloading video {video_id} to {user_video_dir.name}...")
                
                if progress_callback:
                    download_progress = 50 + i / len(video_list) * 25  # 50-75% range
                    await progress_callback(int(download_progress), f"Downloading video {i + 1}/{len(video_list)}...")
                
                # Check for cancellation before starting HTTP request (both mechanisms)
                if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                    logger.info(f"Job cancelled before starting download of {video_id}")
                    return {"errors": ["Job was cancelled"]}
                
                response = await client.get(source_url, timeout=30.0)
                response.raise_for_status()

                # Check for cancellation after getting response but before writing (both mechanisms)
                if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                    logger.info(f"Job cancelled after getting response for {video_id}")
                    return {"errors": ["Job was cancelled"]}

                chunk_count = 0
                with open(filename, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunk_count += 1
                        
                        # Check for cancellation every 5 chunks (roughly every 40KB) for more responsiveness
                        if chunk_count % 5 == 0:
                            if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                                logger.info(f"Job cancelled during video download of {video_id} (chunk {chunk_count})")
                                # Clean up partial file
                                if filename.exists():
                                    filename.unlink()
                                    logger.info(f"Cleaned up partial download: {filename}")
                                return {"errors": ["Job was cancelled"]}
                        
                        f.write(chunk)

                # Final cancellation check after download (both mechanisms)
                if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                    logger.info(f"Job cancelled after downloading {video_id}")
                    # Clean up the file since job was cancelled
                    if filename.exists():
                        filename.unlink()
                        logger.info(f"Cleaned up downloaded file: {filename}")
                    return {"errors": ["Job was cancelled"]}

                # Verify the download
                if is_valid_mp4(filename):
                    logger.info(f"[💾] Successfully downloaded: {filename.name}")
                    saved_paths.append(str(filename))
                    
                    if progress_callback:
                        download_progress = 50 + (i + 1) / len(video_list) * 25  # 50-75% range
                        await progress_callback(int(download_progress), f"Downloaded video {i + 1}/{len(video_list)}")
                else:
                    logger.error(f"[❌] Downloaded file is invalid: {filename}")
                    # Clean up invalid file
                    if filename.exists():
                        filename.unlink()

            except httpx.TimeoutException:
                # Check if this was due to cancellation (both mechanisms)
                if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                    logger.info(f"Download timeout for {video_id} - job was cancelled")
                    return {"errors": ["Job was cancelled"]}
                else:
                    error_msg = f"Timeout downloading video_id={video_id}"
                    logger.error(error_msg)
                    return {"errors": [error_msg]}
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
    
    if progress_callback:
        await progress_callback(75, f"Completed video downloads ({len(saved_paths)} videos)")
    
    return {"downloaded_videos": saved_paths}
