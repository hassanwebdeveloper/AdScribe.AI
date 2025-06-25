from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from app.core.deps import get_current_user
from app.models.user import User
from app.models.recommendation import (
    AdRecommendation, 
    AdRecommendationResponse,
    RecommendationRequest,
    RecommendationGoal,
    RecommendationResponse
)
from app.services.recommendation_service import RecommendationService
from app.services.ml_optimization_service import ml_optimization_service, MLOptimizationService
from recommendation_jobs import job_manager, generate_recommendations_background
from pydantic import BaseModel
import logging
from datetime import datetime
from app.services.ml_recommendation_storage import MLRecommendationStorageService

logger = logging.getLogger(__name__)
router = APIRouter()
recommendation_service = RecommendationService()
ml_optimization_service = MLOptimizationService()
ml_storage_service = MLRecommendationStorageService()


@router.post("/generate", response_model=RecommendationResponse)
async def generate_recommendations(
    current_user: User = Depends(get_current_user)
):
    """
    Generate ROAS improvement recommendations using rule-based analysis.
    
    This endpoint analyzes the user's ad performance data and provides
    actionable recommendations to improve ROAS by at least 10%.
    """
    try:
        recommendations = await recommendation_service.generate_recommendations(current_user)
        return recommendations
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")


@router.post("/optimize", response_model=dict)
async def generate_ml_optimization_recommendations(
    target_improvement: float = Query(default=10.0, description="Target ROAS improvement percentage"),
    include_all_parameters: bool = Query(default=False, description="Include all parameter changes (true) or primary strategy only (false)"),
    current_user: User = Depends(get_current_user)
):
    """
    Generate ML-based optimization recommendations to achieve target ROAS improvement.
    
    This endpoint uses machine learning models to predict ROAS and optimization algorithms
    to find the best parameter changes to achieve the target improvement.
    
    The process:
    1. Trains ML models to predict ROAS based on performance metrics (spend, CTR, CPC, etc.)
    2. Optimizes input parameters to achieve target ROAS improvement
    3. Groups recommendations by strategy (CTR improvement, spend optimization, etc.)
    4. Provides specific creative suggestions using AI for each optimization opportunity
    5. Stores recommendations in database for future reference
    
    Parameters:
    - target_improvement: Target ROAS improvement percentage (default: 10%)
    - include_all_parameters: If true, shows all parameter changes; if false, shows primary strategy only
    """
    try:
        logger.info(f"Generating ML optimization recommendations for user {current_user.id}")
        
        recommendations = await ml_optimization_service.generate_optimization_recommendations(
            user_id=current_user.id,
            target_roas_improvement=target_improvement
        )
        
        # Filter recommendations based on user preference
        if not include_all_parameters:
            # Filter to show only primary strategy recommendations
            filtered_recommendations = {
                "goal": recommendations.get("goal"),
                "optimization_summary": recommendations.get("optimization_summary"),
                "batch_id": recommendations.get("batch_id"),
                "generated_at": recommendations.get("generated_at", datetime.now().isoformat())
            }
            
            # Add only the primary strategy for each recommendation category
            for strategy_key in ["ctr_improvements", "spend_optimizations", "efficiency_improvements", "conversion_improvements"]:
                if strategy_key in recommendations:
                    strategy_data = recommendations[strategy_key]
                    if isinstance(strategy_data, dict) and "recommendations" in strategy_data:
                        # Keep only the primary strategy insights
                        filtered_strategy = {
                            "strategy": strategy_data.get("strategy"),
                            "description": strategy_data.get("description"),
                            "recommendations": []
                        }
                        
                        for rec in strategy_data["recommendations"]:
                            # Keep core recommendation but remove all_parameter_changes if not requested
                            filtered_rec = {k: v for k, v in rec.items() if k != "all_parameter_changes"}
                            filtered_strategy["recommendations"].append(filtered_rec)
                        
                        filtered_recommendations[strategy_key] = filtered_strategy
            
            return filtered_recommendations
        else:
            # Return full recommendations with all parameter changes
            return recommendations
        
    except Exception as e:
        logger.error(f"Error generating ML optimization recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating ML optimization recommendations: {str(e)}"
        )


