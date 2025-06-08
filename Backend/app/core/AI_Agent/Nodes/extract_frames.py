import cv2
import base64
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

def convert_frame_to_base64(frame):
    """Converts an OpenCV frame to Base64-encoded string."""
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return None
    return base64.b64encode(buffer).decode('utf-8')

def extract_evenly_distributed_frames_from_video(video_path: Path, max_frames: int = 5) -> list[str]:
    """
    Extracts up to `max_frames` evenly distributed frames from a video.
    Returns a list of Base64-encoded JPEG images.
    """
    capture = cv2.VideoCapture(str(video_path))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames == 0:
        logger.warning(f"[⚠️] No frames in video: {video_path.name}")
        capture.release()
        return []

    step = max(1, total_frames // max_frames)
    base64_frames = []

    try:
        for i in range(0, total_frames, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = capture.read()

            if ret:
                frame_b64 = convert_frame_to_base64(frame)
                if frame_b64:
                    base64_frames.append(frame_b64)

            if len(base64_frames) >= max_frames:
                break

    except Exception as e:
        logger.error(f"Error extracting frames from {video_path.name}: {e}", exc_info=True)
    finally:
        capture.release()

    return base64_frames

async def extract_all_videos_as_base64_frames(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node to extract frames from all videos and return frames in memory only.
    """
    # Check for cancellation at the start
    cancellation_token = state.get("cancellation_token")
    if cancellation_token and cancellation_token.get("cancelled", False):
        logger.info("Job cancelled during extract_all_videos_as_base64_frames")
        return {"errors": ["Job was cancelled"]}
    
    results = []
    video_paths = state.get("downloaded_videos", [])
    user_id = state.get("user_id")
    analyzed_video_ids = state.get("analyzed_video_ids", [])

    if not video_paths:
        logger.warning("[⚠️] No video paths found in state. Skipping frame extraction.")
        return {"extracted_frames": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for frame extraction"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    logger.info(f"[📽️] Starting frame extraction from {len(video_paths)} videos...")

    for i, video_file in enumerate(video_paths):
        try:
            # Check for cancellation before each video
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled during frame extraction (video {i+1}/{len(video_paths)})")
                return {"errors": ["Job was cancelled"]}
            
            video_file = Path(video_file)
            
            # Extract video ID from filename (assuming format: video_{id}.mp4)
            video_id = video_file.stem.replace("video_", "")
            
            # Skip if already analyzed
            if video_id in analyzed_video_ids:
                logger.info(f"[⏩] Skipping {video_file.name} (already analyzed)")
                continue

            logger.info(f"[📽️] Extracting frames from {video_file.name}")
            
            # Check for cancellation before starting frame extraction
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info(f"Job cancelled before extracting frames from {video_file.name}")
                return {"errors": ["Job was cancelled"]}
            
            frames_b64 = extract_evenly_distributed_frames_from_video(video_file)

            if frames_b64:
                results.append({
                    "video_id": video_id,
                    "video": video_file.name,
                    "frames": frames_b64
                })
                logger.info(f"[✅] Extracted {len(frames_b64)} frames from {video_file.name}")
            else:
                error_msg = f"No frames extracted from {video_file.name}"
                logger.warning(error_msg)

        except Exception as e:
            error_msg = f"Error processing video {video_file}: {str(e)}"
            logger.error(error_msg, exc_info=True)

    logger.info(f"[📽️] Completed frame extraction from {len(results)} videos")
    return {"extracted_frames": results}
