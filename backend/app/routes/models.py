import logging
import time

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

_CACHE_TTL = 300  # 5 minutes
_cached_models: list[dict] | None = None
_cache_ts: float = 0


class ModelInfo(BaseModel):
    id: str
    name: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default: str


async def _fetch_models_from_proxy() -> list[dict]:
    """Fetch available models from the LiteLLM proxy."""
    global _cached_models, _cache_ts

    now = time.monotonic()
    if _cached_models is not None and now - _cache_ts < _CACHE_TTL:
        return _cached_models

    headers = {}
    if settings.litellm_api_key:
        headers["Authorization"] = f"Bearer {settings.litellm_api_key}"

    try:
        url = f"{settings.litellm_proxy_url}/model/info"
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
        data = res.json()
        models = []
        for m in data.get("data", []):
            model_id = m.get("model_name", "")
            if not model_id:
                continue
            # Extract actual model name from litellm_params
            actual = (
                m.get("litellm_params", {})
                .get("model", model_id)
            )
            # Strip provider prefix (e.g. "anthropic/claude-..." → "claude-...")
            display = actual.split("/", 1)[-1] if "/" in actual else actual
            models.append({"id": model_id, "name": display})
        if models:
            _cached_models = models
            _cache_ts = now
            return models
    except Exception:
        logger.warning("Failed to fetch models from LiteLLM proxy", exc_info=True)

    if _cached_models is not None:
        return _cached_models

    return []


@router.get("", response_model=ModelsResponse)
async def list_models(_user_id: str = Depends(get_current_user_id)):
    """List available LLM models."""
    models = await _fetch_models_from_proxy()
    # Prefer claude-sonnet-4-5 if available
    default = ""
    for m in models:
        if "claude-sonnet-4-5" in m.get("name", "") or "claude-sonnet-4-5" in m.get("id", ""):
            default = m["id"]
            break
    if not default and models:
        default = models[0]["id"]
    return {"models": models, "default": default}
