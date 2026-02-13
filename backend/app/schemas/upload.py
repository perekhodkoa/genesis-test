from typing import Any

from pydantic import BaseModel, Field


class SniffResult(BaseModel):
    columns: list[dict[str, Any]]  # [{name, dtype, nullable, sample_values}]
    sample_rows: list[dict[str, Any]]
    row_count: int
    recommended_db: str  # "postgres" or "mongodb"
    recommendation_reason: str


class UploadRequest(BaseModel):
    """Sent after sniff to confirm upload settings."""
    collection_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    db_type: str = Field(pattern=r"^(postgres|mongodb)$")


class UploadResponse(BaseModel):
    collection_name: str
    db_type: str
    row_count: int
    column_count: int
    message: str
