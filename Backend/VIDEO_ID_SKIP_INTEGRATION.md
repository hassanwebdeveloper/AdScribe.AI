# Video ID Skip Integration

This document explains the implementation of database-driven video ID skipping to avoid re-analysis of already processed videos.

## Overview

The AI Agent now integrates with the database to:
1. **Fetch already analyzed video IDs** before starting analysis
2. **Skip re-processing** of videos that have already been analyzed  
3. **Save processing time and resources** by avoiding duplicate work
4. **Maintain data consistency** by preventing duplicate entries

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Endpoint  │    │   AI Agent      │    │   Database      │
│   /analyze/     │───▶│   Service       │───▶│   Query         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   LangGraph     │    │   ad_analyses   │
                       │   Workflow      │    │   Collection    │
                       └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Skip Logic in  │
                       │  All Node Types │
                       └─────────────────┘
```

## Implementation Details

### 1. Database Query Function

**File:** `Backend/app/services/ai_agent_service.py`

```python
async def get_analyzed_video_ids(self, user_id: str) -> List[str]:
    """
    Fetch list of video IDs that have already been analyzed for the user.
    
    Args:
        user_id: The user ID to fetch analyzed video IDs for
        
    Returns:
        List of video IDs that are already analyzed
    """
    # Query the ad_analyses collection for this user
    cursor = self.db.ad_analyses.find(
        {"user_id": user_id},
        {"video_id": 1, "_id": 0}  # Only return video_id field
    )
    
    analyses = await cursor.to_list(length=None)
    
    # Extract video IDs, filtering out None/empty values
    video_ids = [
        analysis["video_id"] 
        for analysis in analyses 
        if analysis.get("video_id") is not None and analysis.get("video_id").strip()
    ]
    
    # Remove duplicates while preserving order
    unique_video_ids = list(dict.fromkeys(video_ids))
    
    return unique_video_ids
```

**Key Features:**
- ✅ **User-specific queries** - Only fetches video IDs for the specific user
- ✅ **Efficient projection** - Only retrieves `video_id` field to minimize data transfer
- ✅ **Null filtering** - Removes None/empty video IDs
- ✅ **Duplicate removal** - Ensures unique video IDs while preserving order
- ✅ **Error handling** - Returns empty list on errors to avoid breaking the flow

### 2. Updated AI Agent Service

**File:** `Backend/app/services/ai_agent_service.py`

```python
async def analyze_ads_with_ai_agent(
    self, 
    user_id: str, 
    access_token: str, 
    account_id: str
) -> List[Dict[str, Any]]:
    """
    Run AI Agent analysis with database integration.
    Fetches already analyzed video IDs and skips re-analysis.
    """
    
    # Fetch already analyzed video IDs from database
    analyzed_video_ids = await self.get_analyzed_video_ids(user_id)
    logger.info(f"Will skip {len(analyzed_video_ids)} already analyzed videos")
    
    # Run the AI Agent with analyzed video IDs to skip
    analysis_results = await run_ad_analysis_graph(
        user_id=user_id,
        access_token=access_token,
        account_id=account_id,
        analyzed_video_ids=analyzed_video_ids  # Pass the analyzed video IDs
    )
```

**Key Changes:**
- ✅ **Database integration** - Fetches analyzed video IDs before running AI Agent
- ✅ **Parameter passing** - Sends analyzed video IDs list to the LangGraph workflow
- ✅ **Logging** - Tracks how many videos are being skipped
- ✅ **Double-check** - Additional validation before storing new results

### 3. LangGraph State Integration

**File:** `Backend/app/core/AI_Agent/Agent/Analyze_all_Ads.py`

```python
class GraphState(TypedDict):
    # Input parameters
    user_id: str
    access_token: str
    account_id: str
    analyzed_video_ids: List[str]  # List of already analyzed video IDs to skip
    
    # Processing state
    ads: Annotated[list, operator.add]
    video_urls: Annotated[list, operator.add]
    # ... other state fields
```

**Key Features:**
- ✅ **State management** - `analyzed_video_ids` available to all nodes
- ✅ **Parameter handling** - Defaults to empty list if not provided
- ✅ **Type safety** - Proper typing for better error detection

### 4. Node Skip Logic

All processing nodes now implement skip logic:

**Pattern used in all nodes:**
```python
async def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
    analyzed_video_ids = state.get("analyzed_video_ids", [])
    
    for item in processing_items:
        video_id = extract_video_id(item)
        
        # Skip if already analyzed
        if video_id in analyzed_video_ids:
            logger.info(f"[⏩] Skipping {item_name} (already analyzed)")
            continue
            
        # Process the item...
