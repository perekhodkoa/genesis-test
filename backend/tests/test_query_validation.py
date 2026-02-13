import pytest

from app.middleware.error_handler import AppError
from app.repositories.query_repo import execute_sql


@pytest.mark.asyncio
async def test_select_allowed(mock_pg_session):
    """A plain SELECT query passes validation and reaches execution."""
    # Mock the session.execute to return a fake result
    fake_result = type("FakeResult", (), {
        "keys": lambda self: ["id", "name"],
        "fetchmany": lambda self, n: [(1, "alice"), (2, "bob")],
    })()
    mock_pg_session.execute.return_value = fake_result

    rows = await execute_sql(mock_pg_session, "SELECT id, name FROM users")
    assert len(rows) == 2
    assert rows[0] == {"id": 1, "name": "alice"}


@pytest.mark.asyncio
async def test_select_with_where(mock_pg_session):
    """SELECT with WHERE clause passes validation."""
    fake_result = type("FakeResult", (), {
        "keys": lambda self: ["id"],
        "fetchmany": lambda self, n: [],
    })()
    mock_pg_session.execute.return_value = fake_result

    rows = await execute_sql(mock_pg_session, "SELECT id FROM users WHERE name = 'test'")
    assert rows == []


@pytest.mark.asyncio
async def test_insert_blocked():
    """INSERT queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "INSERT INTO users (name) VALUES ('hacker')")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_drop_blocked():
    """DROP queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "DROP TABLE users")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_blocked():
    """DELETE queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "DELETE FROM users WHERE id = 1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_blocked():
    """UPDATE queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "UPDATE users SET name = 'hacker' WHERE id = 1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_truncate_blocked():
    """TRUNCATE queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "TRUNCATE TABLE users")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_select_with_embedded_drop_blocked():
    """SELECT that sneaks in DROP is still rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT * FROM users; DROP TABLE users;")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_alter_blocked():
    """ALTER queries are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "ALTER TABLE users ADD COLUMN evil TEXT")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_select_start_blocked():
    """Queries that don't start with SELECT are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "CREATE TABLE evil (id INT)")
    assert exc_info.value.status_code == 403
