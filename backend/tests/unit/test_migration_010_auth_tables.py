"""Tests for migration 010: auth tables.

REQ-013 §6: Verifies that the auth schema migration correctly adds
columns to the users table and creates accounts, sessions, and
verification_tokens tables.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)

# Reusable SQL fragments
_INSERT_USER = text(
    "INSERT INTO users (id, email, created_at, updated_at) "
    "VALUES (:id, :email, now(), now())"
)
_INSERT_ACCOUNT = text(
    "INSERT INTO accounts (id, user_id, type, provider, provider_account_id, created_at) "
    "VALUES (:id, :user_id, 'oauth', 'google', :provider_account_id, now())"
)
_INSERT_SESSION = text(
    "INSERT INTO sessions (id, session_token, user_id, expires, created_at) "
    "VALUES (:id, :token, :user_id, now() + interval '7 days', now())"
)


# =============================================================================
# Helpers
# =============================================================================


async def _reset_schema(conn) -> None:
    """Drop and recreate public schema with required extensions."""
    await conn.execute(text("DROP SCHEMA public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _patch_settings_for_test_db() -> str:
    """Patch settings.database_name so alembic migrates the test DB.

    Returns:
        Original database_name to restore later.
    """
    original = settings.database_name
    settings.database_name = f"{original}_test"
    return original


def _create_alembic_config():
    """Create alembic Config without ini file.

    Avoids fileConfig() which disables existing loggers and breaks
    pytest's caplog fixture for tests running after migration tests.
    """
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    return cfg


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations for schema testing."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "010_auth_tables")
    finally:
        settings.database_name = original_name

    yield engine

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def migration_session(
    migration_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create session on migrated database."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Users table — new columns (REQ-013 §6.1)
# =============================================================================


class TestUsersTableExpansion:
    """Verify new columns added to users table."""

    @pytest.mark.asyncio
    async def test_name_column_exists(self, migration_session: AsyncSession):
        """Users table has nullable name VARCHAR(255) column."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable, character_maximum_length "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'name'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.name column does not exist"
        assert row[0] == "character varying"
        assert row[1] == "YES"
        assert row[2] == 255

    @pytest.mark.asyncio
    async def test_email_verified_column_exists(self, migration_session: AsyncSession):
        """Users table has nullable email_verified TIMESTAMPTZ column."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'email_verified'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.email_verified column does not exist"
        assert row[0] == "timestamp with time zone"
        assert row[1] == "YES"

    @pytest.mark.asyncio
    async def test_image_column_exists(self, migration_session: AsyncSession):
        """Users table has nullable image TEXT column."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'image'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.image column does not exist"
        assert row[0] == "text"
        assert row[1] == "YES"

    @pytest.mark.asyncio
    async def test_updated_at_column_exists(self, migration_session: AsyncSession):
        """Users table has non-null updated_at TIMESTAMPTZ with default now()."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'updated_at'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.updated_at column does not exist"
        assert row[0] == "timestamp with time zone"
        assert row[1] == "NO"
        assert "now()" in str(row[2])

    @pytest.mark.asyncio
    async def test_password_hash_column_exists(self, migration_session: AsyncSession):
        """Users table has nullable password_hash VARCHAR(255) column."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable, character_maximum_length "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'password_hash'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.password_hash column does not exist"
        assert row[0] == "character varying"
        assert row[1] == "YES"
        assert row[2] == 255

    @pytest.mark.asyncio
    async def test_token_invalidated_before_column_exists(
        self, migration_session: AsyncSession
    ):
        """Users table has nullable token_invalidated_before TIMESTAMPTZ."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'token_invalidated_before'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.token_invalidated_before column does not exist"
        assert row[0] == "timestamp with time zone"
        assert row[1] == "YES"

    @pytest.mark.asyncio
    async def test_nullable_columns_accept_null(self, migration_session: AsyncSession):
        """New auth columns accept NULL values for existing users."""
        user_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_USER, {"id": user_id, "email": "test@example.com"}
        )
        await migration_session.flush()

        result = await migration_session.execute(
            text(
                "SELECT name, password_hash, token_invalidated_before "
                "FROM users WHERE id = :id"
            ),
            {"id": user_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is None  # name
        assert row[1] is None  # password_hash
        assert row[2] is None  # token_invalidated_before


# =============================================================================
# Accounts table (REQ-013 §6.2)
# =============================================================================


class TestAccountsTable:
    """Verify accounts table creation and constraints."""

    @pytest.mark.asyncio
    async def test_accounts_table_exists(self, migration_session: AsyncSession):
        """Accounts table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'accounts')"
            )
        )
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_accounts_columns(self, migration_session: AsyncSession):
        """Accounts table has all required columns."""
        result = await migration_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'accounts' ORDER BY ordinal_position"
            )
        )
        columns = {row[0] for row in result.fetchall()}
        expected = {
            "id",
            "user_id",
            "type",
            "provider",
            "provider_account_id",
            "refresh_token",
            "access_token",
            "expires_at",
            "token_type",
            "scope",
            "id_token",
            "session_state",
            "created_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    @pytest.mark.asyncio
    async def test_accounts_user_id_fk_cascade(self, migration_session: AsyncSession):
        """Accounts.user_id has FK to users(id) with CASCADE delete."""
        result = await migration_session.execute(
            text(
                "SELECT rc.delete_rule "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "JOIN information_schema.referential_constraints rc "
                "  ON tc.constraint_name = rc.constraint_name "
                "WHERE tc.table_name = 'accounts' "
                "  AND kcu.column_name = 'user_id' "
                "  AND tc.constraint_type = 'FOREIGN KEY'"
            )
        )
        row = result.fetchone()
        assert row is not None, "accounts.user_id FK not found"
        assert row[0] == "CASCADE"

    @pytest.mark.asyncio
    async def test_accounts_unique_provider_constraint(
        self, migration_session: AsyncSession
    ):
        """Duplicate (provider, provider_account_id) raises IntegrityError."""
        user_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_USER, {"id": user_id, "email": "unique-test@example.com"}
        )
        await migration_session.execute(
            _INSERT_ACCOUNT,
            {"id": uuid.uuid4(), "user_id": user_id, "provider_account_id": "goog-123"},
        )

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_ACCOUNT,
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id,
                    "provider_account_id": "goog-123",
                },
            )

    @pytest.mark.asyncio
    async def test_accounts_user_id_index(self, migration_session: AsyncSession):
        """Index idx_accounts_user_id exists."""
        result = await migration_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'accounts' AND indexname = 'idx_accounts_user_id'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_accounts_cascade_delete(self, migration_session: AsyncSession):
        """Deleting a user cascades to delete their accounts."""
        user_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_USER, {"id": user_id, "email": "cascade-test@example.com"}
        )
        account_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_ACCOUNT,
            {"id": account_id, "user_id": user_id, "provider_account_id": "goog-456"},
        )
        await migration_session.flush()

        await migration_session.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": user_id}
        )
        await migration_session.flush()

        result = await migration_session.execute(
            text("SELECT id FROM accounts WHERE id = :id"), {"id": account_id}
        )
        assert result.fetchone() is None


