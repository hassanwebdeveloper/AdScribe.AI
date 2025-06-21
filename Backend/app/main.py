from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.core.config import settings
from app.core.database import connect_to_mongodb, close_mongodb_connection, get_database
from app.api.v1.router import api_router
from app.services.scheduler_service import SchedulerService

# Define variable for scheduler service
scheduler_service = None

app = FastAPI(
    title="AdScribe.AI API",
    description="Backend API for AdScribe.AI application",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection events
@app.on_event("startup")
async def startup_db_client():
    global scheduler_service
    
    # First establish database connection
    await connect_to_mongodb()
    
    # Ensure collections exist
    db = get_database()
    collections = await db.list_collection_names()
    
    # Create collections if they don't exist
    if "users" not in collections:
        await db.create_collection("users")
        await db.users.create_index("email", unique=True)
    
    if "chat_sessions" not in collections:
        await db.create_collection("chat_sessions")
        await db.chat_sessions.create_index("user_id")
    
    if "analysis_settings" not in collections:
        await db.create_collection("analysis_settings")
        await db.analysis_settings.create_index("user_id", unique=True)
        
    if "ad_analyses" not in collections:
        await db.create_collection("ad_analyses")
        await db.ad_analyses.create_index("user_id")
        
    if "ad_metrics" not in collections:
        await db.create_collection("ad_metrics")
        await db.ad_metrics.create_index([("user_id", 1), ("ad_id", 1), ("collected_at", -1)])
    
    # Create background_jobs collection for job tracking
    if "background_jobs" not in collections:
        await db.create_collection("background_jobs")
        await db.background_jobs.create_index("user_id")
        await db.background_jobs.create_index("status")
        await db.background_jobs.create_index("created_at")
    
    # Create prompt_templates collection for prompt management
    if "prompt_templates" not in collections:
        await db.create_collection("prompt_templates")
        await db.prompt_templates.create_index("prompt_key", unique=True)
        await db.prompt_templates.create_index("category")
        
        # Initialize default prompts
        from app.services.prompt_template_service import PromptTemplateService
        await PromptTemplateService.initialize_default_prompts()
    
    # Create admin authentication collections
    if "admin_otps" not in collections:
        await db.create_collection("admin_otps")
        await db.admin_otps.create_index("email")
        await db.admin_otps.create_index("expires_at")
    
    if "admin_sessions" not in collections:
        await db.create_collection("admin_sessions")
        await db.admin_sessions.create_index("email")
        await db.admin_sessions.create_index("token")
        await db.admin_sessions.create_index("expires_at")
    
    # Create classification_classes collection for text classifier
    if "classification_classes" not in collections:
        await db.create_collection("classification_classes")
        await db.classification_classes.create_index("name", unique=True)
        await db.classification_classes.create_index("is_active")
        
        # Initialize default classification classes
        from app.services.classification_classes_service import ClassificationClassesService
        await ClassificationClassesService.initialize_default_classification_classes()
    
    # Create ad_recommendations collection for the recommendation system
    if "ad_recommendations" not in collections:
        await db.create_collection("ad_recommendations")
        await db.ad_recommendations.create_index("user_id")
        await db.ad_recommendations.create_index("ad_id")
        await db.ad_recommendations.create_index("status")
        await db.ad_recommendations.create_index("generated_at")
        await db.ad_recommendations.create_index([("user_id", 1), ("status", 1)])
    
    # Create creative_patterns collection for pattern analysis
    if "creative_patterns" not in collections:
        await db.create_collection("creative_patterns")
        await db.creative_patterns.create_index("user_id")
        await db.creative_patterns.create_index("pattern_type")
        await db.creative_patterns.create_index("is_active")
        await db.creative_patterns.create_index([("user_id", 1), ("pattern_type", 1)])
    
    # Create ml_models collection for storing model metadata
    if "ml_models" not in collections:
        await db.create_collection("ml_models")
        await db.ml_models.create_index("user_id")
        await db.ml_models.create_index("model_type")
        await db.ml_models.create_index("created_at")
        await db.ml_models.create_index([("user_id", 1), ("model_type", 1)])

    # Initialize scheduler service after database connection is established
    scheduler_service = SchedulerService()
    
    # Start the scheduler and schedule metrics collection for all users
    scheduler_service.start()
    await scheduler_service.schedule_metrics_collection_for_all_users()

@app.on_event("shutdown")
async def shutdown_db_client():
    global scheduler_service
    
    # Shutdown the scheduler
    if scheduler_service:
        scheduler_service.shutdown()
    
    # Close MongoDB connection
    await close_mongodb_connection()

# Include API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Mount the frontend assets
if os.path.exists("../Frontend/dist/assets"):
    app.mount("/assets", StaticFiles(directory="../Frontend/dist/assets"), name="assets")

# Serve frontend for all non-API routes
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Check if this is an API route (should be handled by FastAPI routers)
    if full_path.startswith("api/"):
        return {"message": "API route not found"}
    
    # For admin/prompts and other frontend routes, serve the React app
    frontend_path = "../Frontend/dist/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    
    return {"message": "Welcome to AdScribe AI API"} 