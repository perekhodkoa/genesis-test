from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class VisualizationData(BaseModel):
    chart_type: str  # "bar", "pie", "line"
    title: str = ""
    labels: list[str] = Field(default_factory=list)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    # datasets: [{label, data: [...], backgroundColor?: [...]}]


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    query: str | None = None  # SQL or MongoDB query used
    query_type: str | None = None  # "sql" or "mongodb"
    visualization: VisualizationData | None = None
    follow_ups: list[str] = Field(default_factory=list)
    referenced_collections: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSession(BaseModel):
    """Stored in MongoDB 'chat_sessions' collection."""
    session_id: str
    owner_id: str
    title: str = "New Chat"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