# =============================================================================
# Sessions table (REQ-013 §6.3)
# =============================================================================


class TestSessionsTable:
    """Verify sessions table creation and constraints."""

    @pytest.mark.asyncio
    async def test_sessions_table_exists(self, migration_session: AsyncSession):
        """Sessions table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'sessions')"
            )
        )
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_sessions_columns(self, migration_session: AsyncSession):
        """Sessions table has all required columns."""
        result = await migration_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'sessions' ORDER BY ordinal_position"
            )
        )
        columns = {row[0] for row in result.fetchall()}
        expected = {"id", "session_token", "user_id", "expires", "created_at"}
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    @pytest.mark.asyncio
    async def test_sessions_token_unique(self, migration_session: AsyncSession):
        """Duplicate session_token raises IntegrityError."""
        user_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_USER, {"id": user_id, "email": "session-test@example.com"}
        )

        token = "unique-session-token-123"
        await migration_session.execute(
            _INSERT_SESSION, {"id": uuid.uuid4(), "token": token, "user_id": user_id}
        )

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_SESSION,
                {"id": uuid.uuid4(), "token": token, "user_id": user_id},
            )

    @pytest.mark.asyncio
    async def test_sessions_user_id_index(self, migration_session: AsyncSession):
        """Index idx_sessions_user_id exists."""
        result = await migration_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'sessions' AND indexname = 'idx_sessions_user_id'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_sessions_expires_index(self, migration_session: AsyncSession):
        """Index idx_sessions_expires exists for cleanup queries."""
        result = await migration_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'sessions' AND indexname = 'idx_sessions_expires'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_sessions_cascade_delete(self, migration_session: AsyncSession):
        """Deleting a user cascades to delete their sessions."""
        user_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_USER, {"id": user_id, "email": "session-cascade@example.com"}
        )
        session_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_SESSION,
            {"id": session_id, "token": "cascade-token", "user_id": user_id},
        )
        await migration_session.flush()

        await migration_session.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": user_id}
        )
        await migration_session.flush()

        result = await migration_session.execute(
            text("SELECT id FROM sessions WHERE id = :id"), {"id": session_id}
        )
        assert result.fetchone() is None


# =============================================================================
# Verification tokens table (REQ-013 §6.4)
# =============================================================================


class TestVerificationTokensTable:
    """Verify verification_tokens table creation and constraints."""

    @pytest.mark.asyncio
    async def test_verification_tokens_table_exists(
        self, migration_session: AsyncSession
    ):
        """Verification tokens table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'verification_tokens')"
            )
        )
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_verification_tokens_columns(self, migration_session: AsyncSession):
        """Verification tokens table has exactly (identifier, token, expires)."""
        result = await migration_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'verification_tokens' ORDER BY ordinal_position"
            )
        )
        columns = {row[0] for row in result.fetchall()}
        assert columns == {"identifier", "token", "expires"}

    @pytest.mark.asyncio
    async def test_verification_tokens_has_composite_pk(
        self, migration_session: AsyncSession
    ):
        """Composite PK on (identifier, token) exists."""
        result = await migration_session.execute(
            text(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "WHERE tc.table_name = 'verification_tokens' "
                "  AND tc.constraint_type = 'PRIMARY KEY' "
                "ORDER BY kcu.ordinal_position"
            )
        )
        pk_columns = [row[0] for row in result.fetchall()]
        assert pk_columns == ["identifier", "token"]

    @pytest.mark.asyncio
    async def test_verification_tokens_unique_constraint(
        self, migration_session: AsyncSession
    ):
        """Duplicate (identifier, token) raises IntegrityError."""
        await migration_session.execute(
            text(
                "INSERT INTO verification_tokens (identifier, token, expires) "
                "VALUES ('test@example.com', 'token-abc', now() + interval '10 minutes')"
            )
        )

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                text(
                    "INSERT INTO verification_tokens (identifier, token, expires) "
                    "VALUES ('test@example.com', 'token-abc', now() + interval '10 minutes')"
                )
            )

    @pytest.mark.asyncio
    async def test_verification_tokens_expires_index(
        self, migration_session: AsyncSession
    ):
        """Index idx_verification_tokens_expires exists for cleanup queries."""
        result = await migration_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'verification_tokens' "
                "AND indexname = 'idx_verification_tokens_expires'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_verification_tokens_insert_and_delete(
        self, migration_session: AsyncSession
    ):
        """Tokens can be inserted and deleted (single-use pattern)."""
        await migration_session.execute(
            text(
                "INSERT INTO verification_tokens (identifier, token, expires) "
                "VALUES ('magic@example.com', 'magic-token', now() + interval '10 minutes')"
            )
        )
        await migration_session.flush()

        result = await migration_session.execute(
            text(
                "DELETE FROM verification_tokens "
                "WHERE identifier = 'magic@example.com' AND token = 'magic-token' "
                "RETURNING identifier"
            )
        )
        assert result.fetchone() is not None


# =============================================================================
# Downgrade test
# =============================================================================


class TestMigrationDowngrade:
    """Verify migration 010 can be cleanly downgraded."""

    @pytest.mark.asyncio
    async def test_downgrade_removes_new_tables(self):
        """Downgrading 010 removes accounts, sessions, verification_tokens
        and restores users to original schema."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            await asyncio.to_thread(command.upgrade, alembic_cfg, "010_auth_tables")

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ('accounts', 'sessions', 'verification_tokens')"
                    )
                )
                tables_before = {row[0] for row in result.fetchall()}
                assert tables_before == {"accounts", "sessions", "verification_tokens"}

            await asyncio.to_thread(
                command.downgrade, alembic_cfg, "009_score_details_jsonb"
            )

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ('accounts', 'sessions', 'verification_tokens')"
                    )
                )
                assert {row[0] for row in result.fetchall()} == set()

                result = await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'users' AND column_name IN ("
                        "'name', 'email_verified', 'image', 'updated_at', "
                        "'password_hash', 'token_invalidated_before')"
                    )
                )
                assert {row[0] for row in result.fetchall()} == set()
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
