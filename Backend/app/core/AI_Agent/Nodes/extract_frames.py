import cv2
import base64
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

def get_user_frames_dir(user_id: str) -> Path:
    """
    Create and return user-specific frames directory outside the app folder.
    
    Args:
        user_id (str): The user ID
        
    Returns:
        Path: User-specific frames directory path
    """
    # Get the Backend directory (4 levels up from current file)
    # Current: Backend/app/core/AI_Agent/Nodes/extract_frames.py
    # Target:  Backend/
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    
    # Create user-specific frames directory: Backend/frames_<user_id>/
    user_frames_dir = backend_dir / f"frames_{user_id}"
    user_frames_dir.mkdir(exist_ok=True)
    
    logger.debug(f"[📁] Using frames directory: {user_frames_dir}")
    return user_frames_dir

def convert_frame_to_base64(frame):
    """Converts an OpenCV frame to Base64-encoded string."""
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return None
    return base64.b64encode(buffer).decode('utf-8')

def extract_evenly_distributed_frames_from_video(video_path: Path, user_frames_dir: Path, max_frames: int = 5) -> list[str]:
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

    output_dir = user_frames_dir / video_path.stem

    if output_dir.exists() and any(output_dir.glob("*.jpg")):
        logger.debug(f"[✔️] Frames already extracted for {video_path.name}, loading existing frames.")
        # Load existing frames and convert to base64
        for frame_file in sorted(output_dir.glob("*.jpg"))[:max_frames]:
            try:
                frame = cv2.imread(str(frame_file))
                if frame is not None:
                    frame_b64 = convert_frame_to_base64(frame)
                    if frame_b64:
                        base64_frames.append(frame_b64)
            except Exception as e:
                logger.warning(f"Error loading existing frame {frame_file}: {e}")
        capture.release()
        return base64_frames

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for i in range(0, total_frames, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = capture.read()

            if ret:
                frame_path = output_dir / f"frame_{len(base64_frames) + 1}.jpg"
                cv2.imwrite(str(frame_path), frame)

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
    LangGraph-compatible node to extract frames from all videos in downloaded_videos
    and return the frames as Base64-encoded strings.
    """
    results = []
    video_paths = state.get("downloaded_videos", [])
    user_id = state.get("user_id")

    if not video_paths:
        logger.warning("[⚠️] No video paths found in state. Skipping frame extraction.")
        return {"extracted_frames": []}
    
    if not user_id:
        error_msg = "Missing user_id in state for frame extraction"
        logger.error(error_msg)
        return {"errors": [error_msg]}

    # Get user-specific frames directory
    user_frames_dir = get_user_frames_dir(user_id)

    logger.info(f"[📽️] Starting frame extraction from {len(video_paths)} videos...")

    for video_file in video_paths:
        try:
            video_file = Path(video_file)

            logger.info(f"[📽️] Extracting frames from {video_file.name}")
            frames_b64 = extract_evenly_distributed_frames_from_video(video_file, user_frames_dir)

            if frames_b64:
                results.append({
                    "video": video_file.name,
                    "frames": frames_b64
                })
                logger.info(f"[✅] Extracted {len(frames_b64)} frames from {video_file.name}")
            else:
                error_msg = f"No frames extracted from {video_file.name}"
                logger.warning(error_msg)
                # Note: accumulate errors but don't return early

        except Exception as e:
            error_msg = f"Error processing video {video_file}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Note: accumulate errors but don't return early

    logger.info(f"[📽️] Completed frame extraction from {len(results)} videos")
    return {"extracted_frames": results}
