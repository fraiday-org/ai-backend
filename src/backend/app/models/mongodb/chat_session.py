from mongoengine import fields
from .base import BaseDocument


class ChatSession(BaseDocument):
    session_id = fields.StringField(required=False)
    client = fields.ReferenceField("Client")
    client_channel = fields.ReferenceField("ClientChannel")
    active = fields.BooleanField(default=True)
    participants = fields.ListField(fields.StringField(), default=list)
    has_handover = fields.BooleanField(default=False)


    meta = {"collection": "chat_sessions", "indexes": ["created_at", "updated_at", "client", "client_channel"]}
