from mongoengine import fields

from app.models.mongodb.base import BaseDocument


class WorkflowConfig(BaseDocument):
    """
    Configuration for workflow routing based on client and client channel.
    Defines which workflow ID to use for specific clients and channels.
    The body field contains additional input arguments that will be merged with
    the default input_args in the request payload to the AI orchestrator.
    """

    name = fields.StringField(required=True)
    description = fields.StringField()
    client = fields.ReferenceField("Client", required=True)
    client_channel = fields.ReferenceField("ClientChannel", required=False)
    workflow_id = fields.StringField(required=True)
    is_active = fields.BooleanField(default=True)
    body = fields.DictField(default=dict)

    meta = {
        "collection": "workflow_configs",
        "indexes": [
            "client",
            "client_channel",
            "is_active",
            {
                "fields": ("client", "client_channel", "is_active"),
                "unique": True,
                # Only apply uniqueness when is_active is True to allow multiple inactive processors
                "sparse": False
            },
        ],
    }
