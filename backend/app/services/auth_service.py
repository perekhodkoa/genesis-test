import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import create_access_token, hash_password, verify_password
from app.middleware.error_handler import AuthenticationError, AppError
from app.repositories import user_repo


async def register(session: AsyncSession, username: str, password: str) -> dict:
    existing = await user_repo.get_user_by_username(session, username)
    if existing:
        raise AppError("Username already taken", status_code=409)

    hashed = hash_password(password)
    user = await user_repo.create_user(session, username, hashed)
    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


async def login(session: AsyncSession, username: str, password: str) -> dict:
    user = await user_repo.get_user_by_username(session, username)
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid username or password")

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


async def get_current_user(session: AsyncSession, user_id: str) -> dict:
    user = await user_repo.get_user_by_id(session, uuid.UUID(user_id))
    if not user:
        raise AuthenticationError("User not found")
    return {"id": str(user.id), "username": user.username}
