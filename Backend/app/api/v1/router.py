from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, webhook, chat, ad_analysis, ad_metrics
from app.routers import prediction

api_router = APIRouter()

# Include different endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(ad_analysis.router, prefix="/ad-analysis", tags=["ad-analysis"])
api_router.include_router(ad_metrics.router, prefix="/ad-metrics", tags=["ad-metrics"])
api_router.include_router(prediction.router) 