from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
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
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    ad_name: Optional[str] = None
    campaign_name: Optional[str] = None
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