import tempfile
import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.middleware.error_handler import ValidationError, AppError
from app.repositories import metadata_repo, user_repo
from app.schemas.upload import SniffResult, UploadResponse
from app.services import upload_service

router = APIRouter(prefix="/upload", tags=["upload"])

# Temporary storage for sniffed DataFrames keyed by user_id:filename
_sniff_cache: dict[str, tuple] = {}


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

    # Cache the parsed DataFrame for the confirm step
    cache_key = f"{user_id}:{file.filename}"
    # Save df to a temp parquet file to avoid holding large DataFrames in memory
    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    df.to_parquet(tmp.name, index=False)
    _sniff_cache[cache_key] = (tmp.name, file.filename, result)

    return result


@router.post("/confirm", response_model=UploadResponse)
async def confirm_upload(
    original_filename: str = Form(...),
    collection_name: str = Form(...),
    db_type: str = Form(...),
    overwrite: str = Form("false"),
    is_public: str = Form("false"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    """Confirm upload and ingest data into the chosen database."""
    from app.middleware.input_guard import validate_collection_name, sanitize_filename

    collection_name = validate_collection_name(collection_name)
    original_filename = sanitize_filename(original_filename)

    if db_type not in ("postgres", "mongodb"):
        raise ValidationError("db_type must be 'postgres' or 'mongodb'")

    cache_key = f"{user_id}:{original_filename}"
    cached = _sniff_cache.pop(cache_key, None)
    if not cached:
        raise ValidationError("No sniffed data found. Please sniff the file again.")

    parquet_path, filename, sniff_result = cached

    # Check for existing collection (owned by this user only)
    existing = await metadata_repo.get_owned_by_name(user_id, collection_name)
    if existing and overwrite.lower() != "true":
        # Put cached data back so user can retry with overwrite
        _sniff_cache[cache_key] = (parquet_path, filename, sniff_result)
        raise AppError(
            f"Collection '{collection_name}' already exists. Set overwrite to replace it.",
            status_code=409,
        )

    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
    finally:
        os.unlink(parquet_path)

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
        original_filename=filename,
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
