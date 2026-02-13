from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.middleware.error_handler import NotFoundError
from app.schemas.collection import CollectionDetail, CollectionSummary, TogglePublicRequest
from app.services import collection_service

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("/", response_model=list[CollectionSummary])
async def list_collections(user_id: str = Depends(get_current_user_id)):
    return await collection_service.list_collections(user_id)


@router.get("/{name}", response_model=CollectionDetail)
async def get_collection(name: str, user_id: str = Depends(get_current_user_id)):
    detail = await collection_service.get_collection_detail(user_id, name)
    if not detail:
        raise NotFoundError(f"Collection '{name}' not found")
    return detail


@router.patch("/{name}/public")
async def toggle_public(
    name: str,
    body: TogglePublicRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Toggle public visibility of a collection. Only the owner can do this."""
    result = await collection_service.toggle_public(user_id, name, body.is_public)
    if not result:
        raise NotFoundError(f"Collection '{name}' not found or you are not the owner")
    return result


@router.delete("/{name}")
async def delete_collection(
    name: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    """Delete a collection and its data. Only the owner can do this."""
    deleted = await collection_service.delete_collection(session, user_id, name)
    if not deleted:
        raise NotFoundError(f"Collection '{name}' not found or you are not the owner")
    return {"deleted": True}
