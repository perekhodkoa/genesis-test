import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongodb
from app.middleware.error_handler import AppError

MAX_ROWS = 500

# --- SQL hardening helpers ---

# Regex to match SQL string literals (single-quoted, handles escaped quotes)
_SQL_STRING_RE = re.compile(r"'(?:[^'\\]|\\.)*'")
_SQL_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "INTO", "COPY",
}


def _strip_sql_comments(query: str) -> str:
    """Remove SQL comments while preserving string literals."""
    strings: list[str] = []

    def _save_string(match: re.Match) -> str:
        strings.append(match.group(0))
        return f"__STR{len(strings) - 1}__"

    q = _SQL_STRING_RE.sub(_save_string, query)
    q = _SQL_BLOCK_COMMENT_RE.sub(" ", q)
    q = _SQL_LINE_COMMENT_RE.sub(" ", q)

    for i, s in enumerate(strings):
        q = q.replace(f"__STR{i}__", s, 1)
    return q


def _extract_non_string_tokens(query: str) -> set[str]:
    """Extract uppercase tokens from parts outside string literals."""
    parts = _SQL_STRING_RE.split(query)
    tokens: set[str] = set()
    for part in parts:
        tokens.update(part.upper().split())
    return tokens


def _count_statements(query: str) -> int:
    """Count semicolon-separated statements, ignoring semicolons inside string literals."""
    stripped = _SQL_STRING_RE.sub("''", query)
    stmts = [s.strip() for s in stripped.split(";") if s.strip()]
    return len(stmts)


async def execute_sql(session: AsyncSession, query: str) -> list[dict[str, Any]]:
    """Execute a read-only SQL query with hardened validation."""
    # 1. Strip comments (can hide keywords)
    cleaned = _strip_sql_comments(query.strip())

    # 2. Reject multiple statements (prevent stacked queries)
    if _count_statements(cleaned) > 1:
        raise AppError("Only a single SQL statement is allowed", status_code=403)

    # 3. Normalize
    cleaned = cleaned.strip().rstrip(";").strip()

    # 4. Must start with SELECT
    if not cleaned.upper().startswith("SELECT"):
        raise AppError("Only SELECT queries are allowed", status_code=403)

    # 5. Check forbidden keywords OUTSIDE string literals
    tokens = _extract_non_string_tokens(cleaned)
    found = tokens & FORBIDDEN_SQL_KEYWORDS
    if found:
        raise AppError(
            f"Query contains forbidden keywords: {', '.join(sorted(found))}",
            status_code=403,
        )

    # 6. Execute in READ ONLY transaction as ultimate backstop
    await session.execute(text("SET TRANSACTION READ ONLY"))
    result = await session.execute(text(cleaned))
    columns = list(result.keys())
    rows = result.fetchmany(MAX_ROWS)
    return [dict(zip(columns, row)) for row in rows]


# --- MongoDB hardening ---

FORBIDDEN_MONGO_OPERATORS = {
    "$out", "$merge",         # write to collection
    "$function",              # arbitrary JS execution
    "$accumulator",           # arbitrary JS execution
    "$where",                 # JS expression evaluation
    "$currentOp",             # server internals
    "$listSessions",          # session data
    "$planCacheStats",        # server internals
    "$collStats",             # internal stats
    "$indexStats",            # internal stats
}


def _check_mongo_value(value: Any) -> None:
    """Recursively inspect a MongoDB pipeline value for forbidden operators."""
    if isinstance(value, dict):
        for key, val in value.items():
            if key in FORBIDDEN_MONGO_OPERATORS:
                raise AppError(f"Pipeline contains forbidden operator: {key}", status_code=403)
            _check_mongo_value(val)
    elif isinstance(value, list):
        for item in value:
            _check_mongo_value(item)


async def execute_mongodb(collection_name: str, pipeline: list[dict]) -> list[dict[str, Any]]:
    """Execute a MongoDB aggregation pipeline with hardened validation."""
    db = get_mongodb()

    # Deep recursive check for forbidden operators
    for stage in pipeline:
        _check_mongo_value(stage)

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
