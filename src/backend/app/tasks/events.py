import traceback
from typing import Dict, Any, Optional
from celery import shared_task
from celery.exceptions import Retry
from celery import Task

from app.models.mongodb.events.event_types import EventType, EntityType
from app.models.mongodb.events.event_delivery_attempt import AttemptStatus
from app.services.events.event_delivery_tracking import EventDeliveryTrackingService
from app.services.events.event import EventService
from app.services.events.event_processor_dispatch import ProcessorDispatchService
from app.services.events.event_processor_config import ProcessorConfigService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_entity_client_info(entity_type: str, entity_id: str) -> tuple[Optional[str], Optional[str]]:
    """
    Helper function to determine client_id and client_channel_id for different entity types.
    
    Returns:
        Tuple of (client_id, client_channel_id)
    """
    from app.models.mongodb.chat_message import ChatMessage
    from app.models.mongodb.chat_session import ChatSession
    from app.models.mongodb.chat_message_suggestion import ChatMessageSuggestion
    try:
        if entity_type == EntityType.CHAT_MESSAGE:
            message = ChatMessage.objects.get(id=entity_id)
            client_id = str(message.session.client.id)
            client_channel_id = str(message.session.client_channel.id) if message.session.client_channel else None
            return client_id, client_channel_id

        elif entity_type == EntityType.CHAT_SESSION:
            session = ChatSession.objects.get(id=entity_id)
            client_id = str(session.client.id)
            client_channel_id = str(session.client_channel.id) if session.client_channel else None
            return client_id, client_channel_id
        
        elif entity_type == EntityType.CHAT_SUGGESTION:
            suggestion = ChatMessageSuggestion.objects.get(id=entity_id)
            client_id = str(suggestion.chat_session.client.id)
            client_channel_id = str(suggestion.chat_session.client_channel.id) if suggestion.chat_session.client_channel else None
            return client_id, client_channel_id

        elif entity_type == EntityType.AI_SERVICE:
            # For AI service events, we need to find the related chat message
            # This assumes parent_id points to a chat message
            events = EventService.get_entity_events(entity_type=EntityType.AI_SERVICE, entity_id=entity_id)
            if events and events[0].parent_id:
                return _get_entity_client_info(entity_type=EntityType.CHAT_MESSAGE, entity_id=events[0].parent_id)

        logger.error(f"Could not determine client info for {entity_type}:{entity_id}")
        return None, None

    except Exception as e:
        logger.error(f"Error determining client info for {entity_type}:{entity_id}", exc_info=True)
        return None, None


@shared_task(bind=True, queue="events")
def process_event(
    self,
    event_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    parent_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Process an event asynchronously.
    """
    try:
        # Get the original event to find the client_id
        event = EventService.get_event_by_id(event_id)
        if not event:
            logger.error(f"Event {event_id} not found")
            return {"status": "error", "message": "Event not found"}

        # Get client_id and client_channel_id from the entity
        client_id, client_channel_id = _get_entity_client_info(entity_type, entity_id)
        if not client_id:
            logger.error(f"Could not determine client_id for {entity_type}:{entity_id}")
            return {"status": "error", "message": "Client ID not found"}

        # Find matching processors for this event, including client channel routing if available
        processors = ProcessorConfigService.get_matching_processors(
            client_id=client_id, 
            event_type=event_type, 
            entity_type=entity_type,
            client_channel_id=client_channel_id
        )

        if not processors:
            logger.info(f"No matching processors found for {event_type} event for client {client_id}")
            return {"status": "skipped", "reason": "No matching processors"}

        # Prepare event data for dispatching
        dispatch_data = {
            "event_id": event_id,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "parent_id": parent_id,
            "data": data or {},
            "timestamp": event.created_at.isoformat(),
            "client_id": client_id,
        }

        # For each processor, create a delivery record and dispatch in a separate task
        delivery_results = []
        for processor in processors:
            # Create delivery record
            delivery = EventDeliveryTrackingService.create_delivery_record(
                event_id=event_id, processor_id=str(processor.id), request_payload=dispatch_data
            )

            # Dispatch to processor in a separate task with retry capability
            deliver_to_processor.delay(
                processor_id=str(processor.id), event_data=dispatch_data, delivery_id=str(delivery.id)
            )

            delivery_results.append(
                {
                    "processor_id": str(processor.id),
                    "processor_name": processor.name,
                    "delivery_id": str(delivery.id),
                    "status": "dispatched",
                }
            )

        logger.info(f"Dispatched event {event_id} to {len(processors)} processors")
        return {
            "status": "dispatched",
            "event_id": event_id,
            "client_id": client_id,
            "delivery_results": delivery_results,
        }

    except Exception as e:
        logger.error(f"Error processing event {event_id}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, queue="events")
def deliver_to_processor(self, processor_id: str, event_data: Dict[str, Any], delivery_id: str) -> Dict[str, Any]:
    """
    Deliver an event to a specific processor with retries.
    """
    try:
        # Get the processor
        processor = ProcessorConfigService.get_processor_by_id(processor_id)
        if not processor:
            logger.error(f"Processor {processor_id} not found")

            # Record failure
            EventDeliveryTrackingService.record_attempt(
                delivery_id=delivery_id,
                status=AttemptStatus.FAILURE,
                logs={"error": f"Processor {processor_id} not found"},
            )

            return {"status": "error", "message": "Processor not found"}

        # Try to dispatch
        result = ProcessorDispatchService.dispatch_to_processor(processor, event_data)
        success, response_status, response_body, error_message = result

        # Record the attempt
        attempt = EventDeliveryTrackingService.record_attempt(
            delivery_id=delivery_id,
            status=AttemptStatus.SUCCESS if success else AttemptStatus.FAILURE,
            response_status=response_status,
            response_body=response_body,
            logs={"error": error_message},
        )

        # If failed and we have retries left, retry with exponential backoff
        if not success:
            if self.request.retries < self.max_retries:
                # Exponential backoff: 60s, 120s, 240s
                countdown = 60 * (2**self.request.retries)
                logger.info(
                    f"Retry {self.request.retries + 1}/{self.max_retries} for delivery {delivery_id} in {countdown}s"
                )
                raise self.retry(countdown=countdown, exc=Exception(error_message))
            else:
                logger.error(f"All retries failed for delivery {delivery_id}")

        return {
            "status": "success" if success else "failed",
            "delivery_id": delivery_id,
            "attempt": attempt.attempt_number,
        }

    except Retry:
        # This is a retry exception, let it propagate, The code will reach here if the dispatch fails.
        raise
    except Exception as e:
        logger.error(f"Error delivering to processor {processor_id}", exc_info=True)

        # Record failure unless it's already a retry
        if not isinstance(e, self.retry_error):
            EventDeliveryTrackingService.record_attempt(
                delivery_id=delivery_id, status=AttemptStatus.FAILURE, logs=str(e) + traceback.format_exc()
            )

        # Retry if we have attempts left
        if self.request.retries < self.max_retries:
            countdown = 60 * (2**self.request.retries)
            logger.info(
                f"Retry {self.request.retries + 1}/{self.max_retries} for delivery {delivery_id} in {countdown}s"
            )
            raise self.retry(countdown=countdown, exc=e)

        raise
