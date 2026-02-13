import uuid

from fastapi import Depends, Header

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.db.mongodb import get_mongodb
from app.middleware.auth import decode_access_token
from app.middleware.error_handler import AuthenticationError


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Extract and validate user ID from Bearer token."""
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header")

    token = authorization.removeprefix("Bearer ")
    user_id = decode_access_token(token)
    if user_id is None:
        raise AuthenticationError("Invalid or expired token")

    # Validate it's a proper UUID
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid token payload")

    return user_id
