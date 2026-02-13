import io
import json
import re
from typing import Any

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongodb
from app.middleware.error_handler import ValidationError, AppError
from app.models.metadata import CollectionMetadata, ColumnSchema
from app.repositories import metadata_repo

SNIFF_ROWS = 5
MAX_FILE_SIZE_MB = 100


def _sanitize_column_name(name: str) -> str:
    """Make column names safe for SQL."""
    name = re.sub(r"[^\w]", "_", str(name).strip().lower())
    if name and name[0].isdigit():
        name = f"col_{name}"
    return name or "unnamed"


def _pandas_dtype_to_str(dtype) -> str:
    dtype_str = str(dtype)
    if "int" in dtype_str:
        return "integer"
    if "float" in dtype_str:
        return "float"
    if "bool" in dtype_str:
        return "boolean"
    if "datetime" in dtype_str:
        return "datetime"
    return "string"


def _pandas_dtype_to_sql(dtype_str: str) -> str:
    mapping = {
        "integer": "BIGINT",
        "float": "DOUBLE PRECISION",
        "boolean": "BOOLEAN",
        "datetime": "TIMESTAMP",
        "string": "TEXT",
    }
    return mapping.get(dtype_str, "TEXT")


async def parse_file(file: UploadFile) -> pd.DataFrame:
    """Parse uploaded file into a DataFrame."""
    content = await file.read()

    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"File exceeds {MAX_FILE_SIZE_MB}MB limit")

    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        return pd.read_csv(io.BytesIO(content))
    elif ext == "tsv":
        return pd.read_csv(io.BytesIO(content), sep="\t")
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(content))
    elif ext == "json":
        return _parse_json(content)
    else:
        raise ValidationError(f"Unsupported file type: .{ext}. Supported: csv, tsv, xlsx, xls, json")


def _parse_json(content: bytes) -> pd.DataFrame:
    """Parse JSON content. Handles both array-of-objects and nested structures."""
    data = json.loads(content)

    if isinstance(data, list):
        return pd.json_normalize(data)
    elif isinstance(data, dict):
        # Check if it's a single record or has a data key
        for key in ("data", "results", "records", "items", "rows"):
            if key in data and isinstance(data[key], list):
                return pd.json_normalize(data[key])
        # Treat as single record
        return pd.json_normalize([data])
    else:
        raise ValidationError("JSON must be an object or array of objects")


def _is_nested(data: Any) -> bool:
    """Check if data has nested/hierarchical structure."""
    if isinstance(data, dict):
        return any(isinstance(v, (dict, list)) for v in data.values())
    return False


def sniff_data(df: pd.DataFrame, raw_json: bytes | None = None) -> dict:
    """Analyze first few rows and produce schema + recommendation."""
    df.columns = [_sanitize_column_name(c) for c in df.columns]

    sample = df.head(SNIFF_ROWS)
    columns = []
    for col in df.columns:
        col_schema = ColumnSchema(
            name=col,
            dtype=_pandas_dtype_to_str(df[col].dtype),
            nullable=bool(df[col].isna().any()),
            sample_values=sample[col].dropna().tolist()[:SNIFF_ROWS],
        )
        columns.append(col_schema)

    # Determine if data is nested (favor MongoDB)
    has_nested = any("." in col for col in df.columns)  # json_normalize produces dotted names
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            items = parsed if isinstance(parsed, list) else [parsed]
            has_nested = any(_is_nested(item) for item in items[:SNIFF_ROWS])
        except (json.JSONDecodeError, TypeError):
            pass

    if has_nested:
        recommended_db = "mongodb"
        reason = "Data contains nested/hierarchical structures, better suited for MongoDB document storage."
    else:
        recommended_db = "postgres"
        reason = "Data is flat/tabular, well-suited for PostgreSQL relational storage."

    sample_rows = sample.where(sample.notna(), None).to_dict(orient="records")

    return {
        "columns": [c.model_dump() for c in columns],
        "sample_rows": sample_rows,
        "row_count": len(df),
        "recommended_db": recommended_db,
        "recommendation_reason": reason,
    }


async def ingest_postgres(
    session: AsyncSession,
    df: pd.DataFrame,
    collection_name: str,
    columns: list[dict],
) -> int:
    """Create table and insert data into PostgreSQL."""
    df.columns = [_sanitize_column_name(c) for c in df.columns]

    # Build CREATE TABLE
    col_defs = []
    for col_info in columns:
        sql_type = _pandas_dtype_to_sql(col_info["dtype"])
        nullable = "NULL" if col_info.get("nullable", True) else "NOT NULL"
        col_defs.append(f'"{col_info["name"]}" {sql_type} {nullable}')

    create_sql = f'CREATE TABLE IF NOT EXISTS "{collection_name}" (\n  id BIGSERIAL PRIMARY KEY,\n  {",\n  ".join(col_defs)}\n)'
    await session.execute(text(create_sql))

    # Insert rows in batches
    if len(df) == 0:
        await session.commit()
        return 0

    col_names = [c["name"] for c in columns]
    placeholders = ", ".join(f":{c}" for c in col_names)
    col_list = ", ".join(f'"{c}"' for c in col_names)
    insert_sql = text(f'INSERT INTO "{collection_name}" ({col_list}) VALUES ({placeholders})')

    records = df.where(df.notna(), None).to_dict(orient="records")
    batch_size = 1000
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        await session.execute(insert_sql, batch)

    await session.commit()
    return len(records)


async def ingest_mongodb(
    df: pd.DataFrame,
    collection_name: str,
) -> int:
    """Create collection and insert data into MongoDB."""
    db = get_mongodb()
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    if not records:
        return 0

    collection = db[collection_name]
    batch_size = 1000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        await collection.insert_many(batch)
        total += len(batch)

    return total


async def save_metadata(
    collection_name: str,
    db_type: str,
    original_filename: str,
    owner_id: str,
    row_count: int,
    sniff_result: dict,
) -> None:
    """Save collection metadata to MongoDB."""
    meta = CollectionMetadata(
        name=collection_name,
        db_type=db_type,
        original_filename=original_filename,
        owner_id=owner_id,
        row_count=row_count,
        columns=[ColumnSchema(**c) for c in sniff_result["columns"]],
        description=f"Uploaded from {original_filename}. {row_count} rows, {len(sniff_result['columns'])} columns.",
        sample_rows=sniff_result["sample_rows"],
    )
    await metadata_repo.upsert_metadata(meta)
