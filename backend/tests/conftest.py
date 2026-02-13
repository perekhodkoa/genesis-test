import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest


@dataclass
class FakeUser:
    id: uuid.UUID
    username: str
    password_hash: str


@pytest.fixture
def fake_user():
    """A pre-built fake user for auth tests."""
    from app.middleware.auth import hash_password

    return FakeUser(
        id=uuid.uuid4(),
        username="testuser",
        password_hash=hash_password("correct-password"),
    )


@pytest.fixture
def mock_pg_session():
    """A mock AsyncSession that does nothing on commit/refresh."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = lambda obj: None
    return session
