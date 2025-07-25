from fastapi import APIRouter, HTTPException
from typing import List

from app.services.client import ClientChannelService
from app.schemas.client import ClientChannelCreateorUpdateRequest, ClientChannelResponse, ClientChannelUpdateRequest
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/clients/{client_id}/channels", tags=["Client Channels"])


@router.post("", response_model=ClientChannelResponse)
def create_channel(client_id: str, request: ClientChannelCreateorUpdateRequest):
    try:
        return ClientChannelService.create_channel(client_id=client_id, request=request)
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Error creating channel: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ClientChannelResponse])
def list_channels(client_id: str):
    try:
        return ClientChannelService.list_channels(client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{client_channel_id}", response_model=dict)
def update_channel(client_id: str, client_channel_id: str, request: ClientChannelUpdateRequest):
    try:
        return ClientChannelService.update_channel(client_id, client_channel_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
