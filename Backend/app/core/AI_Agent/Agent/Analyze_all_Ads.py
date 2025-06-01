from langgraph.graph import StateGraph, END
from typing import Dict, Any, Annotated, List, Optional
from typing_extensions import TypedDict
import operator
from pathlib import Path
import logging
import asyncio
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Output directory
FINAL_OUTPUT_DIR = Path(__file__).resolve().parent / "ad_analysis"
FINAL_OUTPUT_DIR.mkdir(exist_ok=True)

# ---- Shared Graph State ----
class GraphState(TypedDict):
    # Input parameters (these are set once and not updated by nodes)
    user_id: str
    access_token: str
    account_id: str
    
    # Processing state (these can be updated by nodes)
    ads: Annotated[list, operator.add]
    video_urls: Annotated[list, operator.add]
    downloaded_videos: Annotated[list, operator.add]
    extracted_frames: Annotated[list, operator.add]
    transcriptions: Annotated[list, operator.add]
    transcription_analysis: Annotated[list, operator.add]
    frame_analysis: Annotated[list, operator.add]
    final_ad_analysis: Annotated[list, operator.add]
    
    # Error handling
    errors: Annotated[list, operator.add]

# ---- Import all nodes ----
from ..Nodes.get_ads import get_facebook_ads
from ..Nodes.get_video_urls import get_video_urls_from_ads
from ..Nodes.download_video import download_videos
from ..Nodes.transcribe_video import transcribe_all_videos
from ..Nodes.extract_frames import extract_all_videos_as_base64_frames
from ..Nodes.analyze_transcription import analyze_all_transcriptions
from ..Nodes.analyze_frames import analyze_all_frames
from ..Nodes.analyze_ad import final_ad_analysis

# ---- Build the Graph ----
def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("Get Facebook Ads", get_facebook_ads)
    builder.add_node("Get Video URLs", get_video_urls_from_ads)
    builder.add_node("Download Video", download_videos)
    builder.add_node("Transcribe Video", transcribe_all_videos)
    builder.add_node("Extract Frames", extract_all_videos_as_base64_frames)
    builder.add_node("Analyze Transcription", analyze_all_transcriptions)
    builder.add_node("Analyze Frames", analyze_all_frames)
    builder.add_node("Analyze Ad", final_ad_analysis)

    builder.set_entry_point("Get Facebook Ads")

    builder.add_edge("Get Facebook Ads", "Get Video URLs")
    builder.add_edge("Get Video URLs", "Download Video")
    builder.add_edge("Download Video", "Transcribe Video")
    builder.add_edge("Download Video", "Extract Frames")
    builder.add_edge("Transcribe Video", "Analyze Transcription")
    builder.add_edge("Extract Frames", "Analyze Frames")
    builder.add_edge("Analyze Transcription", "Analyze Ad")
    builder.add_edge("Analyze Frames", "Analyze Ad")
    builder.add_edge("Analyze Ad", END)

    return builder.compile()

