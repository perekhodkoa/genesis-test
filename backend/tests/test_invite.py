import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.middleware.error_handler import ValidationError
from app.services import auth_service


@dataclass
class FakeInvite:
    id: uuid.UUID
    code: str
    created_by: uuid.UUID
    used_by: uuid.UUID | None
    created_at: datetime
    expires_at: datetime
    is_used: bool


def _make_invite(
    *,
    code: str = "test-invite-code",
    created_by: uuid.UUID | None = None,
    expires_at: datetime | None = None,
    is_used: bool = False,
) -> FakeInvite:
    return FakeInvite(
        id=uuid.uuid4(),
        code=code,
        created_by=created_by or uuid.uuid4(),
        used_by=None,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=24),
        is_used=is_used,
    )


# --- Registration with invites ---


@pytest.mark.asyncio
async def test_first_user_registers_without_invite(mock_pg_session):
    """When no users exist, registration succeeds without an invite code."""
    new_user_id = uuid.uuid4()

    async def fake_create(session, username, pw_hash):
        from tests.conftest import FakeUser
        return FakeUser(id=new_user_id, username=username, password_hash=pw_hash)

    with (
        patch.object(auth_service.invite_repo, "has_any_user", AsyncMock(return_value=False)),
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.user_repo, "create_user", side_effect=fake_create),
    ):
        result = await auth_service.register(mock_pg_session, "firstuser", "password123")

    assert "access_token" in result
    assert result["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_registration_fails_without_invite_when_users_exist(mock_pg_session):
    """When users exist, registration without invite code raises ValidationError."""
    with (
        patch.object(auth_service.invite_repo, "has_any_user", AsyncMock(return_value=True)),
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
    ):
        with pytest.raises(ValidationError) as exc_info:
            await auth_service.register(mock_pg_session, "newuser", "password123")
        assert "Invite code is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_registration_succeeds_with_valid_invite(mock_pg_session):
    """Registration with a valid invite code succeeds and marks invite used."""
    new_user_id = uuid.uuid4()
    invite = _make_invite(code="valid-code")
    mark_used_mock = AsyncMock()

    async def fake_create(session, username, pw_hash):
        from tests.conftest import FakeUser
        return FakeUser(id=new_user_id, username=username, password_hash=pw_hash)

    with (
        patch.object(auth_service.invite_repo, "has_any_user", AsyncMock(return_value=True)),
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.invite_repo, "get_valid_invite", AsyncMock(return_value=invite)),
        patch.object(auth_service.invite_repo, "mark_used", mark_used_mock),
        patch.object(auth_service.user_repo, "create_user", side_effect=fake_create),
    ):
        result = await auth_service.register(
            mock_pg_session, "newuser", "password123", invite_code="valid-code"
        )

    assert "access_token" in result
    mark_used_mock.assert_awaited_once()
    call_args = mark_used_mock.call_args
    assert call_args[0][1] is invite
    assert call_args[0][2] == new_user_id


@pytest.mark.asyncio
async def test_registration_fails_with_expired_invite(mock_pg_session):
    """Registration with an expired invite code raises ValidationError."""
    with (
        patch.object(auth_service.invite_repo, "has_any_user", AsyncMock(return_value=True)),
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.invite_repo, "get_valid_invite", AsyncMock(return_value=None)),
    ):
        with pytest.raises(ValidationError) as exc_info:
            await auth_service.register(
                mock_pg_session, "newuser", "password123", invite_code="expired-code"
            )
        assert "Invalid or expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_registration_fails_with_used_invite(mock_pg_session):
    """Registration with an already-used invite code raises ValidationError."""
    # get_valid_invite filters out used codes, so it returns None
    with (
        patch.object(auth_service.invite_repo, "has_any_user", AsyncMock(return_value=True)),
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.invite_repo, "get_valid_invite", AsyncMock(return_value=None)),
    ):
        with pytest.raises(ValidationError) as exc_info:
            await auth_service.register(
                mock_pg_session, "newuser", "password123", invite_code="used-code"
            )
        assert "Invalid or expired" in str(exc_info.value)


# --- Invite creation ---


@pytest.mark.asyncio
async def test_create_invite(mock_pg_session):
    """Authenticated user can create an invite code."""
    user_id = str(uuid.uuid4())

    async def fake_create_invite(session, code, created_by, expires_at):
        return FakeInvite(
            id=uuid.uuid4(),
            code=code,
            created_by=created_by,
            used_by=None,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_used=False,
        )

    with patch.object(
        auth_service.invite_repo, "create_invite", side_effect=fake_create_invite
    ):
        result = await auth_service.create_invite(mock_pg_session, user_id)

    assert "code" in result
    assert len(result["code"]) > 0
    assert "expires_at" in result


# --- Invite listing ---


@pytest.mark.asyncio
async def test_list_invites(mock_pg_session):
    """Authenticated user can list their invites."""
    user_id = uuid.uuid4()
    invites = [
        _make_invite(code="code-1", created_by=user_id),
        _make_invite(code="code-2", created_by=user_id, is_used=True),
    ]

    with patch.object(
        auth_service.invite_repo, "list_user_invites", AsyncMock(return_value=invites)
    ):
        result = await auth_service.list_invites(mock_pg_session, str(user_id))

    assert len(result) == 2
    assert result[0]["code"] == "code-1"
    assert result[0]["is_used"] is False
    assert result[1]["code"] == "code-2"
    assert result[1]["is_used"] is True
