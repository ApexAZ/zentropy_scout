"""Tests for migration 030: search_profiles table.

REQ-034 §4.2, §11: Verifies upgrade creates the search_profiles table with
correct columns (fit_searches/stretch_searches JSONB, persona_fingerprint
String(64), is_stale bool, generated_at/approved_at nullable timestamps,
created_at/updated_at timestamps), a UNIQUE constraint on persona_id, and
a FK to personas (CASCADE). Verifies downgrade drops the table cleanly.
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from tests.conftest import TEST_DATABASE_URL, TEST_DB_NAME

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("migrations")]

_REVISION = "030_search_profiles"
_DOWN_REVISION = "029_settlement_retry"
_TABLE = "search_profiles"

_EXPECTED_COLUMNS = [
    "id",
    "persona_id",
    "fit_searches",
    "stretch_searches",
    "persona_fingerprint",
    "is_stale",
    "generated_at",
    "approved_at",
    "created_at",
    "updated_at",
]


# ---------------------------------------------------------------------------
# Helpers (matching migration 029 pattern)
# ---------------------------------------------------------------------------


async def _reset_schema(conn: AsyncConnection) -> None:
    """Drop and recreate public schema with required extensions."""
    await conn.execute(text("DROP SCHEMA public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _patch_settings_for_test_db() -> str:
    """Patch settings.database_name so alembic migrates the test DB."""
    original = settings.database_name
    settings.database_name = TEST_DB_NAME
    return original


def _create_alembic_config() -> Config:
    """Create alembic Config without ini file."""
    cfg = Config()
    migrations_dir = str(Path(__file__).resolve().parents[2] / "migrations")
    cfg.set_main_option("script_location", migrations_dir)
    return cfg


async def _table_exists(session: AsyncSession, table: str) -> bool:
    """Check if a table exists in the public schema."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :table)"
        ),
        {"table": table},
    )
    return result.scalar()  # type: ignore[return-value]


async def _column_exists(session: AsyncSession, table: str, column: str) -> bool:
    """Check if a column exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column)"
        ),
        {"table": table, "column": column},
    )
    return result.scalar()  # type: ignore[return-value]


async def _column_type(session: AsyncSession, table: str, column: str) -> str | None:
    """Get the data type of a column."""
    result = await session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else None


async def _column_is_nullable(session: AsyncSession, table: str, column: str) -> bool:
    """Check if a column is nullable."""
    result = await session.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] == "YES" if row else False


async def _constraint_exists(
    session: AsyncSession, table: str, constraint_name: str
) -> bool:
    """Check if a named constraint exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = :table AND constraint_name = :constraint)"
        ),
        {"table": table, "constraint": constraint_name},
    )
    return result.scalar()  # type: ignore[return-value]


async def _column_default(session: AsyncSession, table: str, column: str) -> str | None:
    """Get the column_default for a column."""
    result = await session.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else None


