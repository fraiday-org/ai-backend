from pydantic import BaseModel
from typing import Optional, Dict, Union

from app.models.mongodb.client_channel import ChannelType


class WebhookChannelConfig(BaseModel):
    webhook_url: str
    headers: Optional[Dict] = None


class SlackWebhookConfig(BaseModel):
    webhook_url: str
    headers: Optional[Dict] = None


class ClientChannelCreateorUpdateRequest(BaseModel):
    channel_id: Optional[str] = None
    channel_type: ChannelType
    channel_config: Union[WebhookChannelConfig, SlackWebhookConfig]
    is_active: Optional[bool] = True


class ClientChannelUpdateRequest(BaseModel):
    channel_id: Optional[str] = None
    channel_type: Optional[ChannelType] = None
    channel_config: Optional[Union[WebhookChannelConfig, SlackWebhookConfig]] = None
    is_active: Optional[bool] = None


class ClientChannelResponse(BaseModel):
    id: str
    channel_id: Optional[str] = None
    channel_type: ChannelType
    channel_config: Union[WebhookChannelConfig, SlackWebhookConfig]
    is_active: bool

    class Config:
        populate_by_name = True
