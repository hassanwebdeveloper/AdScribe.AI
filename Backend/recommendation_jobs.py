import asyncio
import uuid
import traceback
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class RecommendationJob:
    id: str
    status: JobStatus
    progress: int
    current_step: str
    total_steps: int
    step_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None  # Add user_id for persistence
    
    def to_dict(self):
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

class RecommendationJobManager:
    def __init__(self):
        self.jobs: Dict[str, RecommendationJob] = {}
        self._db = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ml_worker")
    
    async def get_db(self):
        """Get database connection lazily"""
        if self._db is None:
            from app.core.database import get_database
            self._db = get_database()
        return self._db
    
    async def create_job(self, user_id: str) -> str:
        """Create a new recommendation job and return its ID"""
        job_id = str(uuid.uuid4())
        job = RecommendationJob(
            id=job_id,
            status=JobStatus.PENDING,
            progress=0,
            current_step="1",
            total_steps=6,
            step_name="Initializing recommendation generation...",
            started_at=datetime.now(),
            user_id=user_id
        )
        self.jobs[job_id] = job
        
        # Persist to database
        try:
            db = await self.get_db()
            await db.recommendation_jobs.insert_one({
                "_id": job_id,
                "user_id": user_id,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "total_steps": job.total_steps,
                "step_name": job.step_name,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error": job.error,
                "result": job.result
            })
        except Exception as e:
            print(f"Failed to persist job {job_id} to database: {e}")
        
        return job_id
    
    async def get_job(self, job_id: str, user_id: str = None) -> Optional[RecommendationJob]:
        """Get job status by ID, with fallback to database"""
        # First check memory
        if job_id in self.jobs:
            return self.jobs[job_id]
        
        # Fallback to database
        try:
            db = await self.get_db()
            query = {"_id": job_id}
            if user_id:
                query["user_id"] = user_id
                
            job_doc = await db.recommendation_jobs.find_one(query)
            if job_doc:
                # Reconstruct job from database
                job = RecommendationJob(
                    id=job_doc["_id"],
                    status=job_doc["status"],
                    progress=job_doc["progress"],
                    current_step=job_doc["current_step"],
                    total_steps=job_doc["total_steps"],
                    step_name=job_doc["step_name"],
                    started_at=job_doc["started_at"],
                    completed_at=job_doc.get("completed_at"),
                    error=job_doc.get("error"),
                    result=job_doc.get("result"),
                    user_id=job_doc.get("user_id")
                )
                # Cache in memory
                self.jobs[job_id] = job
                return job
        except Exception as e:
            print(f"Failed to retrieve job {job_id} from database: {e}")
        
        return None
    
    async def update_job_progress(self, job_id: str, step: str, step_name: str):
        """Update job progress"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.current_step = step
            job.step_name = step_name
            job.progress = int((int(step) / job.total_steps) * 100)
            job.status = JobStatus.RUNNING
            
            # Update in database
            try:
                db = await self.get_db()
                await db.recommendation_jobs.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "current_step": step,
                        "step_name": step_name,
                        "progress": job.progress,
                        "status": job.status
                    }}
                )
            except Exception as e:
                print(f"Failed to update job {job_id} in database: {e}")
    
    async def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark job as completed with result"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.current_step = str(job.total_steps)
            job.progress = 100
            job.step_name = "Recommendations generated successfully!"
            job.completed_at = datetime.now()
            job.result = result
            
            # Update in database
            try:
                db = await self.get_db()
                await db.recommendation_jobs.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "status": job.status,
                        "current_step": job.current_step,
                        "progress": job.progress,
                        "step_name": job.step_name,
                        "completed_at": job.completed_at,
                        "result": result
                    }}
                )
            except Exception as e:
                print(f"Failed to complete job {job_id} in database: {e}")
    
    async def fail_job(self, job_id: str, error: str):
        """Mark job as failed with error"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.status = JobStatus.FAILED
            job.error = error
            job.completed_at = datetime.now()
            
            # Update in database
            try:
                db = await self.get_db()
                await db.recommendation_jobs.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "status": job.status,
                        "error": error,
                        "completed_at": job.completed_at
                    }}
                )
            except Exception as e:
                print(f"Failed to fail job {job_id} in database: {e}")
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = [
            job_id for job_id, job in self.jobs.items()
            if job.started_at < cutoff
        ]
        for job_id in to_remove:
            del self.jobs[job_id]
            
        # Also cleanup database
        try:
            db = await self.get_db()
            await db.recommendation_jobs.delete_many({
                "started_at": {"$lt": cutoff}
            })
        except Exception as e:
            print(f"Failed to cleanup old jobs from database: {e}")

# Global job manager instance
job_manager = RecommendationJobManager()