```

**Affected nodes:**
- ✅ `transcribe_all_videos` - Skips transcription for analyzed videos
- ✅ `extract_all_videos_as_base64_frames` - Skips frame extraction
- ✅ `analyze_all_transcriptions` - Skips transcription analysis  
- ✅ `analyze_all_frames` - Skips frame analysis
- ✅ `final_ad_analysis` - Skips final analysis

### 5. API Integration

**File:** `Backend/app/api/v1/endpoints/ad_analysis.py`

The existing API endpoint automatically uses the new functionality:

```python
@router.post("/analyze/")
async def analyze_ads(current_user: User = Depends(get_current_user)):
    """
    Analyze ads using the AI Agent and storing the results in MongoDB.
    """
    # Initialize the AI Agent service
    ai_agent_service = AIAgentService()
    
    # Run the AI Agent analysis (now with skip logic)
    stored_analyses = await ai_agent_service.analyze_ads_with_ai_agent(
        user_id=str(current_user.id),
        access_token=current_user.fb_graph_api_key,
        account_id=current_user.fb_ad_account_id
    )
```

**No API changes required** - The integration is transparent to the API layer.

## Workflow Example

### Before Integration
```
1. Fetch all Facebook ads → 10 ads found
2. Download all videos → 10 videos downloaded
3. Transcribe all videos → 10 transcriptions
4. Analyze all videos → 10 analyses
5. Store in database → 10 new records

Total processing time: ~15 minutes
```

### After Integration (with 7 already analyzed)
```
1. Query database → 7 already analyzed video IDs found
2. Fetch all Facebook ads → 10 ads found
3. Download videos → 3 new videos downloaded (7 skipped)
4. Transcribe videos → 3 transcriptions (7 skipped)
5. Analyze videos → 3 analyses (7 skipped)
6. Store in database → 3 new records (7 skipped)

Total processing time: ~4.5 minutes (70% reduction)
```

## Benefits

### Performance Improvements
- ⚡ **Faster execution** - Skip already processed videos
- 💾 **Reduced storage** - No duplicate video downloads
- 🔄 **Efficient API usage** - Fewer calls to OpenAI and Facebook APIs
- 📉 **Lower costs** - Reduced API usage and processing time

### Data Integrity
- 🚫 **No duplicates** - Prevents duplicate entries in database
- ✅ **Consistent state** - Database remains the source of truth
- 🔄 **Resumable processing** - Can restart analysis without losing progress
- 📊 **Accurate tracking** - Clear logging of what's being skipped

### User Experience
- ⏱️ **Faster results** - Quicker analysis completion
- 🔄 **Incremental updates** - Only new ads are analyzed
- 📊 **Progress tracking** - Clear feedback on what's being processed
- 🎯 **Efficient workflow** - No wasted processing on existing data

## Testing

### Manual Testing Steps

1. **First Run** (no existing data):
   ```bash
   POST /api/v1/ad_analysis/analyze/
   # Should process all videos and store results
   ```

2. **Second Run** (with existing data):
   ```bash
   POST /api/v1/ad_analysis/analyze/
   # Should skip existing videos and only process new ones
   ```

3. **Verify Logs**:
   ```
   [📋] Skipping 5 already analyzed videos
   [⏩] Skipping video_123.mp4 (already analyzed)
   [✅] Processed 2 new videos out of 7 total
   ```

### Database Verification

```javascript
// MongoDB query to verify data
db.ad_analyses.find({"user_id": "your_user_id"}).count()
// Should show increasing count only for new videos
```

## Error Handling

### Database Connection Issues
- 🛡️ **Graceful fallback** - Returns empty list if database query fails
- 📝 **Error logging** - Logs database errors without breaking workflow
- 🔄 **Continues processing** - Workflow continues even if skip logic fails

### Malformed Data
- 🔍 **Data validation** - Filters out None/empty video IDs
- 🧹 **Data cleaning** - Removes duplicates and invalid entries
- ⚠️ **Warning logs** - Reports data quality issues

### API Integration
- 🔄 **Transparent integration** - No changes required to existing API calls
- 🛡️ **Backward compatibility** - Works with existing client code
- 📊 **Detailed logging** - Comprehensive tracking of skip operations

## Configuration

### Environment Variables
No additional configuration required - uses existing database connection.

### Logging Level
```python
# To see detailed skip operations
logging.getLogger("app.services.ai_agent_service").setLevel(logging.DEBUG)
```

## Future Enhancements

### Advanced Filtering
- 📅 **Date-based skipping** - Skip only videos analyzed within X days
- 🏷️ **Tag-based filtering** - Skip based on analysis categories
- 🎯 **Selective re-analysis** - Force re-analysis of specific videos

### Performance Optimization
- 🗃️ **Caching** - Cache video ID lists for faster subsequent queries
- 📊 **Batch processing** - Process multiple users' skip lists efficiently
- 🔄 **Incremental sync** - Track changes since last analysis

### Monitoring
- 📊 **Skip metrics** - Track skip rates and efficiency gains
- ⏱️ **Performance tracking** - Monitor time savings from skip logic
- 📈 **Usage analytics** - Analyze patterns in video re-processing 