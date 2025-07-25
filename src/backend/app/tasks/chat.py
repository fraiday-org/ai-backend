import requests
from requests.exceptions import RequestException
import traceback

from celery import shared_task, chain
from celery.utils.log import get_task_logger

import app.constants as constants
from app.db.mongodb_utils import connect_to_db
from app.models.mongodb.chat_message import ChatMessage, SenderType, MessageCategory
from app.schemas.chat import ChatMessageCreate
from app.models.mongodb.chat_session import ChatSession
from app.models.mongodb.chat_message_suggestion import ChatMessageSuggestion
from app.models.mongodb.channel_request_log import EntityType, ChannelRequestLog
from app.services.ai_service import AIService
from app.services.chat.utils import create_system_chat_message
from app.services.webhook.payload import PayloadService
from app.services.chat.message import ChatMessageService, get_session_id_filter
from app.services.client import ChannelRequestLogService, ClientChannelService
from app.services.webhook import MessagePayloadStrategy, SuggestionPayloadStrategy

logger = get_task_logger(__name__)

connect_to_db()

# Default error message if client has no custom message configured
DEFAULT_AI_SERVICE_ERROR_MESSAGE = """
🤖 We're sorry!
We couldn't generate a response to your message.
Please try rephrasing your message and try again.
"""


WEBHOOK_ERROR_MESSAGE = """
📡 Delivery Failed!
Your message was processed, but we couldn't respond.
We'll retry shortly, or you can contact support if this persists.
"""


@shared_task(bind=True)
def generate_ai_response_task(self, session_data: dict):
    from app.models.mongodb.events.event_types import EventType
    from app.services.events.event_publisher import EventPublisher

    try:
        message_id = session_data["message_id"]
        message: ChatMessage = ChatMessage.objects.get(id=message_id)

        # Publish processing event
        EventPublisher.publish(
            event_type=EventType.CHAT_WORKFLOW_PROCESSING,
            entity_type=EntityType.CHAT_MESSAGE,
            entity_id=message_id,
            parent_id=str(message.session.id),
            data={"status": "ai_processing_started", "session_id": str(message.session.session_id)},
        )

        # Process the AI request (existing code)
        workflow_id = session_data.get("workflow_id")
        processor = AIService()
        processed_message = processor.get_response(message_id=message_id, workflow_id=workflow_id)

        # Create appropriate response entity
        chat_message_config = message.get_message_config()

        if chat_message_config.suggestion_mode:
            suggestion = ChatMessageSuggestion(
                chat_session=message.session,
                chat_message=message,
                text=processed_message.data.answer.answer_text,
                data={"meta_data": processed_message.data.answer.answer_data},
            )
            suggestion.save()

            # Publish suggestion created event
            EventPublisher.publish(
                event_type=EventType.CHAT_SUGGESTION_CREATED,
                entity_type=EntityType.CHAT_SUGGESTION,
                entity_id=str(suggestion.id),
                parent_id=message_id,
                data=PayloadService.create_payload(
                    entity_id=str(suggestion.id), entity_type=EntityType.CHAT_SUGGESTION
                ),
            )

        else:
            confidence_score = processed_message.data.confidence_score
            ai_message = ChatMessageService.create_chat_message(
                message_data=ChatMessageCreate(
                    client_id=str(message.session.client.client_id),
                    client_channel_type=message.session.client_channel.channel_type,
                    session_id=message.session.session_id,
                    text=processed_message.data.answer.answer_text,
                    sender_name=constants.BOT_SENDER_NAME,
                    sender=constants.BOT_SENDER_NAME,
                    sender_type=SenderType.ASSISTANT,
                    confidence_score=confidence_score,
                    data={"meta_data": processed_message.data.answer.answer_data},
                    attachments=processed_message.data.answer.attachments,
                )
            )

            # Publish AI message created event
            EventPublisher.publish(
                event_type=EventType.CHAT_WORKFLOW_COMPLETED,
                entity_type=EntityType.CHAT_MESSAGE,
                entity_id=str(ai_message.id),
                parent_id=str(message.session.id),
                data={
                    "user_message": PayloadService.create_payload(
                        entity_id=message_id, entity_type=EntityType.CHAT_MESSAGE
                    ),
                    "ai_message": PayloadService.create_payload(
                        entity_id=str(ai_message.id), entity_type=EntityType.CHAT_MESSAGE
                    ),
                    "session_id": str(message.session.session_id),
                },
            )

            if confidence_score == 0:
                # Publish handover event manually
                EventPublisher.publish(
                    event_type=EventType.CHAT_WORKFLOW_HANDOVER,
                    entity_type=EntityType.CHAT_MESSAGE,
                    entity_id=str(ai_message.id),
                    parent_id=str(message.session.id),
                    data={
                        "user_message": PayloadService.create_payload(
                            entity_id=message_id, entity_type=EntityType.CHAT_MESSAGE
                        ),
                        "ai_message": PayloadService.create_payload(
                            entity_id=str(ai_message.id), entity_type=EntityType.CHAT_MESSAGE
                        ),
                        "session_id": str(message.session.session_id),
                    },
                )

        # No more send_to_webhook_task!
        return {"status": "success"}

    except Exception as exc:
        # Publish error event
        EventPublisher.publish(
            event_type=EventType.CHAT_WORKFLOW_ERROR,
            entity_type=EntityType.CHAT_MESSAGE,
            entity_id=message_id,
            parent_id=str(message.session.id) if message else None,
            data={
                "error": str(exc) + traceback.format_exc(),
                "session_id": str(message.session.session_id) if message else None,
            },
        )

        # Create system error message
        logger.info(f"Creating system error message on session data {session_data}")
        session_id_filter = get_session_id_filter(session_data["session_id"])
        session = ChatSession.objects(session_id_filter).first()
        
        # Get client's custom error message if available
        custom_error_message = DEFAULT_AI_SERVICE_ERROR_MESSAGE
        if session and session.client:
            try:
                client = session.client
                if client.chat_config and 'error_message' in client.chat_config:
                    custom_error_message = client.chat_config['error_message']
                else:
                    # If client has no chat_config or no error_message in it, use default
                    if not client.chat_config:
                        client.chat_config = {}
                    logger.info(f"Using default error message for client {client.client_id}")
            except Exception as e:
                logger.error(f"Error getting client error message: {e}")
        
        error_message = create_system_chat_message(
            session=session,
            error_message=custom_error_message,
            message_category=MessageCategory.ERROR,
        )

        # Publish error message created event
        EventPublisher.publish(
            event_type=EventType.CHAT_MESSAGE_CREATED,
            entity_type=EntityType.CHAT_MESSAGE,
            entity_id=str(error_message.id),
            parent_id=str(session.id),
            data=PayloadService.create_payload(entity_id=str(error_message.id), entity_type=EntityType.CHAT_MESSAGE),
        )

        raise exc