async def _column_max_length(
    session: AsyncSession, table: str, column: str
) -> int | None:
    """Get the character_maximum_length for a varchar column."""
    result = await session.execute(
        text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else None


async def _fk_delete_rule(session: AsyncSession, table: str, column: str) -> str | None:
    """Get the delete_rule for a FK constraint on the given column."""
    result = await session.execute(
        text(
            "SELECT rc.delete_rule "
            "FROM information_schema.referential_constraints rc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON kcu.constraint_name = rc.constraint_name "
            "WHERE kcu.table_name = :table AND kcu.column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 030."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(
            __import__("alembic.command", fromlist=["upgrade"]).upgrade,
            alembic_cfg,
            _REVISION,
        )
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
    """Create session on migrated database (at 030 level)."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Schema tests (upgrade)
# =============================================================================


class TestUpgradeSchema:
    """Verify 030 upgrade creates the search_profiles table."""

    @pytest.mark.asyncio
    async def test_table_exists(self, migration_session: AsyncSession) -> None:
        """search_profiles table exists after upgrade."""
        assert await _table_exists(migration_session, _TABLE)

    @pytest.mark.asyncio
    async def test_all_expected_columns_exist(
        self, migration_session: AsyncSession
    ) -> None:
        """All 10 expected columns exist on search_profiles."""
        for col in _EXPECTED_COLUMNS:
            assert await _column_exists(migration_session, _TABLE, col), (
                f"Missing column: {col}"
            )

    @pytest.mark.asyncio
    async def test_id_is_uuid(self, migration_session: AsyncSession) -> None:
        """id column is uuid type."""
        col_type = await _column_type(migration_session, _TABLE, "id")
        assert col_type == "uuid"

    @pytest.mark.asyncio
    async def test_persona_id_is_uuid(self, migration_session: AsyncSession) -> None:
        """persona_id column is uuid type."""
        col_type = await _column_type(migration_session, _TABLE, "persona_id")
        assert col_type == "uuid"

    @pytest.mark.asyncio
    async def test_fit_searches_is_jsonb(self, migration_session: AsyncSession) -> None:
        """fit_searches column is jsonb type."""
        col_type = await _column_type(migration_session, _TABLE, "fit_searches")
        assert col_type == "jsonb"

    @pytest.mark.asyncio
    async def test_stretch_searches_is_jsonb(
        self, migration_session: AsyncSession
    ) -> None:
        """stretch_searches column is jsonb type."""
        col_type = await _column_type(migration_session, _TABLE, "stretch_searches")
        assert col_type == "jsonb"

    @pytest.mark.asyncio
    async def test_persona_fingerprint_is_varchar(
        self, migration_session: AsyncSession
    ) -> None:
        """persona_fingerprint column is character varying."""
        col_type = await _column_type(migration_session, _TABLE, "persona_fingerprint")
        assert col_type == "character varying"

    @pytest.mark.asyncio
    async def test_is_stale_is_boolean(self, migration_session: AsyncSession) -> None:
        """is_stale column is boolean type."""
        col_type = await _column_type(migration_session, _TABLE, "is_stale")
        assert col_type == "boolean"

    @pytest.mark.asyncio
    async def test_generated_at_is_timestamptz(
        self, migration_session: AsyncSession
    ) -> None:
        """generated_at column is timestamp with time zone."""
        col_type = await _column_type(migration_session, _TABLE, "generated_at")
        assert col_type == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_approved_at_is_timestamptz(
        self, migration_session: AsyncSession
    ) -> None:
        """approved_at column is timestamp with time zone."""
        col_type = await _column_type(migration_session, _TABLE, "approved_at")
        assert col_type == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_created_at_is_timestamptz(
        self, migration_session: AsyncSession
    ) -> None:
        """created_at column is timestamp with time zone."""
        col_type = await _column_type(migration_session, _TABLE, "created_at")
        assert col_type == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_updated_at_is_timestamptz(
        self, migration_session: AsyncSession
    ) -> None:
        """updated_at column is timestamp with time zone."""
        col_type = await _column_type(migration_session, _TABLE, "updated_at")
        assert col_type == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_generated_at_is_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """generated_at is nullable (profile exists before generation completes)."""
        assert await _column_is_nullable(migration_session, _TABLE, "generated_at")

    @pytest.mark.asyncio
    async def test_approved_at_is_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """approved_at is nullable (user has not yet approved)."""
        assert await _column_is_nullable(migration_session, _TABLE, "approved_at")

    @pytest.mark.asyncio
    async def test_is_stale_is_not_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """is_stale is NOT nullable."""
        assert not await _column_is_nullable(migration_session, _TABLE, "is_stale")

    @pytest.mark.asyncio
    async def test_is_stale_defaults_true(
        self, migration_session: AsyncSession
    ) -> None:
        """is_stale column default is true."""
        default = await _column_default(migration_session, _TABLE, "is_stale")
        assert default == "true"

    @pytest.mark.asyncio
    async def test_unique_constraint_on_persona_id(
        self, migration_session: AsyncSession
    ) -> None:
        """UNIQUE constraint exists on persona_id (one profile per persona)."""
        assert await _constraint_exists(
            migration_session, _TABLE, "uq_search_profiles_persona_id"
        )

    @pytest.mark.asyncio
    async def test_persona_id_fk_cascades_on_delete(
        self, migration_session: AsyncSession
    ) -> None:
        """persona_id FK uses ON DELETE CASCADE so profiles follow personas."""
        rule = await _fk_delete_rule(migration_session, _TABLE, "persona_id")
        assert rule == "CASCADE"

    @pytest.mark.asyncio
    async def test_persona_fingerprint_max_length_is_64(
        self, migration_session: AsyncSession
    ) -> None:
        """persona_fingerprint has max length 64 (exact SHA-256 hex digest size)."""
        length = await _column_max_length(
            migration_session, _TABLE, "persona_fingerprint"
        )
        assert length == 64

    @pytest.mark.asyncio
    async def test_jsonb_array_constraints_exist(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraints enforce JSONB array shape on fit/stretch columns."""
        for name in [
            "ck_search_profiles_fit_searches_array",
            "ck_search_profiles_stretch_searches_array",
        ]:
            assert await _constraint_exists(migration_session, _TABLE, name), (
                f"Missing JSONB array constraint: {name}"
            )


# =============================================================================
# Downgrade tests
# =============================================================================


_JSONB_CONSTRAINTS = [
    "ck_search_profiles_fit_searches_array",
    "ck_search_profiles_stretch_searches_array",
]


class TestDowngrade:
    """Verify 030 downgrade drops the search_profiles table."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 030, then downgrade to 029."""
        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            from alembic import command

            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
            await asyncio.to_thread(command.downgrade, alembic_cfg, _DOWN_REVISION)
        finally:
            settings.database_name = original_name

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            yield session
            await session.rollback()

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_table_dropped(self, downgraded_session: AsyncSession) -> None:
        """search_profiles table does not exist after downgrade."""
        assert not await _table_exists(downgraded_session, _TABLE)


# =============================================================================
# Roundtrip test
# =============================================================================


class TestRoundtrip:
    """Verify upgrade → downgrade → upgrade works cleanly."""

    @pytest.mark.asyncio
    async def test_upgrade_downgrade_upgrade(self) -> None:
        """Migration 030 can be applied, reverted, and reapplied."""
        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            from alembic import command

            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
            await asyncio.to_thread(command.downgrade, alembic_cfg, _DOWN_REVISION)
            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
        finally:
            settings.database_name = original_name

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            assert await _table_exists(session, _TABLE), (
                "search_profiles table missing after roundtrip"
            )
            for col in _EXPECTED_COLUMNS:
                assert await _column_exists(session, _TABLE, col), (
                    f"Column {col} missing after roundtrip"
                )

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
