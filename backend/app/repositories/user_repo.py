import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def create_user(session: AsyncSession, username: str, password_hash: str) -> User:
    user = User(username=username, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
