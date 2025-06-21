from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from bson import ObjectId
from enum import Enum


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


class RecommendationType(str, Enum):
    BUDGET_REALLOCATION = "budget_reallocation"
    CREATIVE_OPTIMIZATION = "creative_optimization"
    AUDIENCE_TARGETING = "audience_targeting"
    BIDDING_STRATEGY = "bidding_strategy"
    PERFORMANCE_IMPROVEMENT = "performance_improvement"


class CreativeMetadata(BaseModel):
    hook_type: Optional[str] = None  # e.g., "Emotional", "Informational", "Problem-solution"
    hook_content: Optional[str] = None  # e.g., "Emotional kahani sunana"
    tone_category: Optional[str] = None  # e.g., "Emotional", "Neutral", "Aggressive"
    visual_style: Optional[str] = None  # e.g., "Standing", "Reaching", "Sitting", "Moving"
    power_elements: Optional[List[str]] = Field(default_factory=list)  # e.g., ["Urgency", "Social Proof", "Risk Reversal"]
    cta_type: Optional[str] = None  # e.g., "Direct", "Soft", "Question"
    product_focus: Optional[str] = None  # e.g., "Feature-focused", "Benefit-focused", "Problem-focused"
    duration_seconds: Optional[float] = None
    voice_tone: Optional[str] = None  # e.g., "Professional", "Casual", "Urgent"
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class PerformanceMetrics(BaseModel):
    roas: Optional[float] = None
    ctr: Optional[float] = None
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    spend: Optional[float] = None
    revenue: Optional[float] = None
    clicks: Optional[int] = None
    impressions: Optional[int] = None
    purchases: Optional[int] = None
    conversion_rate: Optional[float] = None
    frequency: Optional[float] = None
    reach: Optional[int] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class RecommendationAction(BaseModel):
    type: RecommendationType
    priority: int = Field(ge=1, le=5)  # 1 = highest priority, 5 = lowest
    title: str
    description: str
    expected_impact: Optional[str] = None  # e.g., "Expected ROAS increase: 15%"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)  # 0-1 scale
    implementation_effort: Optional[str] = None  # e.g., "Low", "Medium", "High"
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class AIRecommendation(BaseModel):
    suggestion: str
    reasoning: str
    specific_changes: Optional[Dict[str, Any]] = None  # e.g., {"hook": {"from": "old", "to": "new"}}
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class RecommendationGoal(BaseModel):
    metric: str  # e.g., "roas", "ctr", "cpc"
    target_improvement: float  # e.g., 10 for 10% improvement
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    timeframe_days: Optional[int] = 30  # Default 30 days
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class AdRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    ad_id: str
    ad_name: Optional[str] = None
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    
    # Performance data
    performance_summary: PerformanceMetrics
    creative_metadata: Optional[CreativeMetadata] = None
    
    # Recommendation details
    goal: RecommendationGoal
    fixed_recommendations: List[RecommendationAction] = Field(default_factory=list)
    ai_recommendations: List[AIRecommendation] = Field(default_factory=list)
    
    # ML model predictions
    predicted_performance: Optional[PerformanceMetrics] = None
    feature_importance: Optional[Dict[str, float]] = None  # Feature importance from ML model
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"  # active, archived, implemented
    implementation_notes: Optional[str] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class AdRecommendationResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    ad_id: str
    ad_name: Optional[str] = None
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    
    performance_summary: PerformanceMetrics
    creative_metadata: Optional[CreativeMetadata] = None
    
    goal: RecommendationGoal
    fixed_recommendations: List[RecommendationAction] = Field(default_factory=list)
    ai_recommendations: List[AIRecommendation] = Field(default_factory=list)
    
    predicted_performance: Optional[PerformanceMetrics] = None
    feature_importance: Optional[Dict[str, float]] = None
    
    generated_at: datetime
    status: str = "active"
    implementation_notes: Optional[str] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


# Batch recommendation request
class RecommendationRequest(BaseModel):
    ad_ids: Optional[List[str]] = None  # If None, analyze all ads
    goal: RecommendationGoal
    force_refresh: bool = False
    include_predictions: bool = True
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


# Creative pattern analysis for finding successful patterns
class CreativePattern(BaseModel):
    pattern_id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: str
    pattern_type: str  # e.g., "high_ctr_pattern", "high_roas_pattern"
    
    # Pattern characteristics
    creative_features: CreativeMetadata
    performance_criteria: Dict[str, Any]  # e.g., {"min_roas": 2.0, "min_ctr": 0.01}
    
    # Statistical significance
    sample_size: int
    avg_performance: PerformanceMetrics
    confidence_interval: Optional[Dict[str, float]] = None
    
    # Associated ads
    ad_examples: List[str] = Field(default_factory=list)  # List of ad_ids that match this pattern
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


# Structured recommendation system models
class Recommendation(BaseModel):
    """Individual recommendation item."""
    title: str
    description: str
    impact: str  # "High", "Medium", "Low"
    effort: str  # "High", "Medium", "Low"
    details: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class RecommendationCategory(BaseModel):
    """Category of recommendations (e.g., Creative Improvements, Scale Opportunities)."""
    name: str
    description: str
    recommendations: List[Recommendation] = Field(default_factory=list)
    priority: str = "Medium"  # "High", "Medium", "Low"
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class RecommendationResponse(BaseModel):
    """Main response structure for recommendation system."""
    goal: str
    categories: List[RecommendationCategory] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approach: Optional[str] = None  # "ML Optimization", "Rule-based Analysis", etc.
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    } 