from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Annotated, Dict
from bson import ObjectId
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.string_schema()


class Ad(BaseModel):
    title: str
    description: str
    video_url: str
    is_active: bool
    purchases: int

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "title": "Product Title",
                "description": "Product Description",
                "video_url": "https://example.com/video.mp4",
                "is_active": True,
                "purchases": 100
            }
        }
    }


class Message(BaseModel):
    id: str
    content: str
    role: str
    timestamp: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    ad: Optional[Ad] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "id": "msg_123456",
                "content": "Hello, how can I help you?",
                "role": "bot",
                "timestamp": "2023-01-01T12:00:00",
                "start_date": "2023-01-01T12:00:00",
                "end_date": "2023-01-31T12:00:00",
                "ad": None
            }
        }
    }


class ChatSession(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    title: str
    messages: List[Message]
    ads: List[Ad] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "_id": "60d21b4967d0d8992e610c85",
                "user_id": "60d21b4967d0d8992e610c85",
                "title": "New Chat 1",
                "messages": [],
                "ads": [],
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:00:00"
            }
        }
    }


class DateRange(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "start_date": "2023-01-01",
                "end_date": "2023-01-31"
            }
        }
    }


class AnalysisSettings(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    date_range: DateRange
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "_id": "60d21b4967d0d8992e610c85",
                "user_id": "60d21b4967d0d8992e610c85",
                "date_range": {
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31"
                },
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:00:00"
            }
        }
    } 