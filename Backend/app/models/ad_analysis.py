from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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


class AdAnalysisDetail(BaseModel):
    hook: Optional[str] = None
    tone: Optional[str] = None
    power_phrases: Optional[str] = None
    visual: Optional[str] = None
    product: Optional[str] = None
    product_type: Optional[str] = None


class AdSetTargeting(BaseModel):
    age_max: Optional[int] = None
    age_min: Optional[int] = None
    age_range: Optional[List[int]] = None
    genders: Optional[List[int]] = None
    geo_locations: Optional[Dict[str, Any]] = None
    brand_safety_content_filter_levels: Optional[List[str]] = None
    targeting_automation: Optional[Dict[str, Any]] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "extra": "allow"  # Allow extra fields beyond those defined
    }


class AdAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    ad_analysis: Optional[AdAnalysisDetail] = None
    audio_description: Optional[str] = None
    video_description: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    ad_id: Optional[str] = None
    adset_name: Optional[str] = None
    adset_targeting: Optional[AdSetTargeting] = None
    video_id: Optional[str] = None
    ad_title: Optional[str] = None
    ad_message: Optional[str] = None
    ad_status: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class InactiveAdAnalysis(AdAnalysis):
    moved_to_inactive_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class AdAnalysisResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    ad_analysis: Optional[AdAnalysisDetail] = None
    audio_description: Optional[str] = None
    video_description: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    adset_id: Optional[str] = None
    adset_name: Optional[str] = None
    adset_targeting: Optional[AdSetTargeting] = None
    video_id: Optional[str] = None
    ad_title: Optional[str] = None
    ad_message: Optional[str] = None
    ad_status: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    } 