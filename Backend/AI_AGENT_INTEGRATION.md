# AI Agent Integration

This document describes the integration of the LangGraph AI Agent to replace the N8N webhook for ad analysis.

## Overview

The AI Agent is a LangGraph-based workflow that replicates the N8N ad analysis pipeline. It performs the following steps:

1. **Get Facebook Ads** - Fetches ads from Facebook Graph API
2. **Get Video URLs** - Extracts video URLs from ad creatives
3. **Download Videos** - Downloads videos for processing
4. **Transcribe Videos** - Uses OpenAI Whisper to transcribe audio
5. **Extract Frames** - Extracts frames from videos for visual analysis
6. **Analyze Transcriptions** - Uses GPT-4 to analyze transcription content
7. **Analyze Frames** - Uses GPT-4 Vision to analyze video frames
8. **Final Analysis** - Combines all analyses into final ad insights

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   AI Agent      │    │   Database      │
│   Endpoint      │───▶│   Service       │───▶│   (MongoDB)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   LangGraph     │
                       │   Workflow      │
                       └─────────────────┘
```

## Files Changed/Added

### New Files
- `Backend/app/core/AI_Agent/Agent/Analyze_all_Ads.py` - Main AI Agent implementation (fixed)
- `Backend/app/services/ai_agent_service.py` - Service layer for AI Agent integration
- `Backend/test_ai_agent.py` - Test script for AI Agent functionality

### Modified Files
- `Backend/app/core/AI_Agent/Nodes/*.py` - All node implementations (fixed for async, logging, error handling)
- `Backend/app/api/v1/endpoints/ad_analysis.py` - Replaced N8N webhook with AI Agent
- `Backend/app/services/facebook_service.py` - Fixed httpx.TimeoutError issue

## Key Improvements

### 1. Fixed AI Agent Issues
- **Async Compatibility**: All nodes are now properly async
- **Error Handling**: Comprehensive error handling and logging
- **State Management**: Proper state passing between nodes
- **Database Integration**: Results are formatted for the existing database schema

### 2. Replaced N8N Dependency
- **Direct Integration**: No external webhook dependencies
- **Better Error Handling**: More granular error messages
- **Consistent Data Format**: Same database schema as before

### 3. Enhanced Logging
- **Structured Logging**: Proper logging throughout the workflow
- **Progress Tracking**: Clear progress indicators for each step
- **Error Reporting**: Detailed error reporting with stack traces

## Usage

### 1. API Endpoint
The existing `/api/v1/ad-analysis/analyze/` endpoint now uses the AI Agent instead of N8N:

```python
POST /api/v1/ad-analysis/analyze/
```

### 2. Direct Service Usage
```python
from app.services.ai_agent_service import AIAgentService

ai_agent_service = AIAgentService()
results = await ai_agent_service.analyze_ads_with_ai_agent(
    user_id="user_123",
    access_token="facebook_access_token",
    account_id="ad_account_id"
)
```

### 3. Testing
Run the test script to verify functionality:

```bash
cd Backend
python test_ai_agent.py
```

## Environment Variables

The AI Agent requires the following environment variables:

```bash
# OpenAI API Key (for transcription and analysis)
OPENAI_API_KEY=your_openai_api_key

# Facebook credentials (passed from user settings)
# These are provided per-user, not as environment variables
```

## Data Flow

### Input
- User ID
- Facebook Access Token
- Facebook Ad Account ID

### Processing
1. Fetch ads from Facebook Graph API
2. Extract video URLs from ad creatives
3. Download videos to temporary storage
4. Transcribe audio using OpenAI Whisper
5. Extract frames from videos
6. Analyze transcriptions with GPT-4
7. Analyze frames with GPT-4 Vision
8. Combine analyses into final insights

### Output
The AI Agent returns data in the same format as the previous N8N implementation:

```python
[
    {
        "user_id": "string",
        "video_id": "string",
        "ad_id": "string",
        "campaign_id": "string",
        "campaign_name": "string",
        "adset_id": "string",
        "adset_name": "string",
        "adset_targeting": {...},
        "ad_title": "string",
        "ad_message": "string",
        "ad_status": "string",
        "video_url": "string",
        "audio_description": "string",
        "video_description": "string",
        "ad_analysis": {
            "hook": "string",
            "tone": "string",
            "power_phrases": "string",
            "visual": "string"
        },
        "created_at": "datetime"
    }
]
```

## Error Handling

The AI Agent includes comprehensive error handling:

### Node-Level Errors
- Each node catches and logs its own errors
- Errors are accumulated in the state for reporting
- Processing continues even if individual items fail

### Service-Level Errors
- Database connection errors
- Facebook API errors
- OpenAI API errors
- Timeout handling

### API-Level Errors
- User-friendly error messages
- Specific error types (timeout, API, credentials)
- Proper HTTP status codes

## Performance Considerations

### Caching
- Downloaded videos are cached to avoid re-downloading
- Transcriptions are cached to avoid re-processing
- Frame extractions are cached
- Analysis results are cached

### Concurrency
- Videos are processed sequentially to avoid overwhelming APIs
- Individual operations within each video are optimized
- Proper resource cleanup

### Resource Management
- Temporary files are cleaned up automatically
- Memory usage is optimized for large video processing
- API rate limiting is respected

## Monitoring and Debugging

### Logging
All operations are logged with appropriate levels:
- `INFO`: Progress and success messages
- `WARNING`: Non-critical issues
- `ERROR`: Failures that don't stop processing
- `DEBUG`: Detailed debugging information

### Graph Visualization
The AI Agent can generate a visual representation of the workflow:

```python
from app.core.AI_Agent.Agent.Analyze_all_Ads import visualize_graph
visualize_graph()
```

This creates a `graph_output.png` file showing the workflow structure.

## Migration from N8N

### What Changed
1. **Endpoint Behavior**: Same API, different implementation
2. **Data Format**: Identical output format
3. **Error Handling**: Improved error messages
4. **Performance**: Better caching and resource management

### What Stayed the Same
1. **API Interface**: No changes to the REST API
2. **Database Schema**: Same data structure
3. **Frontend Compatibility**: No frontend changes needed
4. **User Experience**: Same functionality from user perspective

## Troubleshooting

### Common Issues

1. **OpenAI API Key Missing**
   ```
   Error: OpenAI API key not configured
   Solution: Set OPENAI_API_KEY environment variable
   ```

2. **Facebook API Errors**
   ```
   Error: Error accessing Facebook API
   Solution: Check user's Facebook access token and ad account ID
   ```

3. **Video Download Failures**
   ```
   Error: Failed to download video
   Solution: Check video URL accessibility and network connectivity
   ```

4. **Transcription Failures**
   ```
   Error: Failed to transcribe video
   Solution: Check video format and OpenAI API quota
   ```

### Debug Mode
Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Improvements
1. **Parallel Processing**: Process multiple videos concurrently
2. **Advanced Caching**: Redis-based caching for better performance
3. **Retry Logic**: Exponential backoff for API failures
4. **Metrics Collection**: Performance and usage metrics
5. **A/B Testing**: Compare AI Agent vs N8N results

### Extensibility
The AI Agent is designed to be easily extensible:
- Add new analysis nodes
- Modify existing analysis prompts
- Integrate additional AI services
- Add new data sources

## Support

For issues or questions regarding the AI Agent integration:

1. Check the logs for detailed error messages
2. Run the test script to verify functionality
3. Review this documentation for common solutions
4. Check environment variable configuration 