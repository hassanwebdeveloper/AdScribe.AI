from abc import ABC, abstractmethod
from typing import Protocol

class SchedulerInterface(Protocol):
    """Interface for scheduler operations."""
    
    async def schedule_metrics_collection_for_user(self, user_id: str) -> None:
        """Schedule metrics collection for a user."""
        pass
    
    def remove_metrics_collection_job(self, user_id: str) -> None:
        """Remove metrics collection job for a user."""
        pass
    
    def is_job_running(self, user_id: str) -> bool:
        """Check if a job is currently running for a user."""
        pass 