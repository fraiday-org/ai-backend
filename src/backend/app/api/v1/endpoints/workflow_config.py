from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.v1.deps import verify_api_key
from app.models.schemas.workflow_config import (
    WorkflowConfigCreate,
    WorkflowConfigUpdate,
    WorkflowConfigResponse,
)
from app.services.workflow_config import WorkflowConfigService

router = APIRouter(prefix="/workflow-configs", tags=["workflow-configs"])


@router.post("", response_model=WorkflowConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_config(
    config: WorkflowConfigCreate,
    api_key: str = Depends(verify_api_key),
):
    """
    Create a new workflow configuration.
    """
    try:
        result = WorkflowConfigService.create_workflow_config(
            client_id=config.client_id,
            workflow_id=config.workflow_id,
            name=config.name,
            client_channel_id=config.client_channel_id,
            is_active=config.is_active,
            body=config.body,
        )
        return WorkflowConfigResponse(
            id=str(result.id),
            client_id=str(result.client.client_id),
            client_channel_id=str(result.client_channel.id) if result.client_channel else None,
            name=result.name,
            workflow_id=result.workflow_id,
            is_active=result.is_active,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workflow config: {str(e)}",
        )


@router.get("/{config_id}", response_model=WorkflowConfigResponse)
async def get_workflow_config(
    config_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Get a specific workflow configuration by ID.
    """
    try:
        result = WorkflowConfigService.get_workflow_config_by_id(config_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow config with ID {config_id} not found",
            )
        return WorkflowConfigResponse(
            id=str(result.id),
            client_id=str(result.client.client_id),
            client_channel_id=str(result.client_channel.id) if result.client_channel else None,
            name=result.name,
            workflow_id=result.workflow_id,
            is_active=result.is_active,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workflow config: {str(e)}",
        )


@router.get("", response_model=List[WorkflowConfigResponse])
async def list_workflow_configs(
    client_id: Optional[str] = Query(None),
    client_channel_id: Optional[str] = Query(None),
    api_key: str = Depends(verify_api_key),
):
    """
    List workflow configurations with optional filtering.
    """
    try:
        configs = WorkflowConfigService.list_workflow_configs(
            client_id=client_id,
            client_channel_id=client_channel_id,
        )
        return [
            WorkflowConfigResponse(
                id=str(result.id),
                client_id=str(result.client.client_id),
                client_channel_id=str(result.client_channel.id) if result.client_channel else None,
                name=result.name,
                workflow_id=result.workflow_id,
                is_active=result.is_active,
                body=result.body,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
            for result in configs
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflow configs: {str(e)}",
        )


@router.put("/{config_id}", response_model=WorkflowConfigResponse)
async def update_workflow_config(
    config_id: str,
    config_update: WorkflowConfigUpdate,
    api_key: str = Depends(verify_api_key),
):
    """
    Update a workflow configuration.
    """
    try:
        result = WorkflowConfigService.update_workflow_config(
            config_id=config_id,
            workflow_id=config_update.workflow_id,
            is_active=config_update.is_active,
            client_id=config_update.client_id,
            client_channel_id=config_update.client_channel_id,
            body=config_update.body,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow config with ID {config_id} not found",
            )
        return WorkflowConfigResponse(
            id=str(result.id),
            client_id=str(result.client.client_id),
            client_channel_id=str(result.client_channel.id) if result.client_channel else None,
            name=result.name,
            workflow_id=result.workflow_id,
            is_active=result.is_active,
            created_at=result.created_at,
            updated_at=result.updated_at,
            body=result.body,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow config: {str(e)}",
        )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_config(
    config_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Delete a workflow configuration.
    """
    try:
        success = WorkflowConfigService.delete_workflow_config(config_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow config with ID {config_id} not found",
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete workflow config: {str(e)}",
        )
