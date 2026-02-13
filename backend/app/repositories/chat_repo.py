from datetime import datetime, timezone

from app.db.mongodb import get_mongodb
from app.models.chat import ChatMessage, ChatSession

COLLECTION = "chat_sessions"


async def create_session(session_id: str, owner_id: str, title: str = "New Chat") -> ChatSession:
    db = get_mongodb()
    chat_session = ChatSession(session_id=session_id, owner_id=owner_id, title=title)
    await db[COLLECTION].insert_one(chat_session.model_dump(mode="json"))
    return chat_session


async def get_session(session_id: str, owner_id: str) -> dict | None:
    db = get_mongodb()
    return await db[COLLECTION].find_one(
        {"session_id": session_id, "owner_id": owner_id},
        {"_id": 0},
    )


async def append_message(session_id: str, owner_id: str, message: ChatMessage) -> None:
    db = get_mongodb()
    await db[COLLECTION].update_one(
        {"session_id": session_id, "owner_id": owner_id},
        {
            "$push": {"messages": message.model_dump(mode="json")},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )


async def update_title(session_id: str, owner_id: str, title: str) -> None:
    db = get_mongodb()
    await db[COLLECTION].update_one(
        {"session_id": session_id, "owner_id": owner_id},
        {"$set": {"title": title}},
    )


async def list_sessions(owner_id: str) -> list[dict]:
    db = get_mongodb()
    cursor = db[COLLECTION].find(
        {"owner_id": owner_id},
        {"_id": 0, "session_id": 1, "title": 1, "created_at": 1, "updated_at": 1, "messages": 1},
    ).sort("updated_at", -1)
    results = await cursor.to_list(length=100)
    for r in results:
        r["message_count"] = len(r.pop("messages", []))
    return results
