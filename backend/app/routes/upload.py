from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.middleware.error_handler import ValidationError, AppError
from app.repositories import metadata_repo, user_repo
from app.schemas.upload import SniffResult, UploadResponse
from app.services import upload_service

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/sniff", response_model=SniffResult)
async def sniff_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Parse file and return schema preview + DB recommendation without ingesting."""
    df = await upload_service.parse_file(file)
    raw_json = None
    if file.filename and file.filename.endswith(".json"):
        await file.seek(0)
        raw_json = await file.read()

    result = upload_service.sniff_data(df, raw_json)
    return result


@router.post("/confirm", response_model=UploadResponse)
async def confirm_upload(
    file: UploadFile = File(...),
    collection_name: str = Form(...),
    db_type: str = Form(...),
    overwrite: str = Form("false"),
    is_public: str = Form("false"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    """Confirm upload and ingest data into the chosen database."""
    from app.middleware.input_guard import validate_collection_name

    collection_name = validate_collection_name(collection_name)

    if db_type not in ("postgres", "mongodb"):
        raise ValidationError("db_type must be 'postgres' or 'mongodb'")

    # Re-parse the file (no longer relies on in-memory cache)
    df = await upload_service.parse_file(file)
    raw_json = None
    if file.filename and file.filename.endswith(".json"):
        await file.seek(0)
        raw_json = await file.read()
    sniff_result = upload_service.sniff_data(df, raw_json)

    # Check for existing collection (owned by this user only)
    existing = await metadata_repo.get_owned_by_name(user_id, collection_name)
    if existing and overwrite.lower() != "true":
        raise AppError(
            f"Collection '{collection_name}' already exists. Set overwrite to replace it.",
            status_code=409,
        )

    # Drop existing data if overwriting
    if existing and overwrite.lower() == "true":
        if existing["db_type"] == "postgres":
            await upload_service.drop_existing_postgres(session, collection_name)
        else:
            await upload_service.drop_existing_mongodb(collection_name)

    if db_type == "postgres":
        row_count = await upload_service.ingest_postgres(
            session, df, collection_name, sniff_result["columns"]
        )
    else:
        row_count = await upload_service.ingest_mongodb(df, collection_name)

    # Fetch username for metadata
    import uuid
    user = await user_repo.get_user_by_id(session, uuid.UUID(user_id))
    owner_username = user.username if user else ""

    await upload_service.save_metadata(
        collection_name=collection_name,
        db_type=db_type,
        original_filename=file.filename or "",
        owner_id=user_id,
        owner_username=owner_username,
        row_count=row_count,
        sniff_result=sniff_result,
        is_public=is_public.lower() == "true",
    )

    action = "replaced" if existing else "uploaded"
    return UploadResponse(
        collection_name=collection_name,
        db_type=db_type,
        row_count=row_count,
        column_count=len(sniff_result["columns"]),
        message=f"Successfully {action} {row_count} rows into {db_type}:{collection_name}",
    )
