"""Tests for migration 031: search_bucket + last_seen_external_ids columns.

REQ-034 §6.1, §5.4, §11: Verifies upgrade adds search_bucket (nullable VARCHAR
with CHECK constraint) to persona_jobs and last_seen_external_ids (NOT NULL JSONB
defaulting to '{}') to polling_configurations. Verifies downgrade removes both.
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

_REVISION = "031_search_bucket_cursors"
_DOWN_REVISION = "030_search_profiles"
_PERSONA_JOBS = "persona_jobs"
_POLLING_CFG = "polling_configurations"


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 031."""
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
    """Create session on migrated database (at 031 level)."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Upgrade tests
# =============================================================================


class TestUpgradeSchema:
    """Verify 031 upgrade adds expected columns to existing tables."""

    @pytest.mark.asyncio
    async def test_search_bucket_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """search_bucket column exists on persona_jobs after upgrade."""
        assert await _column_exists(migration_session, _PERSONA_JOBS, "search_bucket")

    @pytest.mark.asyncio
    async def test_search_bucket_is_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """search_bucket is nullable — existing rows have no bucket (NULL = pre-buckets)."""
        assert await _column_is_nullable(
            migration_session, _PERSONA_JOBS, "search_bucket"
        )

    @pytest.mark.asyncio
    async def test_search_bucket_check_constraint_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraint restricts search_bucket to valid enum values."""
        assert await _constraint_exists(
            migration_session, _PERSONA_JOBS, "ck_persona_jobs_search_bucket"
        )

    @pytest.mark.asyncio
    async def test_last_seen_external_ids_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """last_seen_external_ids column exists on polling_configurations after upgrade."""
        assert await _column_exists(
            migration_session, _POLLING_CFG, "last_seen_external_ids"
        )

    @pytest.mark.asyncio
    async def test_last_seen_external_ids_is_not_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """last_seen_external_ids is NOT nullable — always has a cursor map (even if empty)."""
        assert not await _column_is_nullable(
            migration_session, _POLLING_CFG, "last_seen_external_ids"
        )

    @pytest.mark.asyncio
    async def test_last_seen_external_ids_defaults_to_empty_object(
        self, migration_session: AsyncSession
    ) -> None:
        """Default is empty JSONB object — means no prior cursors, start fresh on first poll."""
        default = await _column_default(
            migration_session, _POLLING_CFG, "last_seen_external_ids"
        )
        assert default is not None
        assert "'{}'" in default  # server default is '{}'::jsonb


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """Verify 031 downgrade removes both added columns."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 031, then downgrade to 030."""
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
    async def test_search_bucket_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """search_bucket column removed after downgrade."""
        assert not await _column_exists(
            downgraded_session, _PERSONA_JOBS, "search_bucket"
        )

    @pytest.mark.asyncio
    async def test_last_seen_external_ids_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """last_seen_external_ids column removed after downgrade."""
        assert not await _column_exists(
            downgraded_session, _POLLING_CFG, "last_seen_external_ids"
        )


# =============================================================================
# Roundtrip test
# =============================================================================


class TestRoundtrip:
    """Verify upgrade → downgrade → upgrade works cleanly."""

    @pytest.mark.asyncio
    async def test_upgrade_downgrade_upgrade(self) -> None:
        """Migration 031 can be applied, reverted, and reapplied."""
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
            assert await _column_exists(session, _PERSONA_JOBS, "search_bucket"), (
                "search_bucket missing after roundtrip"
            )
            assert await _column_exists(
                session, _POLLING_CFG, "last_seen_external_ids"
            ), "last_seen_external_ids missing after roundtrip"

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
