from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.middleware.error_handler import NotFoundError
from app.repositories import chat_repo
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionSummary,
)
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    """Send a chat message and get an AI-powered response with query + visualization."""
    result = await chat_service.handle_message(
        session=session,
        owner_id=user_id,
        session_id=body.session_id,
        message=body.message,
    )
    return result


@router.get("/sessions", response_model=list[ChatSessionSummary])
async def list_sessions(user_id: str = Depends(get_current_user_id)):
    """List all chat sessions for the current user."""
    return await chat_repo.list_sessions(user_id)


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Retrieve full chat history for a session."""
    data = await chat_repo.get_session(session_id, user_id)
    if not data:
        raise NotFoundError("Chat session not found")
    return data
