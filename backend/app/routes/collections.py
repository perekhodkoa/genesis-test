from fastapi import APIRouter, Depends

from app.dependencies import get_current_user_id
from app.middleware.error_handler import NotFoundError
from app.schemas.collection import CollectionDetail, CollectionSummary
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
