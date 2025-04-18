from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.core.config import settings
from app.core.database import connect_to_mongodb, close_mongodb_connection
from app.api.v1.router import api_router

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
    await connect_to_mongodb()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongodb_connection()

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Mount the frontend dist directory (Vite build output)
app.mount("/assets", StaticFiles(directory="../Frontend/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Serve the frontend dist/index.html for all non-API routes
    if not full_path.startswith("api/"):
        frontend_path = "../Frontend/dist/index.html"
        if os.path.exists(frontend_path):
            return FileResponse(frontend_path)
    
    # If the path starts with api/, let it be handled by the API routes
    return {"message": "Welcome to AdScribe AI API"} 