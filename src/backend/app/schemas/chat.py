from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.mongodb.chat_message import MessageCategory, ChatMessage, SenderType
from app.models.mongodb.chat_message_suggestion import ChatMessageSuggestion


class MessageConfig(BaseModel):
    suggestion_mode: bool = Field(default=False, description="Whether to create suggestions instead of messages")
    ai_enabled: bool = Field(default=True, description="Whether to enable AI processing")


class CarouselItemButton(BaseModel):
    type: str  # "postback" or "link"
    text: str
    payload: Optional[Dict[str, Any]] = None  # For postback buttons
    url: Optional[str] = None  # For link buttons


class CarouselItem(BaseModel):
    title: str
    description: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    default_action_url: Optional[str] = None
    buttons: Optional[List[CarouselItemButton]] = None


class Carousel(BaseModel):
    items: List[CarouselItem]


class AttachmentCreate(BaseModel):
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    type: str = "image"
    carousel: Optional[Dict[str, Any]] = None


class BaseChatMessageCreate(BaseModel):
    sender: Optional[str] = None
    sender_name: Optional[str] = None
    sender_type: Optional[Union[SenderType, str]] = Field(default=SenderType.USER)
    created_at: Optional[str] = None
    text: str
    attachments: Optional[List[AttachmentCreate]] = None
    data: Optional[dict] = None
    category: MessageCategory = MessageCategory.MESSAGE

    @field_validator("sender_type")
    def validate_sender_type(cls, v):
        if isinstance(v, SenderType):
            return v
        if isinstance(v, str):
            # Check if it's a default type
            try:
                return SenderType(v)
            except ValueError:
                # Check if it's a custom client type
                if v.startswith("client:"):
                    return v
                raise ValueError(f"Invalid sender_type: {v}. Custom types must start with 'client:'")
        raise ValueError(f"Invalid sender_type: {v}")


class ChatMessageCreate(BaseChatMessageCreate):
    client_id: str = None
    client_channel_type: str = None
    client_channel_id: Optional[str] = None
    session_id: str = None
    config: Optional[MessageConfig] = Field(default_factory=MessageConfig)
    external_id: Optional[str] = None


class BulkChatMessageCreate(BaseModel):
    messages: List[BaseChatMessageCreate]
    session_id: str
    client_id: str = None
    client_channel_type: str = None
    client_channel_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.replace(tzinfo=timezone.utc).isoformat()})
    
    id: str
    created_at: datetime = Field(description="UTC timestamp with timezone info")
    updated_at: datetime = Field(description="UTC timestamp with timezone info")
    sender_id: Optional[str]
    sender_name: Optional[str]
    sender_type: Optional[str]
    session_id: str
    text: str
    data: Optional[dict] = Field(default_factory=dict)
    attachments: Optional[List[AttachmentCreate]]
    category: MessageCategory
    confidence_score: float
    external_id: Optional[str] = None
    edit: bool = False

    @classmethod
    def from_chat_message(cls, chat_message: ChatMessage):
        return cls(
            id=str(chat_message.id),
            created_at=chat_message.created_at,
            updated_at=chat_message.updated_at,
            sender_id=chat_message.sender,
            sender_name=chat_message.sender_name,
            session_id=str(chat_message.session.session_id),
            text=chat_message.text,
            data=chat_message.data,
            attachments=(
                [AttachmentCreate(**a.to_mongo().to_dict()) for a in chat_message.attachments]
                if chat_message.attachments
                else None
            ),
            category=MessageCategory(chat_message.category),
            sender_type=chat_message.sender_type,
            edit=chat_message.edit,
            confidence_score=chat_message.confidence_score,
            external_id=chat_message.external_id,
        )


class ChatMessageSuggestionResponse(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.replace(tzinfo=timezone.utc).isoformat()})
    
    id: str = Field(description="Suggestion ID")
    created_at: datetime = Field(description="UTC timestamp with timezone info")
    updated_at: datetime = Field(description="UTC timestamp with timezone info")
    chat_message: ChatMessageResponse
    session_id: str
    text: str
    data: Optional[dict] = Field(default_factory=dict)
    attachments: Optional[List[AttachmentCreate]]

    @classmethod
    def from_suggestion(cls, suggestion: "ChatMessageSuggestion") -> "ChatMessageSuggestionResponse":
        """Creates a response model from a ChatMessageSuggestion instance"""
        return cls(
            id=str(suggestion.id),
            created_at=suggestion.created_at,
            updated_at=suggestion.updated_at,
            chat_message=ChatMessageResponse.from_chat_message(suggestion.chat_message),
            session_id=str(suggestion.chat_session.session_id),
            text=suggestion.text,
            attachments=(
                [AttachmentCreate(**a.to_mongo().to_dict()) for a in suggestion.attachments]
                if suggestion.attachments
                else None
            ),
            data=suggestion.data,
        )
