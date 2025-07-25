from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class WorkflowConfigBase(BaseModel):
    """Base model for workflow configuration"""
    workflow_id: str
    name: str
    is_active: bool = True
    body: Dict[str, Any] = {}


class WorkflowConfigCreate(WorkflowConfigBase):
    """Model for creating a workflow configuration"""
    client_id: str
    client_channel_id: Optional[str] = None


class WorkflowConfigUpdate(BaseModel):
    """Model for updating a workflow configuration"""
    workflow_id: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    client_id: Optional[str] = None
    client_channel_id: Optional[str] = None
    body: Optional[Dict[str, Any]] = None


class WorkflowConfigResponse(WorkflowConfigBase):
    """Response model for workflow configuration"""
    id: str
    client_id: str
    client_channel_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
