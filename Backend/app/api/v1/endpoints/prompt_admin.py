from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging

from app.models.prompt_template import (
    PromptTemplate, 
    PromptTemplateCreate, 
    PromptTemplateUpdate, 
    PromptTemplateResponse
)
from app.models import ClassificationClasses, ClassificationClassesCreate, ClassificationClassesUpdate, ClassificationClassesResponse
from app.services.prompt_template_service import PromptTemplateService
from app.services.classification_classes_service import ClassificationClassesService
from app.middleware.admin_auth import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/prompts", response_model=List[PromptTemplateResponse], dependencies=[Depends(verify_admin_token)])
async def get_all_prompts():
    """Get all prompt templates for admin panel"""
    try:
        templates = await PromptTemplateService.get_all_prompt_templates()
        return [PromptTemplateResponse(**template.dict()) for template in templates]
    except Exception as e:
        logger.error(f"Error getting prompt templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve prompt templates")

@router.get("/prompts/{prompt_key}", response_model=PromptTemplateResponse, dependencies=[Depends(verify_admin_token)])
async def get_prompt(prompt_key: str):
    """Get a specific prompt template"""
    try:
        template = await PromptTemplateService.get_prompt_template(prompt_key)
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return PromptTemplateResponse(**template.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt template {prompt_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve prompt template")

@router.post("/prompts", response_model=PromptTemplateResponse, dependencies=[Depends(verify_admin_token)])
async def create_prompt(prompt_data: PromptTemplateCreate):
    """Create a new prompt template"""
    try:
        template = await PromptTemplateService.create_prompt_template(prompt_data)
        return PromptTemplateResponse(**template.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating prompt template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create prompt template")

@router.put("/prompts/{prompt_key}", response_model=PromptTemplateResponse, dependencies=[Depends(verify_admin_token)])
async def update_prompt(prompt_key: str, update_data: PromptTemplateUpdate):
    """Update a prompt template"""
    try:
        template = await PromptTemplateService.update_prompt_template(prompt_key, update_data)
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return PromptTemplateResponse(**template.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prompt template {prompt_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update prompt template")

@router.delete("/prompts/{prompt_key}", dependencies=[Depends(verify_admin_token)])
async def delete_prompt(prompt_key: str):
    """Delete a prompt template"""
    try:
        success = await PromptTemplateService.delete_prompt_template(prompt_key)
        if not success:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return {"message": "Prompt template deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prompt template {prompt_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete prompt template")

@router.post("/prompts/initialize-defaults", dependencies=[Depends(verify_admin_token)])
async def initialize_default_prompts():
    """Initialize default prompt templates from existing codebase"""
    try:
        await PromptTemplateService.initialize_default_prompts()
        return {"message": "Default prompts initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing default prompts: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize default prompts")

@router.post("/prompts/{prompt_key}/initialize-default", dependencies=[Depends(verify_admin_token)])
async def initialize_default_prompt(prompt_key: str):
    """Initialize a specific default prompt by its key"""
    try:
        success = await PromptTemplateService.initialize_default_prompt_by_key(prompt_key)
        if not success:
            raise HTTPException(status_code=404, detail=f"No default prompt found for key: {prompt_key}")
        return {"message": f"Default prompt '{prompt_key}' initialized successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing default prompt {prompt_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize default prompt")

@router.get("/models", dependencies=[Depends(verify_admin_token)])
async def get_available_models():
    """Get list of available OpenAI models"""
    return {
        "models": [
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ]
    }

# Classification Classes endpoints
@router.get("/classification-classes", response_model=List[ClassificationClassesResponse], dependencies=[Depends(verify_admin_token)])
async def get_all_classification_classes():
    """Get all classification classes"""
    try:
        classes_list = await ClassificationClassesService.get_all_classification_classes()
        return [ClassificationClassesResponse(**cls.model_dump()) for cls in classes_list]
    except Exception as e:
        logger.error(f"Error getting classification classes: {e}")
        raise HTTPException(status_code=500, detail="Failed to get classification classes")

@router.post("/classification-classes", response_model=ClassificationClassesResponse, dependencies=[Depends(verify_admin_token)])
async def create_classification_classes(data: ClassificationClassesCreate):
    """Create new classification classes"""
    try:
        classes = await ClassificationClassesService.create_classification_classes(data)
        return ClassificationClassesResponse(**classes.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating classification classes: {e}")
        raise HTTPException(status_code=500, detail="Failed to create classification classes")

@router.put("/classification-classes/{name}", response_model=ClassificationClassesResponse, dependencies=[Depends(verify_admin_token)])
async def update_classification_classes(name: str, data: ClassificationClassesUpdate):
    """Update classification classes"""
    try:
        updated_classes = await ClassificationClassesService.update_classification_classes(name, data)
        if not updated_classes:
            raise HTTPException(status_code=404, detail="Classification classes not found")
        return ClassificationClassesResponse(**updated_classes.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating classification classes {name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update classification classes")

@router.delete("/classification-classes/{name}", dependencies=[Depends(verify_admin_token)])
async def delete_classification_classes(name: str):
    """Delete classification classes"""
    try:
        success = await ClassificationClassesService.delete_classification_classes(name)
        if not success:
            raise HTTPException(status_code=404, detail="Classification classes not found")
        return {"message": "Classification classes deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting classification classes {name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete classification classes")

@router.post("/classification-classes/initialize-defaults", dependencies=[Depends(verify_admin_token)])
async def initialize_default_classification_classes():
    """Initialize default classification classes"""
    try:
        await ClassificationClassesService.initialize_default_classification_classes()
        return {"message": "Default classification classes initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing default classification classes: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize default classification classes")

@router.post("/classification-classes/refresh-agent", dependencies=[Depends(verify_admin_token)])
async def refresh_agent_classification_classes():
    """Refresh classification classes in the Ad Script Generator Agent"""
    try:
        from app.core.AI_Agent.Agent.Ad_Script_Generator_Agent import ad_script_generator_agent
        await ad_script_generator_agent.initialize_from_database()
        return {"message": "Agent classification classes refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing agent classification classes: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh agent classification classes") 