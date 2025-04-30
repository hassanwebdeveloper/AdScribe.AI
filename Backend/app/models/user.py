from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
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


class FacebookCredentials(BaseModel):
    access_token: str
    account_id: str
    token_expires_at: Optional[datetime] = None


class FacebookProfile(BaseModel):
    id: str
    name: Optional[str] = None
    email: Optional[str] = None


class UserBase(BaseModel):
    name: str
    email: EmailStr
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class UserCreate(UserBase):
    password: Optional[str] = None


class UserInDB(UserBase):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    hashed_password: Optional[str] = None
    fb_graph_api_key: Optional[str] = None
    fb_ad_account_id: Optional[str] = None
    facebook_profile: Optional[FacebookProfile] = None
    facebook_credentials: Optional[FacebookCredentials] = None
    is_facebook_login: bool = False
    is_collecting_metrics: bool = False
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
    facebook_profile: Optional[FacebookProfile] = None
    facebook_credentials: Optional[FacebookCredentials] = None
    is_facebook_login: bool = False
    is_collecting_metrics: bool = False
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
                "facebook_profile": {
                    "id": "12345678",
                    "name": "John Doe",
                    "email": "john@example.com"
                },
                "facebook_credentials": {
                    "access_token": "EAABsbCS1IPkBOwfLZCjMmzNHRyH...",
                    "account_id": "12345678",
                    "token_expires_at": "2023-12-31T23:59:59"
                },
                "is_facebook_login": True,
                "is_collecting_metrics": False,
                "created_at": "2021-06-22T12:00:00",
                "updated_at": "2021-06-22T12:00:00"
            }
        }
    }


class UserResponse(BaseModel):
    user: User
    token: str


class FacebookCredentialsUpdate(BaseModel):
    access_token: str
    account_id: str 