import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.middleware.auth import hash_password
from app.middleware.error_handler import AppError, AuthenticationError
from app.services import auth_service


@pytest.mark.asyncio
async def test_register_success(mock_pg_session):
    """Registering a new user returns a token."""
    new_user_id = uuid.uuid4()

    async def fake_create(session, username, pw_hash):
        from tests.conftest import FakeUser
        return FakeUser(id=new_user_id, username=username, password_hash=pw_hash)

    with (
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.user_repo, "create_user", side_effect=fake_create),
    ):
        result = await auth_service.register(mock_pg_session, "NewUser", "s3cret")

    assert "access_token" in result
    assert result["token_type"] == "bearer"
    assert len(result["access_token"]) > 0


@pytest.mark.asyncio
async def test_register_lowercases_username(mock_pg_session):
    """Username is lowercased before storage."""
    captured = {}

    async def fake_create(session, username, pw_hash):
        captured["username"] = username
        from tests.conftest import FakeUser
        return FakeUser(id=uuid.uuid4(), username=username, password_hash=pw_hash)

    with (
        patch.object(auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)),
        patch.object(auth_service.user_repo, "create_user", side_effect=fake_create),
    ):
        await auth_service.register(mock_pg_session, "MixedCase", "pw")

    assert captured["username"] == "mixedcase"


@pytest.mark.asyncio
async def test_register_duplicate_username(mock_pg_session, fake_user):
    """Registering an existing username raises 409."""
    with patch.object(
        auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=fake_user)
    ):
        with pytest.raises(AppError) as exc_info:
            await auth_service.register(mock_pg_session, "testuser", "pw")
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_success(mock_pg_session, fake_user):
    """Login with correct credentials returns a token."""
    with patch.object(
        auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=fake_user)
    ):
        result = await auth_service.login(mock_pg_session, "TestUser", "correct-password")

    assert "access_token" in result
    assert result["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(mock_pg_session, fake_user):
    """Login with wrong password raises AuthenticationError."""
    with patch.object(
        auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=fake_user)
    ):
        with pytest.raises(AuthenticationError):
            await auth_service.login(mock_pg_session, "testuser", "wrong-password")


@pytest.mark.asyncio
async def test_login_unknown_user(mock_pg_session):
    """Login with non-existent username raises AuthenticationError."""
    with patch.object(
        auth_service.user_repo, "get_user_by_username", AsyncMock(return_value=None)
    ):
        with pytest.raises(AuthenticationError):
            await auth_service.login(mock_pg_session, "nobody", "pw")
