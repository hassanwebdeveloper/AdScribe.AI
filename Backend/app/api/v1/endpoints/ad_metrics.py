from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from app.core.database import get_database
from app.models.ad_metrics import AdMetrics, AdMetricsResponse
from app.services.metrics_service import MetricsService
from app.services.scheduler_service import SchedulerService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from bson import ObjectId

router = APIRouter()
metrics_service = MetricsService()

# Use lazy loading for scheduler service
def get_scheduler_service():
    return SchedulerService()

@router.get("/", response_model=List[AdMetricsResponse])
async def get_user_metrics(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user)
):
    """
    Get metrics for the current user.
    """
    metrics = await metrics_service.get_user_metrics(current_user.id, skip, limit)
    return metrics

@router.get("/{ad_id}", response_model=List[AdMetricsResponse])
async def get_ad_metrics_history(
    ad_id: str, 
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user)
):
    """
    Get historical metrics for a specific ad.
    """
    metrics = await metrics_service.get_ad_metrics_history(ad_id, skip, limit)
    
    # Check if metrics belong to the current user
    if metrics and metrics[0]["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access these metrics"
        )
    
    return metrics

@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_metrics_collection(current_user: User = Depends(get_current_user)):
    """
    Manually trigger metrics collection for the current user.
    """
    if not current_user.facebook_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook credentials not configured"
        )
    
    # Get scheduler service instance and schedule metrics collection
    scheduler_service = get_scheduler_service()
    await scheduler_service.schedule_metrics_collection_for_user(current_user.id)
    
    return {"message": "Metrics collection scheduled"} 