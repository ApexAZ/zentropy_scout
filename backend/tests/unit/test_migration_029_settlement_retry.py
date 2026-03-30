"""Tests for migration 029: Settlement retry response metadata columns.

REQ-030 §5.8: Verifies upgrade adds 4 nullable columns to
usage_reservations (response_model, response_input_tokens,
response_output_tokens, call_completed_at). Verifies downgrade
drops them cleanly.
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

_REVISION = "029_settlement_retry"
_DOWN_REVISION = "028_billing_hardening"
_RESERVATIONS_TABLE = "usage_reservations"

_NEW_COLUMNS = [
    "response_model",
    "response_input_tokens",
    "response_output_tokens",
    "call_completed_at",
]


# ---------------------------------------------------------------------------
# Helpers (matching migration 028 pattern)
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 029."""
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
    """Create session on migrated database (at 029 level)."""
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
    """Verify 029 upgrade adds 4 response metadata columns."""

    @pytest.mark.asyncio
    async def test_response_model_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """response_model column exists on usage_reservations."""
        assert await _column_exists(
            migration_session, _RESERVATIONS_TABLE, "response_model"
        )

    @pytest.mark.asyncio
    async def test_response_input_tokens_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """response_input_tokens column exists on usage_reservations."""
        assert await _column_exists(
            migration_session, _RESERVATIONS_TABLE, "response_input_tokens"
        )

    @pytest.mark.asyncio
    async def test_response_output_tokens_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """response_output_tokens column exists on usage_reservations."""
        assert await _column_exists(
            migration_session, _RESERVATIONS_TABLE, "response_output_tokens"
        )

    @pytest.mark.asyncio
    async def test_call_completed_at_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """call_completed_at column exists on usage_reservations."""
        assert await _column_exists(
            migration_session, _RESERVATIONS_TABLE, "call_completed_at"
        )

    @pytest.mark.asyncio
    async def test_response_model_is_varchar(
        self, migration_session: AsyncSession
    ) -> None:
        """response_model is character varying type."""
        col_type = await _column_type(
            migration_session, _RESERVATIONS_TABLE, "response_model"
        )
        assert col_type == "character varying"

    @pytest.mark.asyncio
    async def test_response_input_tokens_is_integer(
        self, migration_session: AsyncSession
    ) -> None:
        """response_input_tokens is integer type."""
        col_type = await _column_type(
            migration_session, _RESERVATIONS_TABLE, "response_input_tokens"
        )
        assert col_type == "integer"

    @pytest.mark.asyncio
    async def test_response_output_tokens_is_integer(
        self, migration_session: AsyncSession
    ) -> None:
        """response_output_tokens is integer type."""
        col_type = await _column_type(
            migration_session, _RESERVATIONS_TABLE, "response_output_tokens"
        )
        assert col_type == "integer"

    @pytest.mark.asyncio
    async def test_call_completed_at_is_timestamptz(
        self, migration_session: AsyncSession
    ) -> None:
        """call_completed_at is timestamp with time zone."""
        col_type = await _column_type(
            migration_session, _RESERVATIONS_TABLE, "call_completed_at"
        )
        assert col_type == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_all_new_columns_are_nullable(
        self, migration_session: AsyncSession
    ) -> None:
        """All 4 new columns must be nullable."""
        for col in _NEW_COLUMNS:
            assert await _column_is_nullable(
                migration_session, _RESERVATIONS_TABLE, col
            ), f"Column {col} should be nullable"

    @pytest.mark.asyncio
    async def test_check_constraints_exist(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraints for token non-negativity and metadata completeness exist."""
        for name in [
            "ck_reservation_resp_input_tokens_nonneg",
            "ck_reservation_resp_output_tokens_nonneg",
            "ck_reservation_response_metadata_complete",
        ]:
            assert await _constraint_exists(
                migration_session, _RESERVATIONS_TABLE, name
            ), f"Missing constraint: {name}"


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """Verify 029 downgrade drops all 4 new columns."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 029, then downgrade to 028."""
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
    async def test_all_new_columns_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """All 4 response metadata columns are removed after downgrade."""
        for col in _NEW_COLUMNS:
            assert not await _column_exists(
                downgraded_session, _RESERVATIONS_TABLE, col
            ), f"Column {col} should not exist after downgrade"

    @pytest.mark.asyncio
    async def test_all_new_constraints_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """All 3 new CHECK constraints are removed after downgrade."""
        for name in [
            "ck_reservation_resp_input_tokens_nonneg",
            "ck_reservation_resp_output_tokens_nonneg",
            "ck_reservation_response_metadata_complete",
        ]:
            assert not await _constraint_exists(
                downgraded_session, _RESERVATIONS_TABLE, name
            ), f"Constraint {name} should not exist after downgrade"


# =============================================================================
# Roundtrip test
# =============================================================================


class TestRoundtrip:
    """Verify upgrade → downgrade → upgrade works cleanly."""

    @pytest.mark.asyncio
    async def test_upgrade_downgrade_upgrade(self) -> None:
        """Migration 029 can be applied, reverted, and reapplied."""
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

        # Verify final state — all 4 columns exist
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            for col in _NEW_COLUMNS:
                assert await _column_exists(session, _RESERVATIONS_TABLE, col), (
                    f"Column {col} missing after roundtrip"
                )

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
