from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # MongoDB Configuration
    MONGODB_URL: str
    MONGODB_DB_NAME: str

    # Redis Configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int

    # JWT Configuration
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # Admin JWT Configuration (for admin panel OTP authentication)
    jwt_secret_key: str = "your-secure-admin-jwt-secret-key-change-in-production"
    environment: str = "development"
    
    # Email Configuration (for OTP sending)
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""  # Your email address
    smtp_password: str = ""  # App password for Gmail
    smtp_from_email: str = "noreply@adscribe.ai"
    
    # OpenAI Configuration
    openai_api_key: str
    
    # N8N Configuration
    N8N_WEBHOOK_URL: str
    N8N_WEBHOOK_URL_ANALYZE_ALL_ADS: str
    
    # Scheduler Configuration
    METRICS_COLLECTION_INTERVAL_HOURS: float = 4.0  # Default to 4 hours if not specified
    MIN_METRICS_COLLECTION_INTERVAL_HOURS: float = 4.0  # Minimum allowed interval in hours
    
    # Facebook OAuth Configuration
    FACEBOOK_CLIENT_ID: str
    FACEBOOK_CLIENT_SECRET: str
    FACEBOOK_REDIRECT_URI: str
    FRONTEND_URL: str
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 