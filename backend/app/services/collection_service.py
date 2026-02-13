from app.repositories import metadata_repo


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
        "created_at": meta["created_at"],
        "columns": meta.get("columns", []),
        "sample_rows": meta.get("sample_rows", []),
    }
