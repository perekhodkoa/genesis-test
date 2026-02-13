import json
import logging
import re

import httpx

from app.config import settings
from app.middleware.error_handler import LLMError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Data Lens, a data analysis assistant. You help users query and understand their data.

When the user asks a question about their data, you must:
1. Generate the appropriate database query (SQL for PostgreSQL tables, MongoDB aggregation pipeline for MongoDB collections)
2. The query will be executed automatically - you'll receive the results
3. Provide a clear natural language answer based on the results
4. If the data is suitable for visualization, include a visualization spec

IMPORTANT RULES:
- Only generate SELECT queries for PostgreSQL (no mutations)
- Only generate aggregation pipelines for MongoDB (no $out, $merge)
- Use the provided schema and sample data to write accurate queries
- Reference exact column/field names from the schema
- Keep queries efficient; use LIMIT when appropriate

For your response, output valid JSON with this structure:
{
  "query": "the SQL query or MongoDB pipeline as string",
  "query_type": "sql" or "mongodb",
  "collection_name": "name of the table/collection being queried",
  "answer": "natural language answer (written AFTER seeing results - leave as empty string in query phase)",
  "visualization": null or {
    "chart_type": "bar" | "pie" | "line",
    "title": "chart title",
    "label_field": "field name for labels/x-axis",
    "value_fields": ["field1", "field2"],
    "description": "what this chart shows"
  },
  "follow_ups": ["follow-up question 1", "follow-up question 2", "follow-up question 3"]
}"""

ANSWER_PROMPT = """Based on the query results below, provide:
1. A clear natural language answer to the user's question
2. If visualization is appropriate, a visualization spec
3. 2-3 relevant follow-up questions the user might want to ask

Query results (JSON):
{results}

Respond with valid JSON:
{{
  "answer": "your natural language answer here",
  "visualization": null or {{
    "chart_type": "bar" | "pie" | "line",
    "title": "chart title",
    "labels": ["label1", "label2", ...],
    "datasets": [
      {{
        "label": "dataset name",
        "data": [value1, value2, ...]
      }}
    ]
  }},
  "follow_ups": ["question 1", "question 2", "question 3"]
}}"""


async def generate_query(
    user_message: str,
    collection_schemas: list[dict],
    chat_history: list[dict] | None = None,
) -> dict:
    """Ask LLM to generate a database query for the user's question."""
    schema_text = _format_schemas(collection_schemas)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"Available data sources:\n{schema_text}",
    })

    # Include recent chat history for context (last 6 messages max)
    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    return await _call_llm(messages)


async def generate_answer(
    user_message: str,
    query: str,
    query_type: str,
    results: list[dict],
    collection_schemas: list[dict],
) -> dict:
    """Ask LLM to produce a natural language answer from query results."""
    # Truncate results to avoid token burn
    truncated = results[:50]
    results_json = json.dumps(truncated, default=str, indent=2)

    schema_text = _format_schemas(collection_schemas)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Available data sources:\n{schema_text}"},
        {"role": "user", "content": user_message},
        {
            "role": "assistant",
            "content": f"I executed the following {query_type} query:\n```\n{query}\n```",
        },
        {
            "role": "user",
            "content": ANSWER_PROMPT.format(results=results_json),
        },
    ]

    return await _call_llm(messages)


def _format_schemas(schemas: list[dict]) -> str:
    parts = []
    for s in schemas:
        cols = s.get("columns", [])
        col_lines = [f"  - {c['name']} ({c['dtype']}): samples={c.get('sample_values', [])[:3]}" for c in cols]
        db_label = "PostgreSQL table" if s["db_type"] == "postgres" else "MongoDB collection"
        parts.append(
            f"[{db_label}] {s['name']}\n"
            f"  Description: {s.get('description', 'N/A')}\n"
            f"  Rows: {s.get('row_count', '?')}\n"
            f"  Columns:\n" + "\n".join(col_lines)
        )
    return "\n\n".join(parts)


async def _call_llm(messages: list[dict]) -> dict:
    """Call LiteLLM proxy and parse JSON response."""
    url = f"{settings.litellm_proxy_url}/v1/chat/completions"
    headers = {}
    if settings.litellm_api_key:
        headers["Authorization"] = f"Bearer {settings.litellm_api_key}"

    payload = {
        "model": "default",
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException:
        raise LLMError("LLM request timed out", detail="The LLM proxy did not respond in time")
    except httpx.HTTPStatusError as e:
        raise LLMError(
            f"LLM proxy returned {e.response.status_code}",
            detail=e.response.text[:500],
        )
    except httpx.ConnectError:
        raise LLMError(
            "Cannot connect to LLM proxy",
            detail=f"Check that LiteLLM proxy is running at {settings.litellm_proxy_url}",
        )

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    try:
        # Strip markdown code fencing that LLMs often add
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON, wrapping as answer: %s", content[:200])
        return {
            "query": "",
            "query_type": "sql",
            "collection_name": "",
            "answer": content.strip(),
            "visualization": None,
            "follow_ups": [],
        }