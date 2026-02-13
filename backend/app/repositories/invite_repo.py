import uuid
from datetime import datetime, timezone

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invite_code import InviteCode
from app.models.user import User


async def create_invite(
    session: AsyncSession,
    code: str,
    created_by: uuid.UUID,
    expires_at: datetime,
) -> InviteCode:
    invite = InviteCode(code=code, created_by=created_by, expires_at=expires_at)
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite


async def get_valid_invite(session: AsyncSession, code: str) -> InviteCode | None:
    result = await session.execute(
        select(InviteCode).where(
            InviteCode.code == code,
            InviteCode.is_used.is_(False),
            InviteCode.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def mark_used(
    session: AsyncSession, invite: InviteCode, user_id: uuid.UUID
) -> None:
    invite.is_used = True
    invite.used_by = user_id
    await session.commit()


async def list_user_invites(
    session: AsyncSession, user_id: uuid.UUID
) -> list[InviteCode]:
    result = await session.execute(
        select(InviteCode)
        .where(InviteCode.created_by == user_id)
        .order_by(InviteCode.created_at.desc())
    )
    return list(result.scalars().all())


async def has_any_user(session: AsyncSession) -> bool:
    result = await session.execute(select(exists().where(User.id.isnot(None))))
    return result.scalar()
