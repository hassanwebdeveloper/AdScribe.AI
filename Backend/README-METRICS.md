# Ad Metrics Collection Service

This background service collects ad metrics from Facebook for each user on a scheduled basis.

## Configuration

The metrics collection interval can be configured in your `.env` file:

```
# Scheduler Configuration
METRICS_COLLECTION_INTERVAL_HOURS=4  # Set to desired interval in hours
```

## Available Metrics

The service currently collects the following metrics for each ad:

- Purchases
- Impressions
- Reach
- Clicks
- Spend

## Database Structure

Metrics are stored in the `ad_metrics` collection with the following structure:

- `user_id`: The user ID associated with these metrics
- `ad_id`: The Facebook ad ID
- `campaign_id`: The Facebook campaign ID
- `video_id`: The Facebook video ID (if applicable)
- `ad_name`: The name of the ad
- `campaign_name`: The name of the campaign
- `purchases`: Number of purchases attributed to this ad
- `additional_metrics`: Object containing other metrics (impressions, reach, clicks, spend)
- `collected_at`: Timestamp when these metrics were collected

## Usage

To manually trigger metrics collection for a user, call:

```
POST /api/v1/ad-metrics/collect
```

To view metrics for a user:

```
GET /api/v1/ad-metrics/
```

To view historical metrics for a specific ad:

```
GET /api/v1/ad-metrics/{ad_id}
``` 