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
        processor = AIService()
        processed_message = processor.get_response(message_id=message_id)

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
                # Set has_handover flag on the chat session
                message.session.has_handover = True
                message.session.save()
                
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


@shared_task(bind=True, max_retries=3)
def send_to_webhook_task(self, message_data: dict):
    try:
        logger.info(f"Session data: {message_data}")

        entity_id = message_data["entity_id"]
        entity_type = message_data["entity_type"]

        strategies = {
            EntityType.CHAT_MESSAGE: MessagePayloadStrategy(),
            EntityType.CHAT_SUGGESTION: SuggestionPayloadStrategy(),
        }
        strategy = strategies[entity_type]

        # Get message based on strategy type
        entity = strategy.get_entity(entity_id=entity_id)
        session = strategy.get_session(entity=entity)

        # Get or create the ChannelRequestLog
        request_log, created = ChannelRequestLogService.get_or_create(
            entity=entity,
            channel=session.client_channel,
        )
        webhook_url = ClientChannelService.get_channel_webhook_url(
            client_id=session.client.id,
            channel_id=session.client_channel.id,
        )

        payload = strategy.create_payload(entity=entity)
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()

        response_data = response.json()
        strategy.handle_response(entity=entity, response_data=response_data)

        # Log the successful attempt
        ChannelRequestLogService.log_attempt(
            request_log=request_log,
            attempt_number=self.request.retries + 1,
            success=True,
            response_status=response.status_code,
            response_body=response.json(),
        )

    except RequestException as exc:
        logger.error(f"Webhook notification failed: {exc}")

        # Log the failed attempt
        request_log = ChannelRequestLog.objects.get(
            entity_id=entity_id, entity_type=entity_type
        )  # Ensure we fetch the log
        ChannelRequestLogService.log_attempt(
            request_log=request_log,
            attempt_number=self.request.retries + 1,
            success=False,
            error_message=str(exc),
        )
        raise self.retry(exc=exc, countdown=60)  # Retry after 60 seconds

    except Exception as exc:
        # For internal errors, just log and fail gracefully
        logger.error(
            "Critical internal error in webhook task",
            extra={"entity_id": entity_id, "entity_type": entity_type, "error": str(exc)},
            exc_info=True,
        )
        raise


def trigger_chat_workflow(message_id: str, session_id: str):
    """
    Starts the message processing chain.
    """
    process_chain = chain(
        generate_ai_response_task.s(session_data={"message_id": message_id, "session_id": session_id}),
    )
    process_chain.apply_async()


def trigger_suggestion_workflow(message_id: str, session_id: str):
    """
    Starts the message processing chain.
    """
    process_chain = chain(
        generate_ai_response_task.s(session_data={"message_id": message_id, "session_id": session_id}),
    )
    process_chain.apply_async()
