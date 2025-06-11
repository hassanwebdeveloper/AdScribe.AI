from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field
from bson import ObjectId


class ClassificationClasses(BaseModel):
    """Model for text classification classes"""
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str = Field(..., description="Unique name for this classification set")
    description: str = Field(..., description="Description of what this classification set is for")
    classes: Dict[str, str] = Field(..., description="Dictionary mapping class names to descriptions")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether this classification set is active")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class ClassificationClassesCreate(BaseModel):
    """Model for creating classification classes"""
    name: str
    description: str
    classes: Dict[str, str]


class ClassificationClassesUpdate(BaseModel):
    """Model for updating classification classes"""
    name: Optional[str] = None
    description: Optional[str] = None
    classes: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class ClassificationClassesResponse(BaseModel):
    """Response model for classification classes"""
    id: str
    name: str
    description: str
    classes: Dict[str, str]
    created_at: datetime
    updated_at: datetime
    is_active: bool 