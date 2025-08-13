import requests
import traceback
import logging
import json
from typing import Dict, Any

from app.core.config import settings
from app.schemas.ai_response import AIResponse, AIServiceRequest, Data, Answer, Metadata
from app.schemas.chat import AttachmentCreate
from app.models.mongodb.client_channel import ChannelType, ClientChannel
from app.utils.logger import get_logger
from app.exceptions import AIProcessingException

logger = get_logger(__name__)


class AIService:

    def get_response(self, message_id: str) -> AIResponse:
        try:
            chat_message = self._get_chat_message(message_id=message_id)
            client_channel: ClientChannel = chat_message.session.client_channel

            if client_channel.channel_type in [ChannelType.SLACK.value, ChannelType.SUNSHINE.value]:
                response = requests.post(
                    settings.SLACK_AI_SERVICE_URL,
                    json={
                        "id": settings.SLACK_AI_SERVICE_WORKFLOW_ID,
                        "input_args": {
                            "client_id": chat_message.session.client.client_id,
                            "user_id": str(chat_message.sender),
                            "human_msg": chat_message.text,
                            "session_id": str(chat_message.session.session_id),
                            "metadata": json.dumps(chat_message.data)
                        },
                    },
                    headers={"Authorization": f"Basic {settings.SLACK_AI_TOKEN}"},
                )
                ai_response = response.json()

                # Extract metadata if present in the response
                metadata_dict = {}
                if "metadata" in ai_response["result"]:
                    metadata_dict = ai_response["result"]["metadata"]
                
                return AIResponse(
                    status=ai_response["status"],
                    message="",
                    data=Data(
                        answer=Answer(
                            answer_data=ai_response["result"].get("data", {}),
                            answer_url="www.example.com",
                            answer_text=ai_response["result"]["text"],
                            attachments=[
                                self._parse_attachment(a) for a in ai_response["result"].get("attachments", [])
                            ],
                        ),
                        confidence_score=ai_response["result"].get("confidence_score", 0.9),
                    ),
                    metadata=Metadata(
                        close_session=metadata_dict.get("close_session", False)
                    ),
                )
            else:
                response = requests.post(
                    settings.AI_SERVICE_URL,
                    json=json.loads(
                        self.prepare_payload(message_id).model_dump_json()
                    ),  # Prevent double jsonification of the payload
                )
                ai_response = response.json()
                logger.info(f"AI Response: {ai_response}")
                return AIResponse(**ai_response)
        except Exception as e:
            logging.error(f"Error in ai service: {str(e)}")
            logging.error(traceback.format_exc())
            raise Exception("Error in AI Service")

    def _get_chat_message(self, message_id: str):
        from app.services.chat.message import ChatMessageService

        chat_message = ChatMessageService.get_message(message_id=message_id)
        return chat_message

    def _parse_attachment(self, attachment: Dict[str, Any]) -> AttachmentCreate:
        """Parse different types of attachments from AI response."""
        attachment_type = attachment.get("type", "file")

        # For backwards compatibility, default to file type if no type specified
        result = {
            "file_name": attachment.get("file_name", ""),
            "file_url": attachment.get("file_url", ""),
            "file_type": attachment.get("file_type", ""),
            "type": attachment_type,
        }

        # Add carousel data if present
        if attachment_type == "carousel" and "carousel" in attachment:
            result["carousel"] = attachment["carousel"]
        
        if attachment_type == "buttons" and "buttons" in attachment:
            result["buttons"] = attachment["buttons"]

        return AttachmentCreate(**result)

    def prepare_payload(self, message_id: str):
        from app.services.chat.message import ChatMessageService

        try:
            chat_message = ChatMessageService.get_message(message_id=message_id)
            chat_message_history = ChatMessageService.list_messages(
                last_n=100,
                exclude_id=[message_id],
                session_id=chat_message.session.session_id,
            )[::-1]
            return AIServiceRequest(
                current_message=chat_message.text,
                chat_history=chat_message_history,
                session_id=chat_message.session.session_id,
                sender_id=chat_message.sender,
                sender_type=chat_message.sender_type,
                created_at=chat_message.created_at,
                updated_at=chat_message.updated_at,
                current_message_id=str(chat_message.id),
            )
        except Exception as e:
            logger.error(f"Error creating AI Service Request: {str(e)}", exc_info=True)
            raise AIProcessingException(f"Error creating AI Service Request: {str(e)}")
