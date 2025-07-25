from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.api.v1.deps import verify_api_key
from app.schemas.events.event_processor_config import (
    ProcessorConfigCreate,
    ProcessorConfigUpdate,
    ProcessorConfigResponse,
)
from app.services.events.event_processor_config import ProcessorConfigService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/event-processors", tags=["Event Processors"])


@router.post("", response_model=ProcessorConfigResponse)
async def create_processor_config(data: ProcessorConfigCreate, api_key: str = Depends(verify_api_key)):
    """
    Create a new event processor configuration.
    Requires admin API key.
    """
    try:
        processor = ProcessorConfigService.create_processor_config(
            name=data.name,
            client_id=data.client_id,
            processor_type=data.processor_type,
            config=data.config,
            event_types=data.event_types,
            entity_types=data.entity_types,
            description=data.description,
            is_active=data.is_active,
            client_channel_id=data.client_channel_id,
        )

        return ProcessorConfigResponse.from_db_model(processor)
    except ValueError as e:
        logger.error(f"Error creating processor config: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating processor config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=List[ProcessorConfigResponse])
async def list_processor_configs(
    client_id: Optional[str] = None,
    processor_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    api_key: str = Depends(verify_api_key),
):
    """
    List event processor configurations with optional filtering.
    Requires admin API key.
    """
    try:
        processors = ProcessorConfigService.list_processors(
            client_id=client_id, processor_type=processor_type, is_active=is_active, skip=skip, limit=limit
        )

        # Convert to response models
        return [ProcessorConfigResponse.from_db_model(processor) for processor in processors]
    except Exception as e:
        logger.error(f"Error listing processor configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{processor_id}", response_model=ProcessorConfigResponse)
async def get_processor_config(processor_id: str, api_key: str = Depends(verify_api_key)):
    """
    Get an event processor configuration by ID.
    Requires admin API key.
    """
    try:
        processor = ProcessorConfigService.get_processor_by_id(processor_id)
        if not processor:
            raise HTTPException(status_code=404, detail="Processor config not found")

        return ProcessorConfigResponse.from_db_model(processor)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processor config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{processor_id}", response_model=ProcessorConfigResponse)
async def update_processor_config(
    processor_id: str, data: ProcessorConfigUpdate, api_key: str = Depends(verify_api_key)
):
    """
    Update an event processor configuration.
    Requires admin API key.
    """
    try:
        update_data = data.model_dump(exclude_unset=True)
        processor = ProcessorConfigService.update_processor_config(processor_id=processor_id, **update_data)

        if not processor:
            raise HTTPException(status_code=404, detail="Processor config not found")

        return ProcessorConfigResponse.from_db_model(processor)
    except ValueError as e:
        logger.error(f"Error updating processor config: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating processor config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{processor_id}")
async def deactivate_processor_config(processor_id: str, api_key: str = Depends(verify_api_key)):
    """
    Deactivate an event processor configuration.
    Requires admin API key.
    """
    try:
        success = ProcessorConfigService.deactivate_processor(processor_id)
        if not success:
            raise HTTPException(status_code=404, detail="Processor config not found")

        return {"message": "Processor configuration deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating processor config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
