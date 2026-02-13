import tempfile
import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.middleware.error_handler import ValidationError
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
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    """Confirm upload and ingest data into the chosen database."""
    if db_type not in ("postgres", "mongodb"):
        raise ValidationError("db_type must be 'postgres' or 'mongodb'")

    cache_key = f"{user_id}:{original_filename}"
    cached = _sniff_cache.pop(cache_key, None)
    if not cached:
        raise ValidationError("No sniffed data found. Please sniff the file again.")

    parquet_path, filename, sniff_result = cached

    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
    finally:
        os.unlink(parquet_path)

    if db_type == "postgres":
        row_count = await upload_service.ingest_postgres(
            session, df, collection_name, sniff_result["columns"]
        )
    else:
        row_count = await upload_service.ingest_mongodb(df, collection_name)

    await upload_service.save_metadata(
        collection_name=collection_name,
        db_type=db_type,
        original_filename=filename,
        owner_id=user_id,
        row_count=row_count,
        sniff_result=sniff_result,
    )

    return UploadResponse(
        collection_name=collection_name,
        db_type=db_type,
        row_count=row_count,
        column_count=len(sniff_result["columns"]),
        message=f"Successfully uploaded {row_count} rows into {db_type}:{collection_name}",
    )
