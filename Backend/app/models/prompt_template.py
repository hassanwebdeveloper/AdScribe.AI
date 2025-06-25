from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class PromptTemplate(BaseModel):
    """Model for storing prompt templates with variables and model selections"""
    
    id: Optional[str] = Field(None, alias="_id")
    prompt_key: str = Field(..., description="Unique identifier for the prompt")
    prompt_name: str = Field(..., description="Human-readable name for the prompt")
    prompt_text: str = Field(..., description="The actual prompt template with variables")
    variables: List[str] = Field(default=[], description="List of variables used in the prompt")
    model: str = Field(default="gpt-4o", description="OpenAI model to use for this prompt")
    temperature: float = Field(default=0.4, description="Temperature setting for the model")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens for the response")
    description: str = Field(default="", description="Description of what this prompt does")
    category: str = Field(default="general", description="Category of the prompt")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether this prompt is active")

    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class PromptTemplateCreate(BaseModel):
    """Model for creating new prompt templates"""
    prompt_key: str
    prompt_name: str
    prompt_text: str
    variables: List[str] = []
    model: str = "gpt-4o"
    temperature: float = 0.4
    max_tokens: Optional[int] = None
    description: str = ""
    category: str = "general"

class PromptTemplateUpdate(BaseModel):
    """Model for updating prompt templates"""
    prompt_name: Optional[str] = None
    prompt_text: Optional[str] = None
    variables: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class PromptTemplateResponse(BaseModel):
    """Model for prompt template responses"""
    id: str
    prompt_key: str
    prompt_name: str
    prompt_text: str
    variables: List[str]
    model: str
    temperature: float
    max_tokens: Optional[int]
    description: str
    category: str
    created_at: datetime
    updated_at: datetime
    is_active: bool 