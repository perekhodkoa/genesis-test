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
    """Parse JSON content. Handles wrapper objects, GeoJSON, arrays, and nested structures."""
    data = json.loads(content)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = _unwrap_json_object(data)
    else:
        raise ValidationError("JSON must be an object or array of objects")

    if not items:
        raise ValidationError("JSON contains no records")

    items = _flatten_geojson(items)
    return pd.json_normalize(items)


def _unwrap_json_object(data: dict) -> list[dict]:
    """Unwrap a JSON wrapper object to extract the array of records.

    Strategy:
    1. Check well-known keys (data, results, records, items, rows, features)
    2. If no match, detect a single top-level field whose value is a list of dicts
    3. Otherwise treat as a single record
    """
    well_known = ("data", "results", "records", "items", "rows", "features")
    for key in well_known:
        if key in data and isinstance(data[key], list) and data[key]:
            return data[key]

    # Auto-detect: find fields whose value is a list of dicts
    array_fields = [
        k for k, v in data.items()
        if isinstance(v, list) and v and isinstance(v[0], dict)
    ]
    if len(array_fields) == 1:
        return data[array_fields[0]]

    # Treat the whole object as a single record
    return [data]


def _flatten_geojson(items: list[dict]) -> list[dict]:
    """If items look like GeoJSON features, flatten properties to top level."""
    if not items:
        return items

    sample = items[0]
    is_geojson = (
        isinstance(sample, dict)
        and sample.get("type") == "Feature"
        and isinstance(sample.get("properties"), dict)
    )
    if not is_geojson:
        return items

    flattened = []
    for item in items:
        props = item.get("properties") or {}
        row = {**props}

        geometry = item.get("geometry")
        if isinstance(geometry, dict):
            row["geometry_type"] = geometry.get("type", "")
            coords = geometry.get("coordinates")
            if coords is not None:
                row["geometry_coordinates"] = json.dumps(coords)

        # Preserve any other top-level fields besides type/properties/geometry
        for k, v in item.items():
            if k not in ("type", "properties", "geometry"):
                row[k] = v

        flattened.append(row)

    return flattened


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
    df = _clean_dataframe(df.copy())
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


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string columns and coerce numeric-looking columns."""
    for col in df.columns:
        if df[col].dtype == object:
            # Strip whitespace from string values
            df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)
            # Try to coerce to numeric (int/float) — leaves non-numeric as-is
            coerced = pd.to_numeric(df[col], errors="coerce")
            # Only convert if most non-null values successfully converted
            non_null = df[col].notna().sum()
            if non_null > 0 and coerced.notna().sum() / non_null >= 0.8:
                df[col] = coerced
    return df


async def ingest_mongodb(
    df: pd.DataFrame,
    collection_name: str,
) -> int:
    """Create collection and insert data into MongoDB."""
    db = get_mongodb()
    df = _clean_dataframe(df.copy())
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


async def drop_existing_postgres(session: AsyncSession, collection_name: str) -> None:
    """Drop a PostgreSQL table if it exists."""
    await session.execute(text(f'DROP TABLE IF EXISTS "{collection_name}" CASCADE'))
    await session.commit()


async def drop_existing_mongodb(collection_name: str) -> None:
    """Drop a MongoDB collection if it exists."""
    db = get_mongodb()
    await db[collection_name].drop()


async def save_metadata(
    collection_name: str,
    db_type: str,
    original_filename: str,
    owner_id: str,
    row_count: int,
    sniff_result: dict,
    is_public: bool = False,
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
        is_public=is_public,
    )
    await metadata_repo.upsert_metadata(meta)
