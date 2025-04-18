from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Annotated
from bson import ObjectId


# Custom type for handling MongoDB ObjectIds
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


class UserBase(BaseModel):
    name: str
    email: EmailStr
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class UserCreate(UserBase):
    password: str


class UserInDB(UserBase):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    hashed_password: str
    fb_graph_api_key: Optional[str] = None
    fb_ad_account_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class User(UserBase):
    id: str = Field(..., alias="_id")
    fb_graph_api_key: Optional[str] = None
    fb_ad_account_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "_id": "60d21b4967d0d8992e610c85",
                "name": "John Doe",
                "email": "john@example.com",
                "fb_graph_api_key": "",
                "fb_ad_account_id": "",
                "created_at": "2021-06-22T12:00:00",
                "updated_at": "2021-06-22T12:00:00"
            }
        }
    }


class UserResponse(BaseModel):
    user: User
    token: str 