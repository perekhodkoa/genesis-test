import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", detail: str | None = None):
        super().__init__(message=message, status_code=404, detail=detail)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed", detail: str | None = None):
        super().__init__(message=message, status_code=401, detail=detail)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error", detail: str | None = None):
        super().__init__(message=message, status_code=422, detail=detail)


class LLMError(AppError):
    def __init__(self, message: str = "LLM service error", detail: str | None = None):
        super().__init__(message=message, status_code=502, detail=detail)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppError as e:
            logger.warning("Application error: %s (detail: %s)", e.message, e.detail)
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.message, "detail": e.detail},
            )
        except Exception as e:
            logger.error("Unhandled error: %s\n%s", str(e), traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "detail": None},
            )
