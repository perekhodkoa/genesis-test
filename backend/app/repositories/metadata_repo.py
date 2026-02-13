from app.db.mongodb import get_mongodb
from app.models.metadata import CollectionMetadata

COLLECTION = "collection_metadata"


async def upsert_metadata(meta: CollectionMetadata) -> None:
    db = get_mongodb()
    await db[COLLECTION].update_one(
        {"name": meta.name, "owner_id": meta.owner_id},
        {"$set": meta.model_dump(mode="json")},
        upsert=True,
    )


async def get_all_for_user(owner_id: str) -> list[dict]:
    """Return user's own collections plus all public collections."""
    db = get_mongodb()
    cursor = db[COLLECTION].find(
        {"$or": [{"owner_id": owner_id}, {"is_public": True}]},
        {"_id": 0},
    ).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def get_by_name(owner_id: str, name: str) -> dict | None:
    """Find a collection the user owns or that is public."""
    db = get_mongodb()
    return await db[COLLECTION].find_one(
        {"name": name, "$or": [{"owner_id": owner_id}, {"is_public": True}]},
        {"_id": 0},
    )


async def get_by_names(owner_id: str, names: list[str]) -> list[dict]:
    """Find collections the user owns or that are public."""
    db = get_mongodb()
    cursor = db[COLLECTION].find(
        {"name": {"$in": names}, "$or": [{"owner_id": owner_id}, {"is_public": True}]},
        {"_id": 0},
    )
    return await cursor.to_list(length=100)


async def get_owned_by_name(owner_id: str, name: str) -> dict | None:
    """Find a collection owned by this user only (for overwrite checks)."""
    db = get_mongodb()
    return await db[COLLECTION].find_one(
        {"name": name, "owner_id": owner_id},
        {"_id": 0},
    )


async def delete_metadata(owner_id: str, name: str) -> bool:
    db = get_mongodb()
    result = await db[COLLECTION].delete_one({"name": name, "owner_id": owner_id})
    return result.deleted_count > 0
