"""Tests for migration 032: search_profile_generation task routing seed data.

REQ-034 §4.3, §11: Verifies upgrade inserts three task_routing_config rows
(one per provider) for 'search_profile_generation' using the same cost tier
as 'extraction'. Verifies downgrade removes those rows.
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

_REVISION = "032_search_profile_routing"
_DOWN_REVISION = "031_search_bucket_cursors"
_TASK_TYPE = "search_profile_generation"

# Same cost tier as EXTRACTION — REQ-034 §4.3
_EXPECTED_ROUTING = {
    "claude": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


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


async def _routing_rows(session: AsyncSession, task_type: str) -> dict[str, str]:
    """Return {provider: model} for all rows with the given task_type."""
    result = await session.execute(
        text(
            "SELECT provider, model FROM task_routing_config "
            "WHERE task_type = :task_type"
        ),
        {"task_type": task_type},
    )
    return {row[0]: row[1] for row in result.fetchall()}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 032."""
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
    """Create session on migrated database (at 032 level)."""
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


class TestUpgradeSeedData:
    """Verify 032 upgrade inserts routing rows for search_profile_generation."""

    @pytest.mark.asyncio
    async def test_three_routing_rows_inserted(
        self, migration_session: AsyncSession
    ) -> None:
        """Upgrade inserts one routing row per provider (claude, openai, gemini)."""
        rows = await _routing_rows(migration_session, _TASK_TYPE)
        assert set(rows.keys()) == {"claude", "openai", "gemini"}

    @pytest.mark.asyncio
    async def test_claude_routes_to_haiku(
        self, migration_session: AsyncSession
    ) -> None:
        """Claude provider routes search_profile_generation to Haiku — same tier as extraction."""
        rows = await _routing_rows(migration_session, _TASK_TYPE)
        assert rows["claude"] == _EXPECTED_ROUTING["claude"]

    @pytest.mark.asyncio
    async def test_openai_routes_to_gpt4o_mini(
        self, migration_session: AsyncSession
    ) -> None:
        """OpenAI provider routes search_profile_generation to GPT-4o Mini — same tier as extraction."""
        rows = await _routing_rows(migration_session, _TASK_TYPE)
        assert rows["openai"] == _EXPECTED_ROUTING["openai"]

    @pytest.mark.asyncio
    async def test_gemini_routes_to_flash(
        self, migration_session: AsyncSession
    ) -> None:
        """Gemini provider routes search_profile_generation to Gemini 2.0 Flash — same tier as extraction."""
        rows = await _routing_rows(migration_session, _TASK_TYPE)
        assert rows["gemini"] == _EXPECTED_ROUTING["gemini"]


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """Verify 032 downgrade removes the seeded routing rows."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 032, then downgrade to 031."""
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
    async def test_routing_rows_removed_after_downgrade(
        self, downgraded_session: AsyncSession
    ) -> None:
        """Downgrade removes all search_profile_generation routing rows."""
        rows = await _routing_rows(downgraded_session, _TASK_TYPE)
        assert rows == {}


# =============================================================================
# Roundtrip test
# =============================================================================


class TestRoundtrip:
    """Verify upgrade → downgrade → upgrade works cleanly."""

    @pytest.mark.asyncio
    async def test_upgrade_downgrade_upgrade(self) -> None:
        """Migration 032 can be applied, reverted, and reapplied."""
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
            rows = await _routing_rows(session, _TASK_TYPE)
            assert set(rows.keys()) == {"claude", "openai", "gemini"}, (
                "routing rows missing after roundtrip"
            )

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
