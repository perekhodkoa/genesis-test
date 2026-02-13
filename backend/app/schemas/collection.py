from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CollectionSummary(BaseModel):
    name: str
    db_type: str
    original_filename: str
    row_count: int
    column_count: int
    description: str
    is_public: bool = False
    is_own: bool = True
    owner_username: str = ""
    created_at: datetime


class TogglePublicRequest(BaseModel):
    is_public: bool


class CollectionDetail(CollectionSummary):
    columns: list[dict[str, Any]]
    sample_rows: list[dict[str, Any]]
