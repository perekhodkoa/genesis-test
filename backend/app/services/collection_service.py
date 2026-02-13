from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import metadata_repo
from app.services.upload_service import drop_existing_postgres, drop_existing_mongodb


async def list_collections(owner_id: str) -> list[dict]:
    items = await metadata_repo.get_all_for_user(owner_id)
    return [
        {
            "name": m["name"],
            "db_type": m["db_type"],
            "original_filename": m["original_filename"],
            "row_count": m["row_count"],
            "column_count": len(m.get("columns", [])),
            "description": m.get("description", ""),
            "is_public": m.get("is_public", False),
            "is_own": m.get("owner_id") == owner_id,
            "owner_username": m.get("owner_username", ""),
            "created_at": m["created_at"],
        }
        for m in items
    ]


async def get_collection_detail(owner_id: str, name: str) -> dict | None:
    meta = await metadata_repo.get_by_name(owner_id, name)
    if not meta:
        return None
    return {
        "name": meta["name"],
        "db_type": meta["db_type"],
        "original_filename": meta["original_filename"],
        "row_count": meta["row_count"],
        "column_count": len(meta.get("columns", [])),
        "description": meta.get("description", ""),
        "is_public": meta.get("is_public", False),
        "is_own": meta.get("owner_id") == owner_id,
        "owner_username": meta.get("owner_username", ""),
        "created_at": meta["created_at"],
        "columns": meta.get("columns", []),
        "sample_rows": meta.get("sample_rows", []),
    }


async def toggle_public(owner_id: str, name: str, is_public: bool) -> dict | None:
    """Toggle public visibility. Only the owner can do this."""
    meta = await metadata_repo.get_owned_by_name(owner_id, name)
    if not meta:
        return None
    await metadata_repo.set_public(owner_id, name, is_public)
    meta["is_public"] = is_public
    return {
        "name": meta["name"],
        "is_public": is_public,
    }


async def delete_collection(session: AsyncSession, owner_id: str, name: str) -> bool:
    """Delete a collection: drop data from DB and remove metadata. Owner only."""
    meta = await metadata_repo.get_owned_by_name(owner_id, name)
    if not meta:
        return False

    db_type = meta.get("db_type", "postgres")
    if db_type == "postgres":
        await drop_existing_postgres(session, name)
    else:
        await drop_existing_mongodb(name)

    await metadata_repo.delete_metadata(owner_id, name)
    return True
