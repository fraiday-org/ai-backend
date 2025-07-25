from mongoengine import fields
from enum import Enum

from app.models.mongodb.base import BaseDocument
from app.models.schemas.processor_config import HttpWebhookConfig, AmqpConfig
from .event_types import EventType, EntityType


class ProcessorType(str, Enum):
    HTTP_WEBHOOK = "http_webhook"
    AMQP = "amqp"


class EventProcessorConfig(BaseDocument):
    """
    Configuration for downstream event processors.
    Defines which events get processed by which downstream systems for specific clients.
    """

    name = fields.StringField(required=True)
    description = fields.StringField()
    client = fields.ReferenceField("Client", required=True)
    client_channel = fields.ReferenceField("ClientChannel", required=False)
    processor_type = fields.StringField(choices=[t.value for t in ProcessorType], required=True)

    # Processor-specific configuration
    config = fields.DictField(required=True)

    # Which events this processor handles
    event_types = fields.ListField(fields.StringField(choices=[e.value for e in EventType]), default=list)
    entity_types = fields.ListField(fields.StringField(choices=[e.value for e in EntityType]), default=list)

    is_active = fields.BooleanField(default=True)

    meta = {
        "collection": "event_processor_configs",
        "indexes": [
            "client",
            "client_channel",
            "processor_type",
            "is_active",
            ("client", "is_active"),
            # Add unique constraint for client, client_channel, is_active combination
            {
                "fields": ("client", "client_channel", "is_active"),
                "unique": True,
                # Only apply uniqueness when is_active is True to allow multiple inactive processors
                "sparse": False
            },
            ("event_types", "is_active"),
            ("entity_types", "is_active"),
        ],
    }

    def validate_config(self):
        """
        Validate the config against the appropriate schema based on processor_type.
        """
        try:
            if self.processor_type == ProcessorType.HTTP_WEBHOOK:
                HttpWebhookConfig(**self.config)
            elif self.processor_type == ProcessorType.AMQP:
                AmqpConfig(**self.config)
            else:
                raise ValueError(f"Unsupported processor type: {self.processor_type}")
        except Exception as e:
            from app.utils.logger import get_logger

            logger = get_logger(__name__)
            logger.error(f"Invalid processor config: {e}", exc_info=True)
            raise ValueError(f"Invalid processor config: {str(e)}")

    def clean(self):
        """
        Validate the processor config before saving.
        """
        super().clean()
        self.validate_config()
