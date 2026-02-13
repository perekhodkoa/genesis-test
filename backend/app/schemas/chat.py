from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None  # None = new session
    message: str = Field(min_length=1, max_length=4000)
    model: str


class VisualizationResponse(BaseModel):
    chart_type: str
    title: str
    labels: list[str]
    datasets: list[dict[str, Any]]


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    query: str | None = None
    query_type: str | None = None
    visualization: VisualizationResponse | None = None
    follow_ups: list[str] = Field(default_factory=list)
    referenced_collections: list[str] = Field(default_factory=list)
    timestamp: datetime


class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessageResponse


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ChatHistoryResponse(BaseModel):
    session_id: str
    title: str
    messages: list[ChatMessageResponse]
