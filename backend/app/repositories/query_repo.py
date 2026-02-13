import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongodb
from app.middleware.error_handler import AppError

MAX_ROWS = 500


async def execute_sql(session: AsyncSession, query: str) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return results as list of dicts."""
    normalized = query.strip().rstrip(";").upper()
    if not normalized.startswith("SELECT"):
        raise AppError("Only SELECT queries are allowed", status_code=403)

    # Guard against destructive statements embedded in the query
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"}
    tokens = set(normalized.split())
    if tokens & forbidden:
        raise AppError("Query contains forbidden statements", status_code=403)

    result = await session.execute(text(query))
    columns = list(result.keys())
    rows = result.fetchmany(MAX_ROWS)
    return [dict(zip(columns, row)) for row in rows]


async def execute_mongodb(collection_name: str, pipeline: list[dict]) -> list[dict[str, Any]]:
    """Execute a MongoDB aggregation pipeline and return results."""
    db = get_mongodb()

    # Validate pipeline doesn't contain destructive operations
    forbidden_stages = {"$out", "$merge"}
    for stage in pipeline:
        stage_keys = set(stage.keys())
        if stage_keys & forbidden_stages:
            raise AppError("Pipeline contains forbidden stages ($out, $merge)", status_code=403)

    # Add a $limit if not present to prevent huge result sets
    has_limit = any("$limit" in stage for stage in pipeline)
    if not has_limit:
        pipeline.append({"$limit": MAX_ROWS})

    collection = db[collection_name]
    cursor = collection.aggregate(pipeline)
    results = await cursor.to_list(length=MAX_ROWS)

    # Convert ObjectId to string for JSON serialization
    for doc in results:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

    return results
