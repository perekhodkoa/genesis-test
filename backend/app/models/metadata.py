from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    name: str
    dtype: str  # e.g. "integer", "float", "string", "boolean", "datetime", "object"
    nullable: bool = True
    sample_values: list[Any] = Field(default_factory=list)


class CollectionMetadata(BaseModel):
    """Stored in MongoDB 'collection_metadata' collection."""
    name: str  # table name or collection name
    db_type: str  # "postgres" or "mongodb"
    original_filename: str
    owner_id: str
    row_count: int = 0
    columns: list[ColumnSchema] = Field(default_factory=list)
    description: str = ""  # auto-generated brief description
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)  # first 3-5 rows
    is_public: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
