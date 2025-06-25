import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import random

from app.core.database import get_database, get_mongodb_client
from app.models.job_status import BackgroundJob, JobStatus, JobType, BackgroundJobResponse
from app.services.ai_agent_service import AIAgentService

logger = logging.getLogger(__name__)

class BackgroundJobService:
    """Service to manage background jobs for long-running tasks."""
    
    def __init__(self):
        self.ai_agent_service = AIAgentService()
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._cancellation_tokens: Dict[str, Dict[str, bool]] = {}  # Track cancellation tokens
    
    @property
    def db(self):
        """Get database connection with lazy initialization."""
        mongodb_client = get_mongodb_client()
        if mongodb_client is None:
            raise RuntimeError("MongoDB client is not initialized. Please ensure connect_to_mongodb() was called.")
        
        database = get_database()
        if database is None:
            raise RuntimeError("Failed to get database instance.")
        
        return database
    
    async def start_ad_analysis_job(
        self, 
        user_id: str, 
        access_token: str, 
        account_id: str
    ) -> str:
        """
        Start an ad analysis job in the background.
        
        Args:
            user_id: The user ID
            access_token: Facebook access token
            account_id: Facebook ad account ID
            
        Returns:
            Job ID for tracking
        """
        try:
            # Test database connection before starting
            logger.info(f"Testing database connection before starting job for user {user_id}")
            is_connected = await self.test_database_connection()
            if not is_connected:
                raise RuntimeError("Database connection test failed. Cannot start background job.")
            
            # Check database connection first
            try:
                db = self.db
                logger.debug(f"Database connection established for job creation")
            except Exception as db_error:
                logger.error(f"Failed to get database connection for job creation: {db_error}")
                raise RuntimeError(f"Database connection failed: {db_error}")
            
            # Create job record
            job = BackgroundJob(
                user_id=user_id,
                job_type=JobType.AD_ANALYSIS,
                status=JobStatus.PENDING,
                message="Initializing ad analysis...",
                parameters={
                    "access_token": access_token[:10] + "...",  # Store partial token for debugging
                    "account_id": account_id
                },
                estimated_duration_seconds=300  # 5 minutes estimate
            )
            
            logger.debug(f"Created job object for user {user_id}")
            
            # Insert job into database using safe operation
            async def insert_operation():
                # Remove the _id field to let MongoDB generate it
                job_data = job.model_dump(by_alias=True)
                if '_id' in job_data:
                    del job_data['_id']  # Let MongoDB generate the ObjectId
                return await db.background_jobs.insert_one(job_data)
            
            result = await self._safe_db_operation(f"create_job_{user_id}", insert_operation)
            job_id = str(result.inserted_id)  # Convert ObjectId to string for API
            
            logger.info(f"Created background job {job_id} for user {user_id}")
            logger.debug(f"Job stored with ObjectId: {result.inserted_id}")
            
            # Create cancellation token for this job immediately
            cancellation_token = {"cancelled": False}
            self._cancellation_tokens[job_id] = cancellation_token
            
            # Start the background task
            task = asyncio.create_task(
                self._run_ad_analysis_job(job_id, user_id, access_token, account_id)
            )
            self._running_jobs[job_id] = task
            
            logger.info(f"Job {job_id} added to running jobs and cancellation tokens")
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error starting ad analysis job for user {user_id}: {e}", exc_info=True)
            raise
    
    async def get_job_status(self, job_id: str, user_id: str) -> Optional[BackgroundJobResponse]:
        """
        Get the status of a background job.
        
        Args:
            job_id: The job ID
            user_id: The user ID (for security)
            
        Returns:
            Job status or None if not found
        """
        try:
            # Validate inputs
            if not job_id or not user_id:
                logger.warning(f"Invalid parameters: job_id='{job_id}', user_id='{user_id}'")
                return None
            
            # Check database connection
            try:
                db = self.db
                logger.debug(f"Database connection established for job status query")
            except Exception as db_error:
                logger.error(f"Failed to get database connection: {db_error}")
                raise RuntimeError(f"Database connection failed: {db_error}")
            
            # Convert job_id to ObjectId if it's a valid ObjectId string
            try:
                query_id = ObjectId(job_id)
                logger.debug(f"Searching for job with ObjectId: {query_id}")
            except Exception as e:
                logger.warning(f"Could not convert job_id '{job_id}' to ObjectId: {e}")
                return None
            
            logger.debug(f"Executing database query for job {job_id} and user {user_id}")
            
            # Execute the database query with detailed logging
            job_doc = await db.background_jobs.find_one({
                "_id": query_id,
                "user_id": user_id
            })
            
            logger.debug(f"Database query completed for job {job_id}")
            
            if not job_doc:
                logger.info(f"Job {job_id} not found for user {user_id}")
                return None
            
            # Convert ObjectId to string for the response model
            if '_id' in job_doc and isinstance(job_doc['_id'], ObjectId):
                job_doc['_id'] = str(job_doc['_id'])
            
            logger.debug(f"Found job {job_id} with status: {job_doc.get('status', 'unknown')}")
            return BackgroundJobResponse(**job_doc)
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}", exc_info=True)
            return None
    
    async def get_user_jobs(self, user_id: str, limit: int = 10) -> List[BackgroundJobResponse]:
        """
        Get recent jobs for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of jobs to return
            
        Returns:
            List of user jobs
        """
        try:
            # Clean up old jobs older than 7 days (run occasionally)
            if random.random() < 0.1:  # 10% chance to trigger cleanup
                await self.cleanup_old_jobs(days_old=7)
            
            cursor = self.db.background_jobs.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            
            jobs = await cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings for the response models
            for job in jobs:
                if '_id' in job and isinstance(job['_id'], ObjectId):
                    job['_id'] = str(job['_id'])
            
            return [BackgroundJobResponse(**job) for job in jobs]
            
        except Exception as e:
            logger.error(f"Error getting user jobs for {user_id}: {e}", exc_info=True)
            return []
    
    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: The job ID
            user_id: The user ID (for security)
            
        Returns:
            True if cancelled successfully
        """
        try:
            logger.info(f"Cancelling job {job_id} for user {user_id}")
            logger.debug(f"Current cancellation tokens: {list(self._cancellation_tokens.keys())}")
            logger.debug(f"Current running jobs: {list(self._running_jobs.keys())}")
            
            # Set cancellation flag first to stop AI agent nodes
            if job_id in self._cancellation_tokens:
                self._cancellation_tokens[job_id]["cancelled"] = True
                logger.info(f"Set cancellation flag for job {job_id} - AI agent nodes should stop now")
            else:
                logger.warning(f"No cancellation token found for job {job_id} - job may have already completed")
            
            # Cancel the running task if it exists
            if job_id in self._running_jobs:
                task = self._running_jobs[job_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled asyncio task for job {job_id}")
                    
                    # Wait a bit for graceful cancellation
                    try:
                        await asyncio.wait_for(task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.info(f"Task cancellation completed for job {job_id}")
                    
                # Remove from running jobs after cancellation (if still present)
                if job_id in self._running_jobs:
                    del self._running_jobs[job_id]
                    logger.info(f"Removed job {job_id} from running jobs")
            else:
                logger.info(f"Job {job_id} was not in running jobs (may have already completed)")
            
            # Don't delete the cancellation token here - let the finally block in _run_ad_analysis_job clean it up
            # This ensures the AI agent nodes can still check the cancellation status
            
            # Update job status in database
            try:
                query_id = ObjectId(job_id)
                logger.debug(f"Converting job_id to ObjectId for cancellation: {query_id}")
            except Exception as e:
                logger.warning(f"Could not convert job_id '{job_id}' to ObjectId for cancellation: {e}")
                return False
            
            result = await self.db.background_jobs.update_one(
                {"_id": query_id, "user_id": user_id},
                {
                    "$set": {
                        "status": JobStatus.CANCELLED,
                        "message": "Job cancelled by user",
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Successfully cancelled job {job_id} - cancellation token remains active for AI agent")
            else:
                logger.warning(f"Could not update job status for cancellation: {job_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
            return False
    
    async def _run_ad_analysis_job(
        self, 
        job_id: str, 
        user_id: str, 
        access_token: str, 
        account_id: str
    ):
        """
        Execute the ad analysis job in the background.
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"=== Starting background job execution for job_id: {job_id} ===")
            
            # Convert job_id to ObjectId for database operations
            try:
                db_job_id = ObjectId(job_id)
                logger.debug(f"Converted job_id to ObjectId: {db_job_id}")
            except Exception as e:
                logger.error(f"Failed to convert job_id '{job_id}' to ObjectId: {e}")
                db_job_id = job_id  # Fallback to string
                logger.debug(f"Using string job_id as fallback: {db_job_id}")
            
            logger.info(f"Step 1: Updating job status to RUNNING for job {job_id}")
            
            # Update job status to running
            await self._update_job_status(
                db_job_id, 
                JobStatus.RUNNING, 
                "Starting ad analysis...", 
                progress=5,
                started_at=start_time
            )
            
            logger.info(f"Step 2: Job status updated successfully for job {job_id}")
            logger.info(f"Starting ad analysis job {job_id} for user {user_id}")
            
            # Progress update: Fetching analyzed video IDs
            logger.info(f"Step 3: Updating progress to 10% for job {job_id}")
            await self._update_job_status(
                db_job_id, 
                JobStatus.RUNNING, 
                "Checking previously analyzed videos...", 
                progress=10
            )
            
            logger.info(f"Step 4: Creating progress callback for job {job_id}")
            
            # Get the existing cancellation token for this job
            cancellation_token = self._cancellation_tokens.get(job_id, {"cancelled": False})
            
            # Create progress callback function
            async def progress_callback(progress: int, message: str):
                """Callback to update job progress during AI analysis"""
                try:
                    # Ensure progress is within bounds and make room for final steps
                    clamped_progress = max(10, min(progress, 88))
                    logger.debug(f"Progress callback: {clamped_progress}% - {message} for job {job_id}")
                    await self._update_job_status(
                        db_job_id,
                        JobStatus.RUNNING,
                        message,
                        progress=clamped_progress
                    )
                    logger.info(f"Job {job_id} progress: {clamped_progress}% - {message}")
                except Exception as e:
                    logger.error(f"Error in progress callback for job {job_id}: {e}")
            
            logger.info(f"Step 5: Starting AI Agent analysis for job {job_id}")
            
            # Run the AI Agent analysis with progress callback and cancellation token
            analysis_results = await self.ai_agent_service.analyze_ads_with_ai_agent(
                user_id=user_id,
                access_token=access_token,
                account_id=account_id,
                progress_callback=progress_callback,
                cancellation_token=cancellation_token
            )
            
            logger.info(f"Step 6: AI Agent analysis completed for job {job_id}. Results: {len(analysis_results)}")
            
            # Progress update: Analysis complete
            await self._update_job_status(
                db_job_id, 
                JobStatus.RUNNING, 
                "Finalizing results...", 
                progress=90
            )
            
            logger.info(f"Step 7: Calculating duration for job {job_id}")
            
            # Calculate actual duration
            end_time = datetime.utcnow()
            duration_seconds = int((end_time - start_time).total_seconds())
            
            logger.info(f"Step 8: Updating job to COMPLETED status for job {job_id}")
            
            # Update job status to completed
            await self._update_job_status(
                db_job_id, 
                JobStatus.COMPLETED, 
                f"Analysis completed successfully! Processed {len(analysis_results)} ads.",
                progress=100,
                completed_at=end_time,
                result_count=len(analysis_results),
                actual_duration_seconds=duration_seconds
            )
            
            logger.info(f"=== Completed ad analysis job {job_id} for user {user_id}. Processed {len(analysis_results)} ads in {duration_seconds}s ===")
            
        except asyncio.CancelledError:
            logger.info(f"Ad analysis job {job_id} was cancelled")
            await self._update_job_status(
                db_job_id, 
                JobStatus.CANCELLED, 
                "Job was cancelled",
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"=== ERROR in ad analysis job {job_id}: {e} ===", exc_info=True)
            await self._update_job_status(
                db_job_id, 
                JobStatus.FAILED, 
                "Analysis failed due to an error",
                error_message=str(e),
                completed_at=datetime.utcnow()
            )
        
        finally:
            # Clean up running job reference and cancellation token
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
                logger.info(f"Cleaned up running job reference for {job_id}")
            if job_id in self._cancellation_tokens:
                del self._cancellation_tokens[job_id]
                logger.info(f"Cleaned up cancellation token for {job_id}")
    
    async def _update_job_status(
        self, 
        job_id: Any, 
        status: JobStatus, 
        message: str, 
        progress: int = None,
        error_message: str = None,
        started_at: datetime = None,
        completed_at: datetime = None,
        result_count: int = None,
        actual_duration_seconds: int = None
    ):
        """Update job status in the database."""
        try:
            # Check database connection first
            try:
                db = self.db
                logger.debug(f"Database connection established for job status update")
            except Exception as db_error:
                logger.error(f"Failed to get database connection for job update: {db_error}")
                raise RuntimeError(f"Database connection failed: {db_error}")
            
            update_data = {
                "status": status,
                "message": message
            }
            
            if progress is not None:
                update_data["progress"] = progress
            if error_message is not None:
                update_data["error_message"] = error_message
            if started_at is not None:
                update_data["started_at"] = started_at
            if completed_at is not None:
                update_data["completed_at"] = completed_at
            if result_count is not None:
                update_data["result_count"] = result_count
            if actual_duration_seconds is not None:
                update_data["actual_duration_seconds"] = actual_duration_seconds
            
            logger.debug(f"Updating job {job_id} with data: {update_data}")
            
            # Use safe database operation wrapper
            async def update_operation():
                return await db.background_jobs.update_one(
                    {"_id": job_id},
                    {"$set": update_data}
                )
            
            result = await self._safe_db_operation(f"update_job_status_{job_id}", update_operation)
            
            logger.debug(f"Job update completed for {job_id}. Modified count: {result.modified_count}")
            
            if result.modified_count == 0:
                logger.warning(f"No documents were modified when updating job {job_id}")
            
        except Exception as e:
            logger.error(f"Error updating job status for {job_id}: {e}", exc_info=True)
    
    async def cleanup_old_jobs(self, days_old: int = 7):
        """
        Clean up old completed jobs.
        
        Args:
            days_old: Delete jobs older than this many days
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            result = await self.db.background_jobs.delete_many({
                "status": {"$in": [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]},
                "created_at": {"$lt": cutoff_date}
            })
            
            logger.info(f"Cleaned up {result.deleted_count} old jobs")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}", exc_info=True)
            return 0
    
    async def test_database_connection(self):
        """Test the database connection by performing a simple operation."""
        try:
            db = self.db
            # Try a simple operation to test connectivity
            result = await db.background_jobs.count_documents({})
            logger.info(f"Database connection test successful. Found {result} background jobs.")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}", exc_info=True)
            return False
    
    async def _safe_db_operation(self, operation_name: str, operation_func):
        """
        Wrapper for database operations with timeout and retry logic.
        
        Args:
            operation_name: Name of the operation for logging
            operation_func: Async function that performs the database operation
            
        Returns:
            Result of the operation or raises exception
        """
        max_retries = 3
        timeout_seconds = 10
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempting {operation_name} (attempt {attempt + 1}/{max_retries})")
                
                # Use asyncio.wait_for to add timeout
                result = await asyncio.wait_for(operation_func(), timeout=timeout_seconds)
                
                logger.debug(f"{operation_name} completed successfully")
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"{operation_name} timed out after {timeout_seconds}s (attempt {attempt + 1})")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"{operation_name} failed after {max_retries} attempts due to timeout")
                await asyncio.sleep(1)  # Wait before retry
                
            except Exception as e:
                logger.error(f"{operation_name} failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)  # Wait before retry 