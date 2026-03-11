"""Tests for migration 025: Stripe checkout schema + signup grant.

REQ-029 §4.6: Verifies upgrade adds stripe_customer_id to users,
stripe_event_id to credit_transactions, creates stripe_purchases table
with indexes/constraints, updates CHECK constraint for signup_grant type,
and backfills signup grant transactions for existing users. Verifies
downgrade cleanly reverses all changes.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
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

_REVISION = "025_stripe_checkout"
_DOWN_REVISION = "024_gemini_embedding_dimensions"

# SQL fragments (module-level constants, matching migration 014 pattern)
_INSERT_USER = text(
    "INSERT INTO users (id, email, created_at, updated_at) "
    "VALUES (:id, :email, now(), now())"
)
_SIGNUP_GRANT_CONFIG_QUERY = text(
    "SELECT value FROM system_config WHERE key = 'signup_grant_cents'"
)


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 025."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
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
    """Create session on migrated database (at 025 level)."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_engine():
    """Upgrade to 024, seed test users, then upgrade to 025.

    Creates 2 users (to verify signup grant data migration).
    Verifies the data migration inserts signup_grant transactions.
    """
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    try:
        # Migrate to 024 (pre-025 state)
        await asyncio.to_thread(command.upgrade, alembic_cfg, _DOWN_REVISION)

        # Insert test users at 024 schema level
        async with engine.begin() as conn:
            await conn.execute(
                _INSERT_USER,
                {"id": user1_id, "email": "user1@example.com"},
            )
            await conn.execute(
                _INSERT_USER,
                {"id": user2_id, "email": "user2@example.com"},
            )

        # Upgrade to 025 (triggers data migration)
        await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
    finally:
        settings.database_name = original_name

    yield engine, user1_id, user2_id

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(
    seeded_engine,
) -> AsyncGenerator[tuple[AsyncSession, uuid.UUID, uuid.UUID], None]:
    """Create session on seeded database with user IDs."""
    engine, user1_id, user2_id = seeded_engine
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session, user1_id, user2_id
        await session.rollback()


# =============================================================================
# Schema tests (upgrade)
# =============================================================================


