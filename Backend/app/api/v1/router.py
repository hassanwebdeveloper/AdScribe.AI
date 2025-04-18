from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, webhook, chat

api_router = APIRouter()

# Include different endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"]) 