def trigger_chat_workflow(message_id: str, session_id: str):
    """
    Starts the message processing chain with configurable workflow ID.
    """
    from app.services.workflow_config import WorkflowConfigService
    from app.core.config import settings
    from app.models.mongodb.chat_message import ChatMessage
    
    # Get workflow ID based on client and channel
    workflow_id = settings.SLACK_AI_SERVICE_WORKFLOW_ID
    
    # Use configurable workflow if feature flag is enabled
    if settings.ENABLE_CONFIGURABLE_WORKFLOWS:
        try:
            # Get message to determine client and channel
            message = ChatMessage.objects.get(id=message_id)
            client_id = str(message.session.client.id)
            client_channel_id = str(message.session.client_channel.id) if message.session.client_channel else None
            
            # Get workflow ID from configuration with fallback to env var
            workflow_id = WorkflowConfigService.get_workflow_id(
                client_id=client_id,
                client_channel_id=client_channel_id,
            )
            logger.info(f"Using workflow ID {workflow_id} for chat message {message_id}")
        except Exception as e:
            logger.error(f"Error getting workflow ID for chat message {message_id}: {e}", exc_info=True)
            # Fall back to default workflow ID
            workflow_id = settings.SLACK_AI_SERVICE_WORKFLOW_ID
    
    # Use the workflow ID in the task
    process_chain = chain(
        generate_ai_response_task.s(
            session_data={
                "message_id": message_id, 
                "session_id": session_id,
                "workflow_id": workflow_id
            }
        ),
    )
    process_chain.apply_async()


def trigger_suggestion_workflow(message_id: str, session_id: str):
    """
    Starts the message processing chain with configurable workflow ID.
    """
    from app.services.workflow_config import WorkflowConfigService
    from app.core.config import settings
    from app.models.mongodb.chat_message import ChatMessage
    
    # Get workflow ID based on client and channel
    workflow_id = settings.SLACK_AI_SERVICE_WORKFLOW_ID
    
    # Use configurable workflow if feature flag is enabled
    if settings.ENABLE_CONFIGURABLE_WORKFLOWS:
        try:
            # Get message to determine client and channel
            message = ChatMessage.objects.get(id=message_id)
            client_id = str(message.session.client.id)
            client_channel_id = str(message.session.client_channel.id) if message.session.client_channel else None
            
            # Get workflow ID from configuration with fallback to env var
            workflow_id = WorkflowConfigService.get_workflow_id(
                client_id=client_id,
                client_channel_id=client_channel_id,
            )
            logger.info(f"Using workflow ID {workflow_id} for suggestion message {message_id}")
        except Exception as e:
            logger.error(f"Error getting workflow ID for suggestion message {message_id}: {e}", exc_info=True)
            # Fall back to default workflow ID
            workflow_id = settings.SLACK_AI_SERVICE_WORKFLOW_ID
    
    # Use the workflow ID in the task
    process_chain = chain(
        generate_ai_response_task.s(
            session_data={
                "message_id": message_id, 
                "session_id": session_id,
                "workflow_id": workflow_id
            }
        ),
    )
    process_chain.apply_async()
