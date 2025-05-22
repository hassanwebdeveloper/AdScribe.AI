from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import date

# Schema for individual ad metric
class AdMetric(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    ad_id: str = Field(..., description="Facebook Ad ID")
    ad_name: str = Field(..., description="Ad name")
    spend: float = Field(..., description="Amount spent")
    revenue: float = Field(..., description="Revenue from purchases")
    clicks: int = Field(..., description="Number of clicks")
    impressions: int = Field(..., description="Number of impressions")
    purchases: int = Field(..., description="Number of purchases")
    ctr: float = Field(..., description="Click-through rate (clicks/impressions)")
    cpc: float = Field(..., description="Cost per click (spend/clicks)")
    cpm: float = Field(..., description="Cost per thousand impressions")
    roas: float = Field(..., description="Return on ad spend (revenue/spend)")

# Schema for unique ad information
class UniqueAd(BaseModel):
    ad_id: str = Field(..., description="Facebook Ad ID")
    ad_name: str = Field(..., description="Ad name")

# Schema for date range
class DateRange(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")

# Main response schema for ad metrics endpoint
class AdMetricsResponse(BaseModel):
    ad_metrics: List[AdMetric] = Field(..., description="List of ad metrics")
    unique_ads: List[UniqueAd] = Field(..., description="List of unique ads")
    date_range: DateRange = Field(..., description="Date range of the data") 