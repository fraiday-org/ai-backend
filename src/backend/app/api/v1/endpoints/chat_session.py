import mongoengine as me
from fastapi import HTTPException, Depends, APIRouter, Query
from typing import Optional, Annotated
from datetime import datetime
from bson import ObjectId

from app.models.mongodb.chat_session import ChatSession
from app.models.mongodb.chat_message import ChatMessage
from app.models.mongodb.events.event import Event
from app.schemas.chat_session import ChatSessionResponse, ChatSessionListResponse
from app.api.v1.deps import verify_api_key
from app.utils.logger import get_logger

router = APIRouter(prefix="", tags=["Chat Sessions"])
logger = get_logger(__name__)


@router.post("/sessions", response_model=dict)
async def create_chat_session():
    session = ChatSession()
    session.save()
    return {"session_id": str(session.id)}


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    try:
        session = ChatSession.objects.get(id=session_id)
        return {
            "id": str(session.id),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "active": session.active,
        }
    except me.DoesNotExist:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions(
    client_id: Annotated[Optional[str], Query(description="Filter by client ID")] = None,
    client_channel: Annotated[Optional[str], Query(description="Filter by client channel")] = None,
    user_id: Annotated[Optional[str], Query(description="Filter by user ID (sender)")] = None,
    session_id: Annotated[Optional[str], Query(description="Filter by session ID (supports partial matching)")] = None,
    active: Annotated[Optional[bool], Query(description="Filter by active status")] = None,
    handover: Annotated[
        Optional[bool], Query(description="Filter sessions that were handed over to human agents")
    ] = None,
    start_date: Annotated[Optional[datetime], Query(description="Filter sessions created after this date")] = None,
    end_date: Annotated[Optional[datetime], Query(description="Filter sessions created before this date")] = None,
    skip: Annotated[int, Query(description="Number of records to skip", ge=0)] = 0,
    limit: Annotated[int, Query(description="Maximum number of records to return", ge=1, le=100)] = 10,
    api_key: str = Depends(verify_api_key),
):
    """
    List chat sessions with optional filtering by client_id, client_channel, user_id, active status,
    human handover status, and date range (start_date and end_date).
    """
    try:
        # Validate date range if both dates provided
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=400, detail="Invalid date range: end_date cannot be earlier than start_date"
            )

        # Build filter query for ChatSession.objects
        query = {}
        
        # Standard filters
        if client_id:
            query["client"] = ObjectId(client_id)
        if client_channel:
            query["client_channel"] = ObjectId(client_channel)
        if active is not None:
            query["active"] = active
        if start_date:
            query["updated_at__gte"] = start_date
        if end_date:
            query["updated_at__lte"] = end_date
        
        # Filter by handover status directly using the new has_handover field
        if handover is not None:
            query["has_handover"] = handover
        
        # Session ID filtering with partial matching
        if session_id:
            # Directly use regex for session_id field
            query["session_id__iregex"] = session_id
        
        # User ID filter requires a lookup to messages collection
        if user_id:
            # Get session IDs with messages from this user
            unique_sessions = ChatMessage.objects.filter(sender=user_id).distinct("session")
            if not unique_sessions:
                return ChatSessionListResponse(sessions=[], total=0)
            
            query["id__in"] = [session.id for session in unique_sessions]
        
        # Get total count
        total = ChatSession.objects.filter(**query).count()
        
        # Get paginated sessions
        sessions = ChatSession.objects.filter(**query).order_by("-updated_at").skip(skip).limit(limit)
        
        # Format the response
        session_list = []
        for session in sessions:
            session_list.append(
                ChatSessionResponse(
                    id=str(session.id),
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    session_id=str(session.session_id) if session.session_id else "",
                    active=session.active,
                    client=str(session.client.id) if session.client else None,
                    client_channel=str(session.client_channel.id) if session.client_channel else None,
                    participants=session.participants,
                    handover=session.has_handover
                )
            )

        return ChatSessionListResponse(sessions=session_list, total=total)
    except HTTPException:
        # Re-raise HTTP exceptions to preserve their status codes and messages
        raise
    except Exception as e:
        # Catch all other exceptions and convert them to 500 errors
        raise HTTPException(status_code=500, detail=f"Error listing chat sessions: {str(e)}")