@router.post("/hybrid", response_model=RecommendationResponse)
async def generate_hybrid_recommendations(
    prefer_ml: bool = Query(default=True, description="Prefer ML optimization over rule-based"),
    current_user: User = Depends(get_current_user)
):
    """
    Generate hybrid recommendations using both ML optimization and rule-based analysis.
    
    This endpoint tries ML optimization first, and falls back to rule-based analysis
    if insufficient data is available for ML training.
    """
    try:
        logger.info(f"Generating hybrid recommendations for user {current_user.id}")
        
        if prefer_ml:
            # Try ML optimization first
            try:
                ml_recommendations = await ml_optimization_service.generate_optimization_recommendations(
                    user_id=current_user.id,
                    target_roas_improvement=10.0
                )
                
                # Check if ML optimization was successful
                if ml_recommendations.get("optimization_summary", {}).get("total_ads_analyzed", 0) > 0:
                    logger.info("Using ML optimization recommendations")
                    # Format ML recommendations into RecommendationResponse structure
                    return await _format_ml_to_recommendation_response(ml_recommendations, current_user.id)
                else:
                    logger.info("ML optimization insufficient, falling back to rule-based")
            except Exception as e:
                logger.warning(f"ML optimization failed: {str(e)}, falling back to rule-based")
        
        # Fallback to rule-based recommendations
        logger.info("Using rule-based recommendations")
        recommendations = await recommendation_service.generate_recommendations(current_user)
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating hybrid recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating hybrid recommendations: {str(e)}"
        )


async def _format_ml_to_recommendation_response(ml_recommendations: dict, user_id: str) -> RecommendationResponse:
    """Format ML optimization results into RecommendationResponse structure."""
    from app.models.recommendation import RecommendationCategory, Recommendation
    from datetime import datetime
    
    categories = []
    summary_stats = {
        "total_opportunities": 0,
        "potential_roas_improvement": "0%",
        "ads_analyzed": ml_recommendations.get("optimization_summary", {}).get("total_ads_analyzed", 0)
    }
    
    # Process CTR improvement recommendations
    if "ctr_improvements" in ml_recommendations:
        ctr_data = ml_recommendations["ctr_improvements"]
        ctr_recommendations = []
        
        for rec in ctr_data.get("recommendations", []):
            ctr_recommendations.append(Recommendation(
                title=f"Increase CTR: {rec['ad_name']}",
                description=rec["optimization_goal"],
                impact="High",
                effort="Medium",
                details={
                    "strategy": "Creative Optimization",
                    "current_performance": rec["current_performance"],
                    "target_performance": rec["target_performance"],
                    "ai_optimized_creative": rec["ai_optimized_creative"],
                    "implementation_strategy": rec["implementation_strategy"],
                    "expected_improvement": rec["expected_roas_improvement"]
                }
            ))
        
        if ctr_recommendations:
            categories.append(RecommendationCategory(
                name="Creative Improvements",
                description=ctr_data["description"],
                recommendations=ctr_recommendations,
                priority="High"
            ))
            summary_stats["total_opportunities"] += len(ctr_recommendations)
    
    # Process spend optimization recommendations
    if "spend_optimizations" in ml_recommendations:
        spend_data = ml_recommendations["spend_optimizations"]
        spend_recommendations = []
        
        for rec in spend_data.get("recommendations", []):
            action_type = rec["action"]
            title = f"{action_type} Spend: {rec['ad_name']}"
            
            spend_recommendations.append(Recommendation(
                title=title,
                description=f"{action_type} from {rec['current_daily_spend']} to {rec['recommended_daily_spend']}",
                impact="High" if action_type == "Scale Up" else "Medium",
                effort="Low",
                details={
                    "strategy": "Spend Optimization",
                    "action": rec["action"],
                    "current_spend": rec["current_daily_spend"],
                    "recommended_spend": rec["recommended_daily_spend"],
                    "reasoning": rec["reasoning"],
                    "expected_improvement": rec["expected_roas_improvement"],
                    "risk_level": rec.get("risk_level", "Medium")
                }
            ))
        
        if spend_recommendations:
            categories.append(RecommendationCategory(
                name="Scale Opportunities",
                description=spend_data["description"],
                recommendations=spend_recommendations,
                priority="High"
            ))
            summary_stats["total_opportunities"] += len(spend_recommendations)
    
    # Process efficiency improvements
    if "efficiency_improvements" in ml_recommendations:
        efficiency_data = ml_recommendations["efficiency_improvements"]
        efficiency_recommendations = []
        
        for rec in efficiency_data.get("recommendations", []):
            efficiency_recommendations.append(Recommendation(
                title=f"Improve {rec['optimization_metric']}: {rec['ad_name']}",
                description=f"Reduce {rec['optimization_metric']} by {rec['improvement_needed']}",
                impact="Medium",
                effort="Medium",
                details={
                    "strategy": "Efficiency Optimization",
                    "metric": rec["optimization_metric"],
                    "current_value": rec["current_value"],
                    "target_value": rec["target_value"],
                    "strategies": rec["optimization_strategies"],
                    "expected_improvement": rec["expected_roas_improvement"]
                }
            ))
        
        if efficiency_recommendations:
            categories.append(RecommendationCategory(
                name="Efficiency Improvements",
                description=efficiency_data["description"],
                recommendations=efficiency_recommendations,
                priority="Medium"
            ))
            summary_stats["total_opportunities"] += len(efficiency_recommendations)
    
    # Calculate average potential improvement
    if summary_stats["total_opportunities"] > 0:
        avg_improvement = ml_recommendations.get("optimization_summary", {}).get("average_predicted_improvement", 0)
        summary_stats["potential_roas_improvement"] = f"{avg_improvement:.1f}%"
    
    return RecommendationResponse(
        goal=ml_recommendations.get("goal", "Improve ROAS by 10%"),
        categories=categories,
        summary=summary_stats,
        generated_at=datetime.now()
    )


