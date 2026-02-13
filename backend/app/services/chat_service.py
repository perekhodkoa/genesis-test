import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError, ValidationError
from app.models.chat import ChatMessage, VisualizationData
from app.repositories import chat_repo, metadata_repo, query_repo
from app.services import llm_service


def extract_collection_refs(message: str) -> list[tuple[str, str | None]]:
    """Extract @collection_name and @owner:collection_name references.

    Returns list of (collection_name, owner_username_or_none).
    - @collection_name -> (collection_name, None) — resolve to user's own first
    - @owner:collection_name -> (collection_name, owner) — resolve by specific owner
    """
    refs = []
    # Match @owner:collection or @collection
    for match in re.finditer(r"@(?:(\w+):)?(\w+)", message):
        owner = match.group(1)  # None if plain @collection
        name = match.group(2)
        refs.append((name, owner))
    return refs


async def _resolve_schemas(owner_id: str, refs: list[tuple[str, str | None]]) -> list[dict]:
    """Resolve collection refs to metadata, handling qualified owner:name refs."""
    schemas = []
    seen = set()
    for name, ref_owner in refs:
        if ref_owner:
            # Qualified ref: find by owner username
            meta = await metadata_repo.get_by_name_and_owner_username(name, ref_owner)
        else:
            # Unqualified: prefer user's own, fall back to any accessible
            meta = await metadata_repo.get_owned_by_name(owner_id, name)
            if not meta:
                meta = await metadata_repo.get_by_name(owner_id, name)
        if meta and meta["name"] not in seen:
            schemas.append(meta)
            seen.add(meta["name"])
    return schemas


async def handle_message(
    session: AsyncSession,
    owner_id: str,
    session_id: str | None,
    message: str,
) -> dict:
    """Process a user chat message end-to-end."""
    # 1. Create or retrieve chat session
    if not session_id:
        session_id = str(uuid.uuid4())
        await chat_repo.create_session(session_id, owner_id)

    existing = await chat_repo.get_session(session_id, owner_id)
    if not existing:
        await chat_repo.create_session(session_id, owner_id)

    # 2. Extract @references and fetch their schemas
    refs = extract_collection_refs(message)
    ref_names = [name for name, _ in refs]
    if not refs:
        # If no explicit refs, fetch all user collections for context
        all_meta = await metadata_repo.get_all_for_user(owner_id)
        schemas = all_meta[:10]  # limit context
    else:
        schemas = await _resolve_schemas(owner_id, refs)
        if not schemas:
            raise ValidationError(
                f"Referenced collections not found: {', '.join(ref_names)}",
                detail="Use @collection_name or @owner:collection_name to reference data",
            )

    # 3. Save user message to history
    user_msg = ChatMessage(role="user", content=message, referenced_collections=ref_names)
    await chat_repo.append_message(session_id, owner_id, user_msg)

    # 4. Get chat history for context
    session_data = await chat_repo.get_session(session_id, owner_id)
    history = session_data.get("messages", []) if session_data else []

    # 5. Ask LLM to generate query
    query_response = await llm_service.generate_query(message, schemas, history)

    query = query_response.get("query", "")
    query_type = query_response.get("query_type", "sql")
    collection_name = query_response.get("collection_name", "")

    # 6. Execute the query
    results = await _execute_query(session, query, query_type, collection_name)

    # 7. Ask LLM to generate natural language answer from results
    answer_response = await llm_service.generate_answer(
        message, query, query_type, results, schemas
    )

    answer_text = answer_response.get("answer", "I couldn't generate an answer.")
    follow_ups = answer_response.get("follow_ups", [])[:3]
    viz_data = _parse_visualization(answer_response.get("visualization"))

    # 8. Save assistant message to history
    assistant_msg = ChatMessage(
        role="assistant",
        content=answer_text,
        query=query,
        query_type=query_type,
        visualization=viz_data,
        follow_ups=follow_ups,
        referenced_collections=ref_names or ([collection_name] if collection_name else []),
    )
    await chat_repo.append_message(session_id, owner_id, assistant_msg)

    # 9. Update session title from first message
    if len(history) <= 1:
        title = message[:60] + ("..." if len(message) > 60 else "")
        await chat_repo.update_title(session_id, owner_id, title)

    return {
        "session_id": session_id,
        "message": assistant_msg.model_dump(mode="json"),
    }


async def _execute_query(
    session: AsyncSession,
    query: str,
    query_type: str,
    collection_name: str,
) -> list[dict[str, Any]]:
    """Execute a generated query, returning results or an error message."""
    if not query:
        return []

    try:
        if query_type == "sql":
            return await query_repo.execute_sql(session, query)
        elif query_type == "mongodb":
            import json
            pipeline = json.loads(query) if isinstance(query, str) else query
            if not isinstance(pipeline, list):
                pipeline = [pipeline]
            return await query_repo.execute_mongodb(collection_name, pipeline)
        else:
            return []
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            f"Query execution failed: {str(e)[:200]}",
            status_code=400,
            detail=f"Query: {query[:300]}",
        )


def _parse_visualization(viz: dict | None) -> VisualizationData | None:
    """Parse visualization spec from LLM response."""
    if not viz or not isinstance(viz, dict):
        return None

    chart_type = viz.get("chart_type")
    if chart_type not in ("bar", "pie", "line"):
        return None

    return VisualizationData(
        chart_type=chart_type,
        title=viz.get("title", ""),
        labels=viz.get("labels", []),
        datasets=viz.get("datasets", []),
    )
