from bson import ObjectId
from typing import List, Optional, Dict, Union
from datetime import datetime, timezone

import mongoengine as me
from mongoengine import Q
from fastapi import HTTPException

from app.models.mongodb.chat_message import ChatMessage, Attachment, SenderType
from app.models.mongodb.chat_session import ChatSession
from app.models.mongodb.utils import datetime_utc_now
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, BulkChatMessageCreate
from app.services.client.client import ClientService
from app.services.client.client_channel import ClientChannelService
from app.services.client.user_type import ClientUserTypeService
from app.services.chat.thread_manager import ThreadManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_id_filter(message_id: str) -> Dict:

    if ObjectId.is_valid(message_id):
        return {"id": message_id}
    else:
        return {"external_id": message_id}


def get_session_id_filter(session_id: str) -> Dict:
    query = Q(session_id=session_id)
    if ObjectId.is_valid(session_id):
        query = query | Q(id=session_id)
    return query


class ChatMessageService:
    @staticmethod
    def create_chat_message(message_data: ChatMessageCreate) -> ChatMessageResponse:
        from app.services.events.event_publisher import EventPublisher
        from app.models.mongodb.events.event_types import EventType
        from app.models.mongodb.channel_request_log import EntityType

        client = ClientService.get_client(message_data.client_id)
        
        # Use channel_id if available, otherwise fall back to channel_type
        channel_id = getattr(message_data, 'client_channel_id', None)
        client_channel = ClientChannelService.get_channel_by_type(
            client_id=message_data.client_id, 
            channel_type=message_data.client_channel_type,
            channel_id=channel_id
        )

        base_session_id = message_data.session_id

        # Check if threading is enabled for this client
        threading_enabled, _ = ThreadManager.is_threading_enabled_for_client(client)

        if threading_enabled:
            # Only use thread management when threading is explicitly enabled
            logger.info(f"Using thread management for message in session {base_session_id}")
            base_session_id = ThreadManager.parse_session_id(message_data.session_id)[0]

            session = ThreadManager.get_or_create_active_thread(
                session_id=base_session_id, client=client, client_channel=client_channel
            )
            logger.info(f"Message assigned to thread session: {session.session_id}")
        else:
            # For clients without threading - use traditional session handling
            logger.info(f"Using standard session handling for message in session {base_session_id}")
            try:
                # Try to find existing session with this ID
                session = ChatSession.objects.get(session_id=base_session_id)
                logger.info(f"Using existing session {base_session_id}")
            except me.DoesNotExist:
                # Create new standard session if not found
                logger.info(f"Creating new standard session {base_session_id}")
                session = ChatSession(session_id=base_session_id, client=client, client_channel=client_channel)
                session.save()

        # Process attachments if any
        attachments = (
            [Attachment(**attach.model_dump()) for attach in message_data.attachments]
            if message_data.attachments
            else []
        )

        # Validate sender_type if it's a custom client type
        sender_type = message_data.sender_type
        if isinstance(sender_type, str) and sender_type.startswith("client:"):
            # Extract client_id and type_id from the sender_type
            client_type_info = ClientUserTypeService.parse_sender_type(sender_type)
            if client_type_info is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid custom sender type format: {sender_type}. Expected format: client:<client_id>:<type_id>",
                )

            # Verify that this client user type exists and is active
            client_id, type_id = client_type_info
            user_type = ClientUserTypeService.get_user_type(client_id, type_id)
            if not user_type or not user_type.is_active:
                raise HTTPException(
                    status_code=400, detail=f"Invalid or inactive client user type: {type_id} for client {client_id}"
                )
            # Update sender_type to the actual user type
            sender_type = f"client:{client_id}:{type_id}"

        # Create the chat message
        chat_message = ChatMessage(
            session=session,
            text=message_data.text,
            sender=message_data.sender,
            sender_name=message_data.sender_name,
            sender_type=sender_type,
            attachments=attachments,
            category=message_data.category.value,
            external_id=message_data.external_id,
            data=message_data.data,
            config=message_data.config if isinstance(message_data.config, dict) else message_data.config.model_dump(),
        )
        chat_message.save()

        session.updated_at = datetime_utc_now()
        session.save()

        response = ChatMessageResponse.from_chat_message(chat_message)
        EventPublisher.publish(
            event_type=EventType.CHAT_MESSAGE_CREATED,
            entity_type=EntityType.CHAT_MESSAGE,
            entity_id=str(chat_message.id),
            parent_id=message_data.session_id,
            data=response.model_dump(mode="json"),
        )

        return response

    @staticmethod
    def list_messages(
        id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        last_n: Optional[int] = None,
        sender_type: Optional[Union[SenderType, str]] = None,
        exclude_id: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ChatMessageResponse]:
        query = {}
        if id:
            query.update(get_id_filter(id))
        if session_id:
            try:
                chat_session = ChatSession.objects.get(session_id=session_id)
            except me.DoesNotExist:
                raise HTTPException(status_code=404, detail="Chat Session not found")
            query["session"] = chat_session.id
        if user_id:
            query["sender"] = user_id
        if sender_type:
            # Handle both enum and string sender types
            if isinstance(sender_type, SenderType):
                query["sender_type"] = sender_type.value
            else:
                query["sender_type"] = sender_type
        if exclude_id:
            query["id__nin"] = exclude_id
        if start_date:
            query["created_at__gte"] = start_date
        if end_date:
            query["created_at__lte"] = end_date

        messages = ChatMessage.objects(**query).order_by("-created_at")
        if last_n:
            messages = messages[: last_n + 1]

        return [ChatMessageResponse.from_chat_message(msg) for msg in messages]

    @staticmethod
    def get_message(message_id: str) -> ChatMessage:
        try:
            chat_message = ChatMessage.objects.get(**get_id_filter(message_id))
            return chat_message
        except me.DoesNotExist:
            raise HTTPException(status_code=404, detail="Message not found")

    @staticmethod
    def update_chat_message(message_id: str, message_data: ChatMessageCreate) -> ChatMessageResponse:
        try:
            chat_message = ChatMessage.objects.get(**get_id_filter(message_id))
        except me.DoesNotExist:
            raise HTTPException(status_code=404, detail="Message not found")

        chat_message.text = message_data.text
        chat_message.sender = message_data.sender
        chat_message.sender_name = message_data.sender_name
        chat_message.updated_at = datetime.now(timezone.utc)
        chat_message.edit = True

        if message_data.attachments:
            chat_message.attachments = [Attachment(**attach.dict()) for attach in message_data.attachments]

        if message_data.sql_data:
            chat_message.sql_data = message_data.sql_data

        chat_message.save()

        return ChatMessageResponse.from_chat_message(chat_message)

    @staticmethod
    def create_bulk_chat_messages(bulk_message_data: BulkChatMessageCreate) -> List[ChatMessageResponse]:
        responses = []
        session = None
        client = ClientService.get_client(bulk_message_data.client_id)
        
        # Use channel_id if available, otherwise fall back to channel_type
        channel_id = getattr(bulk_message_data, 'client_channel_id', None)
        client_channel = ClientChannelService.get_channel_by_type(
            client_id=bulk_message_data.client_id, 
            channel_type=bulk_message_data.client_channel_type,
            channel_id=channel_id
        )

        try:
            session = ChatSession.objects.get(
                session_id=bulk_message_data.session_id, client=client, client_channel=client_channel
            )
        except me.DoesNotExist:
            session = ChatSession(
                session_id=bulk_message_data.session_id,
                client=client,
                client_channel=client_channel,
            )
            session.save()

        for message_data in bulk_message_data.messages:
            attachments = (
                [Attachment(**attach.model_dump()) for attach in message_data.attachments]
                if message_data.attachments
                else []
            )

            chat_message = ChatMessage(
                session=session,
                text=message_data.text,
                sender=message_data.sender,
                sender_name=message_data.sender_name,
                attachments=attachments,
                category=message_data.category.value,
                created_at=message_data.created_at or datetime.now(timezone.utc),
            )
            chat_message.save()
            responses.append(chat_message)

        return [ChatMessageResponse.from_chat_message(msg) for msg in responses]
