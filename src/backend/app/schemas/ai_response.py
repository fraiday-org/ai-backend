from pydantic import BaseModel, Field
from datetime import datetime
from app.models.mongodb.chat_message import SenderType

from typing import List, Union, Dict, Optional
from .chat import ChatMessageResponse, AttachmentCreate


class Answer(BaseModel):
    answer_text: str
    answer_data: Union[List[Dict], Dict]
    answer_url: str
    attachments: Optional[List[AttachmentCreate]] = Field(default_factory=list)


class Data(BaseModel):
    answer: Answer
    confidence_score: Optional[float] = Field(default=0.9)


class Metadata(BaseModel):
    close_session: Optional[bool] = False


class AIResponse(BaseModel):
    status: str
    message: str
    data: Data
    metadata: Optional[Metadata] = Field(default_factory=Metadata)


class AIServiceRequest(BaseModel):
    current_message: str
    chat_history: List[ChatMessageResponse] = Field(default_factory=list)
    session_id: str
    sender_id: str
    created_at: datetime
    updated_at: datetime
    sender_type: SenderType
    current_message_id: str
