from typing import List, Optional, Dict
from datetime import datetime
import logging

from app.core.database import get_database
from app.models.classification_classes import ClassificationClasses, ClassificationClassesCreate, ClassificationClassesUpdate

logger = logging.getLogger(__name__)

class ClassificationClassesService:
    """Service for managing classification classes"""
    
    @staticmethod
    async def get_all_classification_classes() -> List[ClassificationClasses]:
        """Get all classification classes"""
        try:
            db = get_database()
            cursor = db.classification_classes.find({"is_active": True}).sort("created_at", -1)
            
            classes_list = []
            async for doc in cursor:
                classes_list.append(ClassificationClasses(**doc))
            
            return classes_list
            
        except Exception as e:
            logger.error(f"Error getting classification classes: {e}")
            return []
    
    @staticmethod
    async def get_classification_classes_by_name(name: str) -> Optional[ClassificationClasses]:
        """Get classification classes by name"""
        try:
            db = get_database()
            doc = await db.classification_classes.find_one({"name": name, "is_active": True})
            
            if doc:
                return ClassificationClasses(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting classification classes '{name}': {e}")
            return None
    
    @staticmethod
    async def create_classification_classes(data: ClassificationClassesCreate) -> ClassificationClasses:
        """Create new classification classes"""
        try:
            db = get_database()
            
            # Check if name already exists
            existing = await ClassificationClassesService.get_classification_classes_by_name(data.name)
            if existing:
                raise ValueError(f"Classification classes with name '{data.name}' already exists")
            
            classes = ClassificationClasses(
                name=data.name,
                description=data.description,
                classes=data.classes
            )
            
            result = await db.classification_classes.insert_one(classes.model_dump(by_alias=True))
            classes.id = str(result.inserted_id)
            
            logger.info(f"Created classification classes: {data.name}")
            return classes
            
        except Exception as e:
            logger.error(f"Error creating classification classes: {e}")
            raise e
    
    @staticmethod
    async def update_classification_classes(name: str, data: ClassificationClassesUpdate) -> Optional[ClassificationClasses]:
        """Update classification classes"""
        try:
            db = get_database()
            
            # Build update data
            update_data = {}
            if data.name is not None:
                update_data["name"] = data.name
            if data.description is not None:
                update_data["description"] = data.description
            if data.classes is not None:
                update_data["classes"] = data.classes
            if data.is_active is not None:
                update_data["is_active"] = data.is_active
            
            update_data["updated_at"] = datetime.utcnow()
            
            result = await db.classification_classes.update_one(
                {"name": name, "is_active": True},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                updated_doc = await db.classification_classes.find_one({"name": data.name or name})
                if updated_doc:
                    logger.info(f"Updated classification classes: {name}")
                    return ClassificationClasses(**updated_doc)
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating classification classes '{name}': {e}")
            raise e
    
    @staticmethod
    async def delete_classification_classes(name: str) -> bool:
        """Delete classification classes (soft delete)"""
        try:
            db = get_database()
            
            result = await db.classification_classes.update_one(
                {"name": name, "is_active": True},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Deleted classification classes: {name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting classification classes '{name}': {e}")
            return False
    
    @staticmethod
    async def initialize_default_classification_classes():
        """Initialize default classification classes from the agent"""
        try:
            # Default classification classes from Ad Script Generator Agent
            default_classes = [
                {
                    "name": "ad_script_generator",
                    "description": "Classification classes for Ad Script Generator Agent",
                    "classes": {
                        "ad_script": "If user wants to write new ad speech or video script or text but not code.",
                        "default": "it is default category all remaining query should lie under this category"
                    }
                }
            ]
            
            for class_data in default_classes:
                existing = await ClassificationClassesService.get_classification_classes_by_name(class_data["name"])
                if not existing:
                    create_data = ClassificationClassesCreate(**class_data)
                    await ClassificationClassesService.create_classification_classes(create_data)
                    logger.info(f"Initialized default classification classes: {class_data['name']}")
                else:
                    logger.info(f"Classification classes '{class_data['name']}' already exists, skipping")
                    
        except Exception as e:
            logger.error(f"Error initializing default classification classes: {e}")
            raise e 