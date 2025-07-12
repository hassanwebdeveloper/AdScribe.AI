
# Video URL Refresh Feature

## Overview

Facebook ad video URLs have expiration times and become invalid after a certain period. This feature automatically checks for expired video URLs and refreshes them using the Facebook Graph API when needed.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Endpoint  │    │  VideoUrlService│    │  Facebook API   │
│   (Any endpoint │───▶│                 │───▶│                 │
│   returning ads)│    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Database      │    │   Fresh Video   │
                       │   Update        │    │   URL           │
                       └─────────────────┘    └─────────────────┘
```

## Implementation Details

### 1. VideoUrlService

**File:** `Backend/app/services/video_url_service.py`

**Key Methods:**
- `check_and_refresh_video_url()` - Main method to check and refresh a single video URL
- `_is_url_valid()` - Validates if a URL is still accessible
- `_get_fresh_video_url()` - Fetches fresh URL from Facebook API
- `_update_video_url_in_database()` - Updates the database with new URL
- `refresh_expired_urls_for_user()` - Batch refresh all URLs for a user
- `get_video_url_with_refresh()` - Get URL with automatic refresh

### 2. Automatic Integration

The video URL checking is automatically integrated into the following endpoints:

**Ad Analysis Endpoints:**
- `GET /api/v1/ad-analysis/` - List all ad analyses
- `GET /api/v1/ad-analysis/get/{analysis_id}` - Get single ad analysis
- `GET /api/v1/ad-analysis/{analysis_id}` - Get ad analysis (alternative endpoint)

**Webhook Endpoint:**
- `POST /api/v1/webhook/chat` - Chat webhook that returns ad data

### 3. Manual Refresh Endpoint

**Endpoint:** `POST /api/v1/ad-analysis/refresh-video-urls`

**Description:** Manually refresh all expired video URLs for the current user.

**Response:**
```json
{
  "success": true,
  "message": "Refreshed 5 video URLs",
  "details": {
    "refreshed": 5,
    "failed": 1,
    "total": 6
  }
}
```

## How It Works

### 1. URL Validation

The service first checks if the current video URL is still valid by making a HEAD request:

```python
async def _is_url_valid(self, url: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.head(url, follow_redirects=True)
        return 200 <= response.status_code < 300
```

### 2. Fresh URL Retrieval

If the URL is expired, the service fetches a fresh URL from Facebook:

```python
async def _get_fresh_video_url(self, video_id: str, user_id: str) -> Optional[str]:
    # Get user's Facebook credentials
    credentials = await self.user_service.get_facebook_credentials(user_id)
    
    # Initialize Facebook service
    fb_service = FacebookAdService(access_token=access_token, account_id=account_id)
    
    # Get fresh video URL
    fresh_url = await fb_service.get_video_url(video_id)
    return fresh_url
```

### 3. Database Update

The service updates the database with the new URL and adds a timestamp:

```python
async def _update_video_url_in_database(self, video_id: str, new_url: str, user_id: str):
    result = await db.ad_analyses.update_many(
        {"user_id": user_id, "video_id": video_id},
        {
            "$set": {
                "video_url": new_url,
                "video_url_updated_at": datetime.utcnow()
            }
        }
    )
```

## Usage Examples

### 1. Automatic Refresh (Transparent to Frontend)

When the frontend calls any endpoint that returns ad data, the video URLs are automatically checked and refreshed:

```javascript
// Frontend code - no changes needed
const response = await fetch('/api/v1/ad-analysis/');
const adAnalyses = await response.json();
// Video URLs are automatically refreshed if expired
```

### 2. Manual Refresh

Trigger a manual refresh of all video URLs for a user:

```javascript
// Frontend code to manually refresh URLs
const response = await fetch('/api/v1/ad-analysis/refresh-video-urls', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const result = await response.json();
console.log(result.message); // "Refreshed 5 video URLs"
```

## Error Handling

The service includes comprehensive error handling:

1. **Network Errors:** If URL validation fails due to network issues, the original URL is returned
2. **Facebook API Errors:** If fresh URL retrieval fails, the original URL is returned
3. **Database Errors:** Errors are logged but don't prevent the endpoint from returning data
4. **Batch Processing:** Failed refreshes are counted and reported in batch operations

## Performance Considerations

1. **Lazy Loading:** URLs are only checked when data is requested
2. **Batch Processing:** Manual refresh processes URLs in batches of 5 to avoid API rate limits
3. **Caching:** The service respects Facebook's rate limits with delays between requests
4. **Fallback:** Original URLs are always returned if refresh fails

## Database Schema Changes

The service adds an optional timestamp field to track when URLs were last updated:

```javascript
{
  "video_url": "https://video.xx.fbcdn.net/...",
  "video_url_updated_at": "2024-01-15T10:30:00Z"  // New field
}
```

## Testing

Run the test script to verify the service functionality:

```bash
cd Backend
python test_video_url_service.py
```

## Future Enhancements

1. **Proactive Refresh:** Schedule background jobs to refresh URLs before they expire
2. **URL Expiration Prediction:** Predict when URLs will expire based on patterns
3. **Caching Strategy:** Implement Redis caching for frequently accessed URLs
4. **Monitoring:** Add metrics to track URL refresh success/failure rates 