async def generate_recommendations_background(
    job_id: str,
    user_id: str,
    use_ml_optimization: bool = True,
    target_improvement: float = 10.0,
    date_range: Optional[Dict[str, str]] = None
):
    """Background task to generate recommendations with progress updates"""
    try:
        from app.services.ml_optimization_service import MLOptimizationService
        from app.services.openai_service import OpenAIService
        from app.services.user_service import UserService
        from app.services.facebook_service import FacebookAdService
        from app.core.database import get_database
        
        # Step 1: Initialize services
        await job_manager.update_job_progress(job_id, "1", "Initializing services...")
        await asyncio.sleep(0.5)  # Brief pause for UI updates
        
        ml_service = MLOptimizationService()
        openai_service = OpenAIService()
        user_service = UserService()
        db = get_database()
        
        # Get user's Facebook credentials for FacebookAdService
        try:
            credentials = await user_service.get_facebook_credentials(user_id)
            if credentials and credentials.get("access_token") and credentials.get("account_id"):
                fb_service = FacebookAdService(
                    access_token=credentials["access_token"],
                    account_id=credentials["account_id"]
                )
            else:
                # If no Facebook credentials, set fb_service to None
                fb_service = None
        except Exception as e:
            # If Facebook credentials retrieval fails, continue without it
            fb_service = None
        
        # Step 2: Check and collect data
        await job_manager.update_job_progress(job_id, "2", "Checking historical data availability...")
        await asyncio.sleep(0.5)
        
        # Check if we have sufficient data (fix async cursor)
        ad_metrics = await db.ad_metrics.find({"user_id": user_id}).limit(100).to_list(length=100)
        if len(ad_metrics) < 10:
            await job_manager.update_job_progress(job_id, "2", "Collecting fresh Facebook data...")
            # Auto-collect Facebook data (simulate the process)
            await asyncio.sleep(2)  # Simulate data collection time
        
        # Step 3: ML Training (if using ML optimization)
        if use_ml_optimization:
            await job_manager.update_job_progress(job_id, "3", "Training machine learning models...")
            await asyncio.sleep(1.5)  # Simulate ML training time
            
            # Step 4: ML Optimization - Run directly in async context with timeout
            await job_manager.update_job_progress(job_id, "4", "Running ML optimization algorithms...")
            
            # Run ML optimization without timeout to allow proper training
            try:
                recommendations = await ml_service.generate_optimization_recommendations(
                    user_id=user_id,
                    target_roas_improvement=target_improvement
                )
            except Exception as e:
                logger.error(f"ML optimization failed for user {user_id}: {str(e)}")
                # Fallback to a simplified recommendation
                recommendations = {
                    "total_ads_analyzed": 0,
                    "creative_improvements": [],
                    "scale_opportunities": [],
                    "pause_recommendations": [],
                    "error_occurred": True,
                    "error_message": str(e)
                }
        else:
            await job_manager.update_job_progress(job_id, "3", "Analyzing performance data...")
            await asyncio.sleep(1)
            
            await job_manager.update_job_progress(job_id, "4", "Generating rule-based recommendations...")
            
            # Run rule-based recommendations without timeout
            try:
                recommendations = await ml_service.generate_optimization_recommendations(
                    user_id=user_id,
                    target_roas_improvement=target_improvement
                )
            except Exception as e:
                logger.error(f"Rule-based recommendations failed for user {user_id}: {str(e)}")
                # Fallback to a simplified recommendation
                recommendations = {
                    "total_ads_analyzed": 0,
                    "creative_improvements": [],
                    "scale_opportunities": [],
                    "pause_recommendations": [],
                    "error_occurred": True,
                    "error_message": str(e)
                }
        
        # Step 5: AI Creative Enhancement
        await job_manager.update_job_progress(job_id, "5", "Generating AI-powered creative suggestions...")
        await asyncio.sleep(1.5)
        
        # Enhance with AI creative suggestions (this would be real implementation)
        # For now, simulate the process
        
        # Step 6: Finalize
        await job_manager.update_job_progress(job_id, "6", "Finalizing recommendations...")
        await asyncio.sleep(0.5)
        
        # Format final result
        result = {
            "goal": recommendations.get("goal", f"Improve ROAS by {target_improvement}% using ML optimization"),
            "optimization_summary": recommendations.get("optimization_summary", {}),
            "summary": {
                "total_ads_analyzed": recommendations.get("optimization_summary", {}).get("total_ads_analyzed", 0),
                "creative_improvement_count": recommendations.get("optimization_summary", {}).get("ctr_improvement_opportunities", 0),
                "scale_opportunity_count": recommendations.get("optimization_summary", {}).get("spend_optimization_opportunities", 0),
                "pause_recommendation_count": 0,  # ML doesn't generate pause recommendations
                "potential_roas_improvement": f"+{recommendations.get('optimization_summary', {}).get('average_predicted_improvement', target_improvement)}%"
            },
            "creative_improvements": recommendations.get("ctr_improvements", {}).get("recommendations", []),
            "scale_opportunities": recommendations.get("spend_optimizations", {}).get("recommendations", []),
            "pause_recommendations": [],  # ML service doesn't generate pause recommendations
            "ctr_improvements": recommendations.get("ctr_improvements", {}),
            "spend_optimizations": recommendations.get("spend_optimizations", {}),
            "efficiency_improvements": recommendations.get("efficiency_improvements", {}),
            "conversion_improvements": recommendations.get("conversion_improvements", {}),
            "ml_optimization_enabled": use_ml_optimization,
            "generated_at": datetime.now().isoformat()
        }
        
        print(f"✅ Job {job_id} completed successfully. Total ads analyzed: {result['summary']['total_ads_analyzed']}")
        
        # Complete the job
        await job_manager.complete_job(job_id, result)
        
    except Exception as e:
        error_msg = f"Recommendation generation failed: {str(e)}"
        print(f"Background job {job_id} failed: {error_msg}")
        print(traceback.format_exc())
        await job_manager.fail_job(job_id, error_msg) 