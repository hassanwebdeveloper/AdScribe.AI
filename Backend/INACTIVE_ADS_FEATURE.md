# Inactive Ads Feature

## Overview

The Inactive Ads feature enhances the AdScribe.AI platform by automatically tracking and managing ads that are no longer active on Facebook. This feature ensures that:

1. The main ad_analyses collection only contains currently active ads
2. Inactive ads are moved to a separate collection (inactive_ads_analyses)
3. Users can view, restore, or delete inactive ads as needed

## How It Works

### Automatic Detection and Movement

When the AI Agent analyzes ads from Facebook:

1. It fetches all current active ads from the Facebook API
2. It compares these with the ads stored in the ad_analyses collection
3. Any ads that are in the database but no longer active on Facebook are moved to the inactive_ads_analyses collection
4. A timestamp (moved_to_inactive_at) is added to track when the ad became inactive

### API Endpoints

The following endpoints are available for managing inactive ads:

- `GET /api/v1/ad-analysis/inactive` - Get a list of inactive ads
- `GET /api/v1/ad-analysis/inactive/count` - Get the count of inactive ads
- `GET /api/v1/ad-analysis/inactive/{ad_id}` - Get a specific inactive ad by ID
- `POST /api/v1/ad-analysis/inactive/{ad_id}/restore` - Restore an inactive ad to the active collection
- `DELETE /api/v1/ad-analysis/inactive/{ad_id}` - Permanently delete an inactive ad

### Models

- `InactiveAdAnalysis` - Extends the AdAnalysis model with an additional field for tracking when it was moved to inactive status

### Services

- `InactiveAdsService` - Provides methods for managing inactive ads
- `AIAgentService._move_inactive_ads()` - Handles the automatic detection and movement of inactive ads

## Testing

A test script (`test_inactive_ads.py`) is provided to verify the functionality of the inactive ads feature. This script:

1. Creates test active ads
2. Simulates the detection of inactive ads
3. Verifies that inactive ads are moved correctly
4. Tests the restoration of inactive ads
5. Cleans up test data

## Implementation Details

### Database Collections

- `ad_analyses` - Contains only active ads
- `inactive_ads_analyses` - Contains ads that were once active but are no longer active on Facebook

### Key Fields

- `ad_status` - Indicates the status of the ad on Facebook
- `moved_to_inactive_at` - Timestamp when the ad was moved to the inactive collection

## Future Enhancements

Potential future enhancements for this feature include:

1. Automatic cleanup of old inactive ads after a configurable retention period
2. Batch operations for restoring or deleting multiple inactive ads
3. Analytics comparing performance of active vs inactive ads
4. Notifications when ads become inactive 