class TestUpgradeSchema:
    """Verify 025 upgrade creates expected schema changes."""

    @pytest.mark.asyncio
    async def test_users_has_stripe_customer_id(
        self, migration_session: AsyncSession
    ) -> None:
        """stripe_customer_id column exists on users table."""
        assert await _column_exists(migration_session, "users", "stripe_customer_id")

    @pytest.mark.asyncio
    async def test_credit_transactions_has_stripe_event_id(
        self, migration_session: AsyncSession
    ) -> None:
        """stripe_event_id column exists on credit_transactions table."""
        assert await _column_exists(
            migration_session, "credit_transactions", "stripe_event_id"
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_table_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """stripe_purchases table is created."""
        assert await _table_exists(migration_session, "stripe_purchases")

    @pytest.mark.asyncio
    async def test_stripe_purchases_user_id_index(
        self, migration_session: AsyncSession
    ) -> None:
        """Index on stripe_purchases.user_id exists."""
        assert await _index_exists(
            migration_session,
            "stripe_purchases",
            "ix_stripe_purchases_user_id",
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_customer_id_index(
        self, migration_session: AsyncSession
    ) -> None:
        """Index on stripe_purchases.stripe_customer_id exists."""
        assert await _index_exists(
            migration_session,
            "stripe_purchases",
            "ix_stripe_purchases_customer_id",
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_status_partial_index(
        self, migration_session: AsyncSession
    ) -> None:
        """Partial index on stripe_purchases.status WHERE pending exists."""
        assert await _index_exists(
            migration_session,
            "stripe_purchases",
            "ix_stripe_purchases_status_pending",
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_session_id_unique(
        self, migration_session: AsyncSession
    ) -> None:
        """UNIQUE constraint on stripe_session_id exists."""
        assert await _constraint_exists(
            migration_session,
            "stripe_purchases",
            "uq_stripe_purchases_session_id",
        )

    @pytest.mark.asyncio
    async def test_stripe_purchases_check_constraints(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraints on stripe_purchases exist."""
        for name in [
            "ck_stripe_purchases_amount_positive",
            "ck_stripe_purchases_grant_positive",
            "ck_stripe_purchases_refund_nonneg",
            "ck_stripe_purchases_status_valid",
        ]:
            assert await _constraint_exists(
                migration_session, "stripe_purchases", name
            ), f"Missing constraint: {name}"

    @pytest.mark.asyncio
    async def test_check_constraint_includes_signup_grant(
        self, migration_session: AsyncSession
    ) -> None:
        """CHECK constraint on credit_transactions includes signup_grant."""
        defn = await _check_constraint_def(
            migration_session, "ck_credit_txn_type_valid"
        )
        assert defn is not None
        assert "signup_grant" in defn

    @pytest.mark.asyncio
    async def test_users_stripe_customer_id_unique(
        self, migration_session: AsyncSession
    ) -> None:
        """UNIQUE constraint on users.stripe_customer_id exists."""
        assert await _constraint_exists(
            migration_session, "users", "uq_users_stripe_customer_id"
        )

    @pytest.mark.asyncio
    async def test_credit_txn_stripe_event_id_unique(
        self, migration_session: AsyncSession
    ) -> None:
        """UNIQUE constraint on credit_transactions.stripe_event_id exists."""
        assert await _constraint_exists(
            migration_session,
            "credit_transactions",
            "uq_credit_txn_stripe_event_id",
        )


# =============================================================================
# Data migration tests (signup grant)
# =============================================================================


class TestSignupGrantDataMigration:
    """Verify signup grant transactions are created for existing users."""

    @pytest.mark.asyncio
    async def test_signup_grant_transactions_created(
        self, seeded_session: tuple[AsyncSession, uuid.UUID, uuid.UUID]
    ) -> None:
        """Each existing user gets a signup_grant transaction."""
        session, user1_id, user2_id = seeded_session
        result = await session.execute(
            text(
                "SELECT user_id FROM credit_transactions "
                "WHERE transaction_type = 'signup_grant' "
                "ORDER BY user_id"
            )
        )
        user_ids = {row[0] for row in result.fetchall()}
        assert user1_id in user_ids
        assert user2_id in user_ids

    @pytest.mark.asyncio
    async def test_signup_grant_amount_matches_config(
        self, seeded_session: tuple[AsyncSession, uuid.UUID, uuid.UUID]
    ) -> None:
        """Signup grant amount matches system_config signup_grant_cents."""
        session, user1_id, _ = seeded_session

        # Read the configured grant
        config_result = await session.execute(_SIGNUP_GRANT_CONFIG_QUERY)
        config_row = config_result.fetchone()
        expected_usd = (
            Decimal(config_row[0]) / Decimal(100) if config_row else Decimal(0)
        )

        # Read the granted amount
        txn_result = await session.execute(
            text(
                "SELECT amount_usd FROM credit_transactions "
                "WHERE user_id = :uid AND transaction_type = 'signup_grant'"
            ),
            {"uid": user1_id},
        )
        actual_usd = txn_result.scalar()
        assert actual_usd == expected_usd

    @pytest.mark.asyncio
    async def test_user_balance_credited(
        self, seeded_session: tuple[AsyncSession, uuid.UUID, uuid.UUID]
    ) -> None:
        """User balance_usd is incremented by the signup grant."""
        session, user1_id, _ = seeded_session

        config_result = await session.execute(_SIGNUP_GRANT_CONFIG_QUERY)
        config_row = config_result.fetchone()
        expected_usd = (
            Decimal(config_row[0]) / Decimal(100) if config_row else Decimal(0)
        )

        result = await session.execute(
            text("SELECT balance_usd FROM users WHERE id = :uid"),
            {"uid": user1_id},
        )
        balance = result.scalar()
        assert balance == expected_usd

    @pytest.mark.asyncio
    async def test_signup_grant_description(
        self, seeded_session: tuple[AsyncSession, uuid.UUID, uuid.UUID]
    ) -> None:
        """Signup grant has the expected description."""
        session, user1_id, _ = seeded_session
        result = await session.execute(
            text(
                "SELECT description FROM credit_transactions "
                "WHERE user_id = :uid AND transaction_type = 'signup_grant'"
            ),
            {"uid": user1_id},
        )
        desc = result.scalar()
        assert desc == "Welcome bonus — free starter balance"


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """Verify 025 downgrade reverses all changes cleanly."""

    @pytest_asyncio.fixture
    async def downgraded_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Upgrade to 025, seed data, then downgrade to 024."""
        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        from alembic import command

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            # Upgrade to 025
            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
            # Downgrade to 024
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
    async def test_stripe_purchases_table_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """stripe_purchases table does not exist after downgrade."""
        assert not await _table_exists(downgraded_session, "stripe_purchases")

    @pytest.mark.asyncio
    async def test_stripe_customer_id_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """stripe_customer_id column removed from users."""
        assert not await _column_exists(
            downgraded_session, "users", "stripe_customer_id"
        )

    @pytest.mark.asyncio
    async def test_stripe_event_id_dropped(
        self, downgraded_session: AsyncSession
    ) -> None:
        """stripe_event_id column removed from credit_transactions."""
        assert not await _column_exists(
            downgraded_session, "credit_transactions", "stripe_event_id"
        )

    @pytest.mark.asyncio
    async def test_check_constraint_excludes_signup_grant(
        self, downgraded_session: AsyncSession
    ) -> None:
        """CHECK constraint restored without signup_grant."""
        defn = await _check_constraint_def(
            downgraded_session, "ck_credit_txn_type_valid"
        )
        assert defn is not None
        assert "signup_grant" not in defn

    @pytest.mark.asyncio
    async def test_signup_grant_transactions_deleted(
        self, downgraded_session: AsyncSession
    ) -> None:
        """signup_grant transactions are removed on downgrade."""
        result = await downgraded_session.execute(
            text(
                "SELECT COUNT(*) FROM credit_transactions "
                "WHERE transaction_type = 'signup_grant'"
            )
        )
        count = result.scalar()
        assert count == 0


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

        from alembic import command

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            # Upgrade → Downgrade → Upgrade
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
            assert await _table_exists(session, "stripe_purchases")
            assert await _column_exists(session, "users", "stripe_customer_id")
            assert await _column_exists(
                session, "credit_transactions", "stripe_event_id"
            )

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
