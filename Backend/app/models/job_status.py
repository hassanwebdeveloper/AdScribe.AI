from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from bson import ObjectId

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(str, Enum):
    AD_ANALYSIS = "ad_analysis"

class BackgroundJob(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    progress: int = 0  # Progress percentage (0-100)
    message: Optional[str] = None
    error_message: Optional[str] = None
    
    # Job parameters
    parameters: Optional[Dict[str, Any]] = None
    
    # Results
    result_count: Optional[int] = None  # Number of analyses completed
    results: Optional[List[Dict[str, Any]]] = None  # Store results if needed
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Duration tracking
    estimated_duration_seconds: Optional[int] = None
    actual_duration_seconds: Optional[int] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class BackgroundJobResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    job_type: JobType
    status: JobStatus
    progress: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    result_count: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration_seconds: Optional[int] = None
    actual_duration_seconds: Optional[int] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class JobStartResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    estimated_duration_seconds: Optional[int] = None 