# ---- Main execution function ----
async def run_ad_analysis_graph(
    user_id: str,
    access_token: str,
    account_id: str
) -> List[Dict[str, Any]]:
    """
    Run the ad analysis graph and return the results in the format expected by the database.
    
    Args:
        user_id: The user ID
        access_token: Facebook access token
        account_id: Facebook ad account ID
        
    Returns:
        List of ad analysis results in the format expected by the database
    """
    try:
        logger.info(f"[🚀] Starting Ad Analysis Graph for user {user_id}...")
        graph = build_graph()

        # Initialize state with required parameters
        initial_state = {
            "user_id": user_id,
            "access_token": access_token,
            "account_id": account_id,
            "ads": [],
            "video_urls": [],
            "downloaded_videos": [],
            "extracted_frames": [],
            "transcriptions": [],
            "transcription_analysis": [],
            "frame_analysis": [],
            "final_ad_analysis": [],
            "errors": []
        }

        # Start the graph execution
        final_state = await graph.ainvoke(initial_state)

        logger.info("[🎉] Workflow complete.")

        # Process results and convert to database format
        final_results = final_state.get("final_ad_analysis", [])
        ads_data = final_state.get("ads", [])
        video_urls_data = final_state.get("video_urls", [])
        
        # Convert results to the format expected by the database
        database_results = []
        
        for result in final_results:
            try:
                video_name = result.get("video", "")
                analysis = result.get("final_analysis", {})
                
                # Find corresponding ad and video data
                ad_data = None
                video_data = None
                
                # Match by video name/ID
                for video_info in video_urls_data:
                    if video_info.get("video_id") in video_name or video_name in str(video_info.get("video_id", "")):
                        video_data = video_info
                        # Find corresponding ad
                        for ad in ads_data:
                            if ad.get("id") == video_info.get("ad_id"):
                                ad_data = ad
                                break
                        break
                
                if not ad_data:
                    logger.warning(f"Could not find ad data for video {video_name}")
                    continue
                
                # Create the database record in the expected format
                db_record = {
                    "user_id": user_id,
                    "video_id": video_data.get("video_id") if video_data else None,
                    "ad_id": ad_data.get("id") if ad_data else None,
                    "campaign_id": ad_data.get("campaign", {}).get("id") if ad_data and "campaign" in ad_data else None,
                    "campaign_name": ad_data.get("campaign", {}).get("name") if ad_data and "campaign" in ad_data else None,
                    "adset_id": ad_data.get("adset", {}).get("id") if ad_data and "adset" in ad_data else None,
                    "adset_name": ad_data.get("adset", {}).get("name") if ad_data and "adset" in ad_data else None,
                    "adset_targeting": ad_data.get("adset", {}).get("targeting") if ad_data and "adset" in ad_data else None,
                    "ad_title": ad_data.get("name") if ad_data else None,
                    "ad_message": None,  # This would come from creative data if available
                    "ad_status": ad_data.get("status") if ad_data else None,
                    "video_url": video_data.get("source") or video_data.get("permalink_url") if video_data else None,
                    "audio_description": None,  # Will be filled from transcription analysis
                    "video_description": None,  # Will be filled from frame analysis
                    "ad_analysis": {
                        "hook": analysis.get("hook", ""),
                        "tone": analysis.get("tone", ""),
                        "power_phrases": analysis.get("power_phrases", ""),
                        "visual": analysis.get("visual", "")
                    },
                    "created_at": datetime.utcnow()
                }
                
                # Add transcription analysis as audio description
                transcription_data = final_state.get("transcription_analysis", [])
                for trans in transcription_data:
                    if video_name in trans.get("file", ""):
                        db_record["audio_description"] = trans.get("analysis", "")
                        break
                
                # Add frame analysis as video description
                frame_data = final_state.get("frame_analysis", [])
                for frame in frame_data:
                    if video_name in frame.get("video", ""):
                        frame_analysis = frame.get("analysis", {})
                        if isinstance(frame_analysis, dict):
                            db_record["video_description"] = " | ".join(frame_analysis.values())
                        else:
                            db_record["video_description"] = str(frame_analysis)
                        break
                
                database_results.append(db_record)
                
            except Exception as e:
                logger.error(f"Error processing result {result}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"[📌] Processed {len(database_results)} ad analyses")
        
        # Log any errors that occurred during processing
        errors = final_state.get("errors", [])
        if errors:
            logger.warning(f"[⚠️] {len(errors)} errors occurred during processing: {errors}")
        
        return database_results

    except Exception as e:
        logger.error(f"[❌] Error in ad analysis graph: {str(e)}", exc_info=True)
        raise

# ---- Legacy function for backward compatibility ----
def run_ad_analysis_graph_sync():
    """
    Legacy synchronous function for backward compatibility.
    This should not be used in the FastAPI context.
    """
    logger.warning("run_ad_analysis_graph_sync is deprecated. Use run_ad_analysis_graph instead.")
    return []

# ---- Visualize and save the graph structure ----
def visualize_graph():
    print("\n[🖼️] Visualizing graph structure...")

    try:
        graph = build_graph()
        png_bytes = graph.get_graph().draw_mermaid_png()
        output_path = FINAL_OUTPUT_DIR / "graph_output.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        print(f"[✅] Saved graph visualization to: {output_path}")
    except Exception as e:
        print(f"[❌] Graph visualization failed: {e}")
