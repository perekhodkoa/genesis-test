import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import create_access_token, hash_password, verify_password
from app.middleware.error_handler import AuthenticationError, AppError, ValidationError
from app.repositories import invite_repo, user_repo


async def register(
    session: AsyncSession, username: str, password: str, invite_code: str | None = None
) -> dict:
    username = username.lower()
    existing = await user_repo.get_user_by_username(session, username)
    if existing:
        raise AppError("Username already taken", status_code=409)

    # First-user bootstrap: allow registration without invite if no users exist
    users_exist = await invite_repo.has_any_user(session)
    invite = None
    if users_exist:
        if not invite_code:
            raise ValidationError("Invite code is required")
        invite = await invite_repo.get_valid_invite(session, invite_code)
        if not invite:
            raise ValidationError("Invalid or expired invite code")

    hashed = hash_password(password)
    user = await user_repo.create_user(session, username, hashed)

    if invite:
        await invite_repo.mark_used(session, invite, user.id)

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


async def login(session: AsyncSession, username: str, password: str) -> dict:
    user = await user_repo.get_user_by_username(session, username.lower())
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid username or password")

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


async def get_current_user(session: AsyncSession, user_id: str) -> dict:
    user = await user_repo.get_user_by_id(session, uuid.UUID(user_id))
    if not user:
        raise AuthenticationError("User not found")
    return {"id": str(user.id), "username": user.username}


async def create_invite(session: AsyncSession, user_id: str) -> dict:
    code = secrets.token_urlsafe(16)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    invite = await invite_repo.create_invite(
        session, code=code, created_by=uuid.UUID(user_id), expires_at=expires_at
    )
    return {
        "code": invite.code,
        "expires_at": invite.expires_at.isoformat(),
    }


async def list_invites(session: AsyncSession, user_id: str) -> list[dict]:
    invites = await invite_repo.list_user_invites(session, uuid.UUID(user_id))
    return [
        {
            "code": inv.code,
            "created_at": inv.created_at.isoformat(),
            "expires_at": inv.expires_at.isoformat(),
            "is_used": inv.is_used,
            "used_by": str(inv.used_by) if inv.used_by else None,
        }
        for inv in invites
    ]
