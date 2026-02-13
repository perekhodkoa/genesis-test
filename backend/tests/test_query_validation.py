import pytest

from app.middleware.error_handler import AppError
from app.repositories.query_repo import execute_sql, execute_mongodb, _check_mongo_value


# --- SQL Validation ---


@pytest.mark.asyncio
async def test_select_allowed(mock_pg_session):
    """A plain SELECT query passes validation and reaches execution."""
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
async def test_keyword_in_string_literal_allowed(mock_pg_session):
    """Forbidden keywords inside string literals should NOT trigger rejection."""
    fake_result = type("FakeResult", (), {
        "keys": lambda self: ["name"],
        "fetchmany": lambda self, n: [],
    })()
    mock_pg_session.execute.return_value = fake_result

    rows = await execute_sql(
        mock_pg_session,
        "SELECT * FROM t WHERE name = 'DELETE this or DROP that'"
    )
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
async def test_stacked_queries_blocked():
    """Stacked queries (multiple statements) are rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT 1; DELETE FROM users")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_comment_hidden_keyword_blocked():
    """Keywords hidden in block comments around them still get caught after stripping."""
    # After comment stripping: "SELECT 1;  DROP TABLE x"
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT 1; /* hidden */ DROP TABLE x")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_line_comment_stacked_blocked():
    """Line comment followed by destructive statement is blocked."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT 1; --comment\nDROP TABLE x")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_select_into_blocked():
    """SELECT INTO (creates a new table) is blocked."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT * INTO new_table FROM users")
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


@pytest.mark.asyncio
async def test_copy_blocked():
    """COPY command is rejected."""
    with pytest.raises(AppError) as exc_info:
        await execute_sql(None, "SELECT 1; COPY users TO '/tmp/dump'")
    assert exc_info.value.status_code == 403


# --- MongoDB Validation ---


def test_mongo_function_top_level_blocked():
    """$function at top-level stage is blocked."""
    with pytest.raises(AppError):
        _check_mongo_value({"$function": {"body": "return 1"}})


def test_mongo_function_nested_blocked():
    """$function nested inside $addFields is blocked."""
    pipeline_stage = {
        "$addFields": {
            "computed": {
                "$function": {
                    "body": "function() { return 1; }",
                    "args": [],
                    "lang": "js",
                }
            }
        }
    }
    with pytest.raises(AppError):
        _check_mongo_value(pipeline_stage)


def test_mongo_accumulator_nested_blocked():
    """$accumulator nested inside $group is blocked."""
    pipeline_stage = {
        "$group": {
            "_id": None,
            "total": {
                "$accumulator": {
                    "init": "function() { return 0; }",
                    "accumulate": "function(state, val) { return state + val; }",
                    "merge": "function(a, b) { return a + b; }",
                    "lang": "js",
                }
            }
        }
    }
    with pytest.raises(AppError):
        _check_mongo_value(pipeline_stage)


def test_mongo_where_blocked():
    """$where operator is blocked."""
    with pytest.raises(AppError):
        _check_mongo_value({"$where": "this.x > 1"})


def test_mongo_out_blocked():
    """$out stage is blocked."""
    with pytest.raises(AppError):
        _check_mongo_value({"$out": "evil_collection"})


def test_mongo_merge_blocked():
    """$merge stage is blocked."""
    with pytest.raises(AppError):
        _check_mongo_value({"$merge": {"into": "target"}})


def test_mongo_safe_pipeline_passes():
    """A normal aggregation pipeline passes validation."""
    stages = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
    ]
    for stage in stages:
        _check_mongo_value(stage)  # Should not raise
