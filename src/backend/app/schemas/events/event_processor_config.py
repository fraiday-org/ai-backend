from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime

from app.models.mongodb.events.event_types import EventType, EntityType
from app.models.mongodb.events.event_processor_config import ProcessorType, EventProcessorConfig
from app.models.schemas.processor_config import HttpWebhookConfig, AmqpConfig


class ProcessorConfigCreate(BaseModel):
    """Schema for creating a new processor configuration"""

    name: str
    client_id: str
    processor_type: ProcessorType
    config: Union[HttpWebhookConfig, AmqpConfig, Dict[str, Any]]
    event_types: List[EventType]
    entity_types: List[EntityType]
    description: Optional[str] = Field(None)
    is_active: bool = Field(default=True)
    client_channel_id: Optional[str] = Field(None, description="Optional client channel ID to associate with this processor")


class ProcessorConfigUpdate(BaseModel):
    """Schema for updating an existing processor configuration"""

    name: Optional[str] = Field(None)
    config: Optional[Union[HttpWebhookConfig, AmqpConfig, Dict[str, Any]]] = Field(None)
    event_types: Optional[List[EventType]] = Field(None)
    entity_types: Optional[List[EntityType]] = Field(None)
    description: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    client_channel_id: Optional[str] = Field(None, description="Optional client channel ID to associate with this processor")


class ProcessorConfigResponse(BaseModel):
    """Schema for processor configuration response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client_id: str
    processor_type: str
    config: Dict[str, Any]  # We use Dict here to handle any processor type
    event_types: List[str]
    entity_types: List[str]
    description: Optional[str] = None
    is_active: bool
    client_channel_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db_model(cls, db_model: EventProcessorConfig) -> "ProcessorConfigResponse":
        """
        Convert a database model instance to a response schema.

        Args:
            db_model: An EventProcessorConfig instance from the database

        Returns:
            ProcessorConfigResponse: The formatted response object
        """
        return cls(
            id=str(db_model.id),
            name=db_model.name,
            client_id=str(db_model.client.client_id),
            processor_type=db_model.processor_type,
            config=db_model.config,
            event_types=db_model.event_types,
            entity_types=db_model.entity_types,
            description=db_model.description,
            is_active=db_model.is_active,
            client_channel_id=str(db_model.client_channel.id) if db_model.client_channel else None,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )
