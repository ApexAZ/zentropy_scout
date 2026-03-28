"""Tests for migration 028: Billing and metering hardening.

REQ-030 §4: Verifies upgrade adds held_balance_usd to users, creates
usage_reservations table with constraints/indexes, aligns grant_cents
type (BIGINT→INTEGER), and adds 'expired' to stripe_purchases status.
Verifies downgrade cleanly reverses all changes.
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

_REVISION = "028_billing_hardening"
_DOWN_REVISION = "027_stripe_payment_intent_index"

# Repeated identifiers (S1192 prevention)
_USERS = "users"
_HELD_BALANCE_COL = "held_balance_usd"
_RESERVATIONS_TABLE = "usage_reservations"
_STRIPE_PURCHASES = "stripe_purchases"
_FUNDING_PACKS = "funding_packs"
_GRANT_CENTS = "grant_cents"
_CK_STATUS_VALID = "ck_stripe_purchases_status_valid"
_CK_HELD_BALANCE = "ck_users_held_balance_nonneg"


# ---------------------------------------------------------------------------
# Helpers (matching migration 025 pattern)
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


async def _table_exists(session: AsyncSession, table: str) -> bool:
    """Check if a table exists."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table)"
        ),
        {"table": table},
    )
    return result.scalar()  # type: ignore[return-value]


