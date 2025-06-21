from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class ParameterChange(BaseModel):
    """Individual parameter change recommendation"""
    parameter: str  # e.g., "ctr", "spend", "cpc"
    current_value: float
    optimized_value: float
    change_percent: float
    change_direction: str  # "increase" or "decrease"
    impact_level: str  # "high", "medium", "low"


class MLAdRecommendation(BaseModel):
    """Individual ad optimization recommendation"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    ad_id: str
    ad_name: str
    campaign_id: Optional[str] = None
    video_id: Optional[str] = None
    
    # Performance data
    current_roas: float
    predicted_roas: float
    improvement_percent: float
    
    # Optimization details
    primary_strategy: str  # "ctr", "spend", "efficiency", "conversion"
    optimization_confidence: float
    optimization_status: str  # "converged", "max_iterations"
    
    # All parameter changes (comprehensive view)
    parameter_changes: List[ParameterChange] = Field(default_factory=list)
    
    # Creative metadata
    creative_metadata: Optional[Dict[str, Any]] = None
    
    # AI-generated strategies
    implementation_strategies: List[str] = Field(default_factory=list)
    ai_creative_suggestions: Optional[Dict[str, Any]] = None
    benchmark_creative: Optional[Dict[str, Any]] = None
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"  # "active", "implemented", "dismissed"
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class MLRecommendationBatch(BaseModel):
    """Complete ML recommendation batch for a user"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    
    # Batch metadata
    goal: str
    target_improvement: float
    ml_optimization_enabled: bool
    
    # Summary statistics
    total_ads_analyzed: int
    successful_optimizations: int
    convergence_rate: float
    average_predicted_improvement: float
    max_improvement_achieved: float
    min_improvement_achieved: float
    
    # Strategy breakdowns
    ctr_improvement_opportunities: int
    spend_optimization_opportunities: int
    efficiency_improvement_opportunities: int
    conversion_improvement_opportunities: int
    
    # Individual recommendations
    ad_recommendations: List[MLAdRecommendation] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "active"  # "active", "archived"
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class MLRecommendationSummary(BaseModel):
    """Summary view of recommendations for API responses"""
    batch_id: str
    user_id: str
    goal: str
    total_ads_analyzed: int
    total_opportunities: int
    average_improvement: float
    generated_at: datetime
    status: str 