from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)
        
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Handle Pydantic core schema."""
        schema = handler(str)
        schema["custom_wire_type"] = "string"
        return schema


class AdMetrics(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    ad_id: str
    ad_account_id: Optional[str] = None
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    ad_name: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    adset_name: Optional[str] = None
    purchases: int = 0
    additional_metrics: Optional[Dict[str, Any]] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class AdMetricsResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    ad_id: str
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    ad_name: Optional[str] = None
    campaign_name: Optional[str] = None
    purchases: int = 0
    additional_metrics: Optional[Dict[str, Any]] = None
    collected_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class PeriodMetrics(BaseModel):
    start_date: str
    end_date: str
    roas: float = 0
    ctr: float = 0
    cpc: float = 0
    cpm: float = 0
    conversions: int = 0
    spend: float = 0
    revenue: float = 0


class DailyMetric(BaseModel):
    date: str
    spend: float = 0
    revenue: float = 0
    clicks: int = 0
    impressions: int = 0
    purchases: int = 0
    ctr: float = 0
    roas: float = 0
    ad_id: Optional[str] = None
    ad_name: Optional[str] = None


class RefreshStatus(BaseModel):
    metrics_fetched: bool = False
    has_complete_data: bool = False
    force_refresh_attempted: bool = False


class AdDailyMetric(BaseModel):
    date: str
    ad_id: str
    ad_name: Optional[str] = None
    ad_title: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    adset_name: Optional[str] = None
    spend: float = 0
    clicks: int = 0
    impressions: int = 0
    purchases: int = 0
    revenue: float = 0
    ctr: float = 0
    cpc: float = 0
    cpm: float = 0
    roas: float = 0


class UniqueAd(BaseModel):
    ad_id: str
    ad_name: str


class DashboardResponse(BaseModel):
    current_period: PeriodMetrics
    previous_period: PeriodMetrics
    daily_metrics: List[DailyMetric] = Field(default_factory=list)
    refresh_status: RefreshStatus = Field(default_factory=RefreshStatus)
    ad_metrics: List[AdDailyMetric] = Field(default_factory=list)
    unique_ads: List[Dict[str, str]] = Field(default_factory=list)


class AdMetricsDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    ad_id: str
    ad_account_id: Optional[str] = None
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    ad_name: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    adset_name: Optional[str] = None
    purchases: int = 0
    additional_metrics: Optional[Dict[str, Any]] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    } 