async def _index_exists(session: AsyncSession, table: str, index_name: str) -> bool:
    """Check if a named index exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
            "WHERE tablename = :table AND indexname = :index)"
        ),
        {"table": table, "index": index_name},
    )
    return result.scalar()  # type: ignore[return-value]


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


async def _check_constraint_def(
    session: AsyncSession, constraint_name: str
) -> str | None:
    """Get the definition of a CHECK constraint."""
    result = await session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"
        ),
        {"name": constraint_name},
    )
    row = result.fetchone()
    return row[0] if row else None


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 028."""
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
    """Create session on migrated database (at 028 level)."""
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
    """Verify 028 upgrade creates expected schema changes."""

    # -- users.held_balance_usd (REQ-030 §4.1) --

    @pytest.mark.asyncio
    async def test_users_has_held_balance_usd(
        self, migration_session: AsyncSession
    ) -> None:
        """held_balance_usd column exists on users table."""
        assert await _column_exists(migration_session, _USERS, _HELD_BALANCE_COL)

    @pytest.mark.asyncio
    async def test_held_balance_check_constraint(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraint ck_users_held_balance_nonneg exists."""
        assert await _constraint_exists(migration_session, _USERS, _CK_HELD_BALANCE)

    @pytest.mark.asyncio
    async def test_held_balance_defaults_to_zero(
        self, migration_session: AsyncSession
    ) -> None:
        """held_balance_usd defaults to 0 for new rows."""
        await migration_session.execute(
            text(
                "INSERT INTO users (id, email, created_at, updated_at) "
                "VALUES (gen_random_uuid(), 'held-default@test.com', now(), now())"
            )
        )
        result = await migration_session.execute(
            text(
                "SELECT held_balance_usd FROM users "
                "WHERE email = 'held-default@test.com'"
            )
        )
        assert result.scalar() == 0

    # -- usage_reservations table (REQ-030 §4.2) --

    @pytest.mark.asyncio
    async def test_usage_reservations_table_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """usage_reservations table is created."""
        assert await _table_exists(migration_session, _RESERVATIONS_TABLE)

    @pytest.mark.asyncio
    async def test_reservation_check_constraints(
        self, migration_session: AsyncSession
    ) -> None:
        """All CHECK constraints on usage_reservations exist."""
        for name in [
            "ck_reservation_status_valid",
            "ck_reservation_estimated_positive",
            "ck_reservation_actual_nonneg",
        ]:
            assert await _constraint_exists(
                migration_session, _RESERVATIONS_TABLE, name
            ), f"Missing constraint: {name}"

    @pytest.mark.asyncio
    async def test_reservation_status_constraint_values(
        self, migration_session: AsyncSession
    ) -> None:
        """Status constraint includes held, settled, released, stale."""
        defn = await _check_constraint_def(
            migration_session, "ck_reservation_status_valid"
        )
        assert defn is not None
        for status in ("held", "settled", "released", "stale"):
            assert status in defn, f"Missing status '{status}' in constraint"

    @pytest.mark.asyncio
    async def test_reservation_user_status_index(
        self, migration_session: AsyncSession
    ) -> None:
        """Composite index on (user_id, status) exists."""
        assert await _index_exists(
            migration_session, _RESERVATIONS_TABLE, "ix_reservation_user_status"
        )

    @pytest.mark.asyncio
    async def test_reservation_stale_sweep_index(
        self, migration_session: AsyncSession
    ) -> None:
        """Partial index on created_at WHERE status='held' exists."""
        assert await _index_exists(
            migration_session, _RESERVATIONS_TABLE, "ix_reservation_stale_sweep"
        )

    # -- grant_cents type alignment (REQ-030 §4.3) --

    @pytest.mark.asyncio
    async def test_stripe_purchases_grant_cents_is_integer(
        self, migration_session: AsyncSession
    ) -> None:
        """grant_cents on stripe_purchases is INTEGER (not BIGINT)."""
        col_type = await _column_type(
            migration_session, _STRIPE_PURCHASES, _GRANT_CENTS
        )
        assert col_type == "integer"

    @pytest.mark.asyncio
    async def test_funding_packs_grant_cents_is_integer(
        self, migration_session: AsyncSession
    ) -> None:
        """grant_cents on funding_packs is INTEGER (not BIGINT)."""
        col_type = await _column_type(migration_session, _FUNDING_PACKS, _GRANT_CENTS)
        assert col_type == "integer"

    # -- stripe_purchases 'expired' status (REQ-030 §7.3) --

    @pytest.mark.asyncio
    async def test_status_constraint_includes_expired(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraint on stripe_purchases includes 'expired'."""
        defn = await _check_constraint_def(migration_session, _CK_STATUS_VALID)
        assert defn is not None
        assert "expired" in defn


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """Verify 028 downgrade reverses all changes cleanly."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 028, then downgrade to 027."""
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
    async def test_usage_reservations_table_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """usage_reservations table does not exist after downgrade."""
        assert not await _table_exists(downgraded_session, _RESERVATIONS_TABLE)

    @pytest.mark.asyncio
    async def test_held_balance_usd_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """held_balance_usd column removed from users."""
        assert not await _column_exists(downgraded_session, _USERS, _HELD_BALANCE_COL)

    @pytest.mark.asyncio
    async def test_held_balance_constraint_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """CHECK constraint ck_users_held_balance_nonneg removed."""
        assert not await _constraint_exists(
            downgraded_session, _USERS, _CK_HELD_BALANCE
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_grant_cents_restored_to_bigint(
        self, downgraded_session: AsyncSession
    ) -> None:
        """grant_cents reverted to BIGINT on stripe_purchases."""
        col_type = await _column_type(
            downgraded_session, _STRIPE_PURCHASES, _GRANT_CENTS
        )
        assert col_type == "bigint"

    @pytest.mark.asyncio
    async def test_funding_packs_grant_cents_restored_to_bigint(
        self, downgraded_session: AsyncSession
    ) -> None:
        """grant_cents reverted to BIGINT on funding_packs."""
        col_type = await _column_type(downgraded_session, _FUNDING_PACKS, _GRANT_CENTS)
        assert col_type == "bigint"

    @pytest.mark.asyncio
    async def test_status_constraint_excludes_expired(
        self, downgraded_session: AsyncSession
    ) -> None:
        """CHECK constraint restored without 'expired'."""
        defn = await _check_constraint_def(downgraded_session, _CK_STATUS_VALID)
        assert defn is not None
        assert "expired" not in defn


# =============================================================================
# Roundtrip test
# =============================================================================


class TestRoundtrip:
    """Verify upgrade → downgrade → upgrade works cleanly."""

    @pytest.mark.asyncio
    async def test_upgrade_downgrade_upgrade(self) -> None:
        """Migration can be applied, reverted, and reapplied."""
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

        # Verify final state
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            assert await _table_exists(session, _RESERVATIONS_TABLE)
            assert await _column_exists(session, _USERS, _HELD_BALANCE_COL)
            defn = await _check_constraint_def(session, _CK_STATUS_VALID)
            assert defn is not None
            assert "expired" in defn

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