@router.get("/", response_model=List[AdRecommendationResponse])
async def get_recommendations(
    status: str = Query("active", description="Filter by recommendation status"),
    ad_id: Optional[str] = Query(None, description="Filter by specific ad ID"),
    limit: int = Query(50, description="Maximum number of recommendations to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Get existing recommendations for the user.
    
    Args:
        status: Filter by recommendation status (active, archived, implemented)
        ad_id: Filter by specific ad ID
        limit: Maximum number of recommendations to return
        current_user: Authenticated user
    
    Returns:
        List of existing recommendations
    """
    try:
        logger.info(f"Getting recommendations for user {current_user.id}")
        
        # Get recommendations from database
        recommendations = await recommendation_service.get_user_recommendations(
            user_id=current_user.id,
            status=status
        )
        
        # Filter by ad_id if specified
        if ad_id:
            recommendations = [rec for rec in recommendations if rec.ad_id == ad_id]
        
        # Limit results
        recommendations = recommendations[:limit]
        
        # Convert to response format
        response_data = []
        for rec in recommendations:
            response_data.append(AdRecommendationResponse(
                _id=rec.id,
                user_id=rec.user_id,
                ad_id=rec.ad_id,
                ad_name=rec.ad_name,
                campaign_id=rec.campaign_id,
                video_id=rec.video_id,
                performance_summary=rec.performance_summary,
                creative_metadata=rec.creative_metadata,
                goal=rec.goal,
                fixed_recommendations=rec.fixed_recommendations,
                ai_recommendations=rec.ai_recommendations,
                predicted_performance=rec.predicted_performance,
                feature_importance=rec.feature_importance,
                generated_at=rec.generated_at,
                status=rec.status,
                implementation_notes=rec.implementation_notes
            ))
        
        logger.info(f"Retrieved {len(response_data)} recommendations")
        return response_data
        
    except Exception as e:
        logger.error(f"Error retrieving recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recommendations: {str(e)}"
        )


# Move specific routes before generic ones to prevent path parameter conflicts

@router.get("/stored-history")
async def get_stored_recommendations_history(
    limit: int = Query(default=10, description="Maximum number of recommendation batches to return"),
    current_user: User = Depends(get_current_user)
):
    """Get historical stored ML recommendations grouped by batch/date."""
    try:
        history = await ml_storage_service.get_recommendations_history(current_user.id, limit)
        return history
    except Exception as e:
        logger.error(f"Error fetching recommendations history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching recommendations history: {str(e)}")


@router.get("/latest")
async def get_latest_recommendations(
    current_user: User = Depends(get_current_user)
):
    """Get latest ML recommendations for the user"""
    try:
        recommendations = await ml_storage_service.get_latest_recommendations(
            user_id=current_user.id
        )
        
        if not recommendations:
            return {"message": "No recommendations found", "recommendations": None}
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error retrieving latest recommendations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving recommendations: {str(e)}"
        )


@router.get("/stored/{batch_id}")
async def get_stored_recommendations(
    batch_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get stored ML recommendations by batch ID"""
    try:
        recommendations = await ml_storage_service.get_recommendations_by_batch_id(
            batch_id=batch_id,
            user_id=current_user.id
        )
        
        if not recommendations:
            raise HTTPException(
                status_code=404,
                detail="Recommendations not found"
            )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error retrieving stored recommendations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving recommendations: {str(e)}"
        )


@router.get("/job-status/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status and progress of a recommendation generation job.
    """
    try:
        job = await job_manager.get_job(job_id, current_user.id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return job.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get("/{recommendation_id}", response_model=AdRecommendationResponse)
async def get_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific recommendation by ID.
    
    Args:
        recommendation_id: ID of the recommendation
        current_user: Authenticated user
    
    Returns:
        Specific recommendation details
    """
    try:
        from app.core.database import get_database
        from bson import ObjectId
        
        db = get_database()
        
        # Get recommendation from database
        recommendation = await db.ad_recommendations.find_one({
            "_id": ObjectId(recommendation_id),
            "user_id": current_user.id
        })
        
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found"
            )
        
        # Convert ObjectId to string
        if "_id" in recommendation and isinstance(recommendation["_id"], ObjectId):
            recommendation["_id"] = str(recommendation["_id"])
        
        # Convert to Pydantic model
        rec = AdRecommendation(**recommendation)
        
        # Convert to response format
        response_data = AdRecommendationResponse(
            _id=rec.id,
            user_id=rec.user_id,
            ad_id=rec.ad_id,
            ad_name=rec.ad_name,
            campaign_id=rec.campaign_id,
            video_id=rec.video_id,
            performance_summary=rec.performance_summary,
            creative_metadata=rec.creative_metadata,
            goal=rec.goal,
            fixed_recommendations=rec.fixed_recommendations,
            ai_recommendations=rec.ai_recommendations,
            predicted_performance=rec.predicted_performance,
            feature_importance=rec.feature_importance,
            generated_at=rec.generated_at,
            status=rec.status,
            implementation_notes=rec.implementation_notes
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recommendation {recommendation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recommendation: {str(e)}"
        )


@router.put("/{recommendation_id}/status")
async def update_recommendation_status(
    recommendation_id: str,
    status: str,
    implementation_notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Update the status of a recommendation.
    
    Args:
        recommendation_id: ID of the recommendation
        status: New status (active, archived, implemented)
        implementation_notes: Optional notes about implementation
        current_user: Authenticated user
    
    Returns:
        Success message
    """
    try:
        from app.core.database import get_database
        from bson import ObjectId
        from datetime import datetime
        
        db = get_database()
        
        # Validate status
        valid_statuses = ["active", "archived", "implemented"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update recommendation
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if implementation_notes:
            update_data["implementation_notes"] = implementation_notes
        
        result = await db.ad_recommendations.update_one(
            {
                "_id": ObjectId(recommendation_id),
                "user_id": current_user.id
            },
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found"
            )
        
        return {"message": "Recommendation status updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating recommendation status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating recommendation status: {str(e)}"
        )


@router.post("/quick-analysis")
async def quick_performance_analysis(
    ad_id: str,
    goal: RecommendationGoal,
    current_user: User = Depends(get_current_user)
):
    """
    Get a quick performance analysis for a specific ad without full recommendation generation.
    
    Args:
        ad_id: ID of the ad to analyze
        goal: Performance improvement goal
        current_user: Authenticated user
    
    Returns:
        Quick analysis results
    """
    try:
        logger.info(f"Performing quick analysis for ad {ad_id}")
        
        # Generate recommendation for single ad
        recommendations = await recommendation_service.generate_recommendations(
            user=current_user,
            ad_ids=[ad_id],
            goal=goal,
            force_refresh=True
        )
        
        if not recommendations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for the specified ad"
            )
        
        recommendation = recommendations[0]
        
        # Return condensed analysis
        return {
            "ad_id": recommendation.ad_id,
            "ad_name": recommendation.ad_name,
            "current_performance": {
                "roas": recommendation.performance_summary.roas,
                "ctr": recommendation.performance_summary.ctr,
                "cpc": recommendation.performance_summary.cpc,
                "spend": recommendation.performance_summary.spend,
                "revenue": recommendation.performance_summary.revenue
            },
            "goal": {
                "metric": recommendation.goal.metric,
                "current_value": recommendation.goal.current_value,
                "target_value": recommendation.goal.target_value,
                "improvement_needed": recommendation.goal.target_improvement
            },
            "top_recommendations": [
                {
                    "title": rec.title,
                    "description": rec.description,
                    "expected_impact": rec.expected_impact,
                    "priority": rec.priority
                }
                for rec in recommendation.fixed_recommendations[:3]
            ],
            "ai_insights": [
                {
                    "suggestion": ai_rec.suggestion,
                    "confidence": ai_rec.confidence_score
                }
                for ai_rec in recommendation.ai_recommendations[:2]
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in quick analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error performing quick analysis: {str(e)}"
        )


# Background Job Models and Endpoints
class GenerateRecommendationsBackgroundRequest(BaseModel):
    use_ml_optimization: bool = True
    target_improvement: float = 10.0
    date_range: Optional[Dict[str, str]] = None


@router.post("/generate-background")
async def generate_recommendations_background_endpoint(
    request: GenerateRecommendationsBackgroundRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Start background recommendation generation job with progress tracking.
    Returns job_id for polling progress.
    """
    try:
        # Create a new job
        job_id = await job_manager.create_job(current_user.id)
        
        # Start background task
        background_tasks.add_task(
            generate_recommendations_background,
            job_id=job_id,
            user_id=current_user.id,
            use_ml_optimization=request.use_ml_optimization,
            target_improvement=request.target_improvement,
            date_range=request.date_range
        )
        
        logger.info(f"Started background recommendation job {job_id} for user {current_user.id}")
        
        return {
            "job_id": job_id,
            "status": "started",
            "message": "Recommendation generation started in background",
            "estimated_duration": "2-5 minutes"
        }
        
    except Exception as e:
        logger.error(f"Failed to start background recommendation job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start recommendation generation: {str(e)}"
        )


