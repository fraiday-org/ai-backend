from mongoengine import fields
from enum import Enum

from .base import BaseDocument


class ChannelType(Enum):
    WEBHOOK = "webhook"
    SLACK = "slack"
    SUNSHINE = "sunshine"


class ClientChannel(BaseDocument):
    channel_id = fields.StringField(required=False)
    channel_type = fields.StringField(choices=[channel_type.value for channel_type in ChannelType], required=True)
    channel_config = fields.DictField(required=True)
    client = fields.ReferenceField("Client", required=True)
    is_active = fields.BooleanField(default=True)

    meta = {
        "collection": "client_channels", 
        "indexes": [
            "created_at", 
            "client",
            "channel_id",
            
            # This compound index ensures that:
            # 1. Each (client, channel_type) combination is unique when channel_id is null
            # 2. Each (client, channel_type, channel_id) combination is unique when channel_id is provided
            {
                "fields": ("client", "channel_type", "channel_id"),
                "unique": True,
                "sparse": False  # Don't make it sparse so it applies to all documents
            }
        ]
    }
