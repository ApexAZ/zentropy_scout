"""Tests for token metering ORM models and migration.

REQ-020 §4.1–§4.5: Verifies LLMUsageRecord, CreditTransaction models,
User.balance_usd column, migration 020 up/down, and all constraints.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.user import User

# Fixed test UUIDs
_MISSING_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

# Shared test constants
_PROVIDER = "claude"
_MODEL = "claude-3-5-haiku-20241022"
_TASK_TYPE = "extraction"
_INPUT_TOKENS = 100
_OUTPUT_TOKENS = 50
_RAW_COST = Decimal("0.001000")
_BILLED_COST = Decimal("0.001300")
_MARGIN = Decimal("1.30")

TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)


def _make_usage_record(user_id: uuid.UUID, **overrides: object) -> LLMUsageRecord:
    """Create LLMUsageRecord with sensible defaults for testing."""
    defaults: dict[str, object] = {
        "user_id": user_id,
        "provider": _PROVIDER,
        "model": _MODEL,
        "task_type": _TASK_TYPE,
        "input_tokens": _INPUT_TOKENS,
        "output_tokens": _OUTPUT_TOKENS,
        "raw_cost_usd": _RAW_COST,
        "billed_cost_usd": _BILLED_COST,
        "margin_multiplier": _MARGIN,
    }
    defaults.update(overrides)
    return LLMUsageRecord(**defaults)


# ---------------------------------------------------------------------------
# ORM Model Tests (use db_session fixture from conftest)
# ---------------------------------------------------------------------------


class TestLLMUsageRecord:
    """Test LLMUsageRecord ORM model."""

    @pytest.mark.asyncio
    async def test_create_with_valid_data(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Usage record inserts with all required fields."""
        record = _make_usage_record(
            test_user.id,
            input_tokens=500,
            output_tokens=200,
            raw_cost_usd=Decimal("0.001200"),
            billed_cost_usd=Decimal("0.001560"),
        )
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        assert record.id is not None
        assert record.user_id == test_user.id
        assert record.provider == _PROVIDER
        assert record.model == _MODEL
        assert record.task_type == _TASK_TYPE
        assert record.input_tokens == 500
        assert record.output_tokens == 200
        assert record.created_at is not None

    @pytest.mark.asyncio
    async def test_decimal_roundtrip(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Numeric(10,6) preserves Decimal precision through DB roundtrip."""
        raw = Decimal("0.003456")
        billed = Decimal("0.004493")

        record = _make_usage_record(
            test_user.id,
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            raw_cost_usd=raw,
            billed_cost_usd=billed,
        )
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        assert record.raw_cost_usd == raw
        assert record.billed_cost_usd == billed
        assert record.margin_multiplier == _MARGIN

    @pytest.mark.asyncio
    async def test_rejects_null_user_id(self, db_session: AsyncSession) -> None:
        """user_id NOT NULL constraint rejects None."""
        record = _make_usage_record(
            None,  # type: ignore[arg-type]
        )
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_null_provider(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """provider NOT NULL constraint rejects None."""
        record = _make_usage_record(test_user.id, provider=None)
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_null_model(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """model NOT NULL constraint rejects None."""
        record = _make_usage_record(test_user.id, model=None)
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_input_tokens(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative input_tokens."""
        record = _make_usage_record(test_user.id, input_tokens=-1)
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_output_tokens(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative output_tokens."""
        record = _make_usage_record(test_user.id, output_tokens=-1)
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_raw_cost(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative raw_cost_usd."""
        record = _make_usage_record(test_user.id, raw_cost_usd=Decimal("-0.001000"))
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_zero_margin(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects zero margin_multiplier."""
        record = _make_usage_record(test_user.id, margin_multiplier=Decimal("0.00"))
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_fk_cascade_on_user_delete(self, db_session: AsyncSession) -> None:
        """Usage records are deleted when parent user is deleted."""
        user = User(email="cascade-test-usage@example.com")
        db_session.add(user)
        await db_session.flush()

        record = _make_usage_record(user.id)
        db_session.add(record)
        await db_session.flush()
        record_id = record.id

        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            text("SELECT id FROM llm_usage_records WHERE id = :id"),
            {"id": record_id},
        )
        assert result.fetchone() is None

    @pytest.mark.asyncio
    async def test_fk_rejects_invalid_user_id(self, db_session: AsyncSession) -> None:
        """FK constraint rejects non-existent user_id."""
        record = _make_usage_record(_MISSING_USER_ID)
        db_session.add(record)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_default_created_at(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """created_at is set by server default on insert."""
        record = _make_usage_record(
            test_user.id,
            provider="gemini",
            model="gemini-2.0-flash",
            raw_cost_usd=Decimal("0.000060"),
            billed_cost_usd=Decimal("0.000078"),
        )
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        assert record.created_at is not None


class TestCreditTransaction:
    """Test CreditTransaction ORM model."""

    @pytest.mark.asyncio
    async def test_create_purchase_transaction(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Purchase credit transaction inserts with positive amount."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("15.000000"),
            transaction_type="purchase",
            reference_id="cs_test_stripe_session_123",
            description="Stripe purchase: Standard Pack",
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)

        assert txn.id is not None
        assert txn.amount_usd == Decimal("15.000000")
        assert txn.transaction_type == "purchase"
        assert txn.reference_id == "cs_test_stripe_session_123"
        assert txn.description == "Stripe purchase: Standard Pack"
        assert txn.created_at is not None

    @pytest.mark.asyncio
    async def test_create_usage_debit_transaction(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Usage debit transaction inserts with negative amount."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("-0.001560"),
            transaction_type="usage_debit",
            reference_id=str(uuid.uuid4()),
            description="LLM call: claude/claude-3-5-haiku-20241022",
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)

        assert txn.amount_usd == Decimal("-0.001560")
        assert txn.transaction_type == "usage_debit"

    @pytest.mark.asyncio
    async def test_nullable_reference_and_description(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """reference_id and description are nullable (e.g., admin grants)."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="admin_grant",
            reference_id=None,
            description=None,
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)

        assert txn.reference_id is None
        assert txn.description is None

    @pytest.mark.asyncio
    async def test_rejects_null_amount(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """amount_usd NOT NULL constraint rejects None."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=None,  # type: ignore[arg-type]
            transaction_type="purchase",
        )
        db_session.add(txn)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_null_transaction_type(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """transaction_type NOT NULL constraint rejects None."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("5.000000"),
            transaction_type=None,  # type: ignore[arg-type]
        )
        db_session.add(txn)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_invalid_transaction_type(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects invalid transaction_type values."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="free_money",
        )
        db_session.add(txn)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_decimal_roundtrip(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Numeric(10,6) preserves sub-cent precision for debit amounts."""
        amount = Decimal("-0.003315")
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=amount,
            transaction_type="usage_debit",
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)

        assert txn.amount_usd == amount

    @pytest.mark.asyncio
    async def test_fk_cascade_on_user_delete(self, db_session: AsyncSession) -> None:
        """Credit transactions are deleted when parent user is deleted."""
        user = User(email="cascade-test-credit@example.com")
        db_session.add(user)
        await db_session.flush()

        txn = CreditTransaction(
            user_id=user.id,
            amount_usd=Decimal("10.000000"),
            transaction_type="purchase",
        )
        db_session.add(txn)
        await db_session.flush()
        txn_id = txn.id

        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            text("SELECT id FROM credit_transactions WHERE id = :id"),
            {"id": txn_id},
        )
        assert result.fetchone() is None

    @pytest.mark.asyncio
    async def test_default_created_at(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """created_at is set by server default on insert."""
        txn = CreditTransaction(
            user_id=test_user.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="admin_grant",
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)

        assert txn.created_at is not None


class TestUserBalanceUsd:
    """Test User.balance_usd column."""

    @pytest.mark.asyncio
    async def test_default_balance_is_zero(self, db_session: AsyncSession) -> None:
        """New users have balance_usd = 0.000000 by default."""
        user = User(email="balance-default@example.com")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        assert user.balance_usd == Decimal("0.000000")

    @pytest.mark.asyncio
    async def test_balance_preserves_precision(self, db_session: AsyncSession) -> None:
        """Numeric(10,6) preserves 6-decimal-place balance values."""
        user = User(email="balance-precision@example.com")
        db_session.add(user)
        await db_session.flush()

        # Simulate atomic credit via raw SQL
        await db_session.execute(
            text("UPDATE users SET balance_usd = :balance WHERE id = :id"),
            {"balance": Decimal("15.123456"), "id": user.id},
        )
        await db_session.refresh(user)

        assert user.balance_usd == Decimal("15.123456")

    @pytest.mark.asyncio
    async def test_balance_not_nullable(self, db_session: AsyncSession) -> None:
        """balance_usd NOT NULL constraint rejects None via raw SQL."""
        user = User(email="balance-null@example.com")
        db_session.add(user)
        await db_session.flush()

        with pytest.raises(IntegrityError):
            await db_session.execute(
                text("UPDATE users SET balance_usd = NULL WHERE id = :id"),
                {"id": user.id},
            )


# ---------------------------------------------------------------------------
# Migration Upgrade / Downgrade Tests
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
    settings.database_name = f"{original}_test"
    return original


def _create_alembic_config() -> Config:
    """Create alembic Config without ini file."""
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    return cfg


class TestMigration020Upgrade:
    """Verify migration 020 creates metering tables and balance column."""

    @pytest_asyncio.fixture
    async def migration_engine(
        self,
    ) -> AsyncGenerator[AsyncEngine, None]:
        """Run alembic up to 020_token_metering."""
        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        from alembic import command

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            await asyncio.to_thread(command.upgrade, alembic_cfg, "020_token_metering")
        finally:
            settings.database_name = original_name

        yield engine

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()

    @pytest_asyncio.fixture
    async def migration_session(
        self, migration_engine: AsyncEngine
    ) -> AsyncGenerator[AsyncSession, None]:
        """Session on migrated database."""
        session_factory = async_sessionmaker(
            migration_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            yield session
            await session.rollback()

    @pytest.mark.asyncio
    async def test_llm_usage_records_table_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """llm_usage_records table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name = 'llm_usage_records'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_credit_transactions_table_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """credit_transactions table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name = 'credit_transactions'"
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_balance_usd_column_exists(
        self, migration_session: AsyncSession
    ) -> None:
        """users.balance_usd column is added with correct type and default."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable, numeric_precision, "
                "numeric_scale, column_default "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'balance_usd'"
            )
        )
        row = result.fetchone()
        assert row is not None, "users.balance_usd column does not exist"
        assert row[0] == "numeric"
        assert row[1] == "NO"  # NOT NULL
        assert row[2] == 10  # precision
        assert row[3] == 6  # scale
        assert "0.000000" in str(row[4])  # default

    @pytest.mark.asyncio
    async def test_indexes_created(self, migration_session: AsyncSession) -> None:
        """All 4 metering indexes are created."""
        result = await migration_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND indexname LIKE 'ix_%' "
                "AND (indexname LIKE '%usage%' OR indexname LIKE '%credit%')"
            )
        )
        index_names = {row[0] for row in result.fetchall()}
        expected = {
            "ix_llm_usage_records_user_created",
            "ix_llm_usage_records_user_task",
            "ix_credit_transactions_user_created",
            "ix_credit_transactions_user_type",
        }
        assert expected.issubset(index_names), (
            f"Missing indexes: {expected - index_names}"
        )

    @pytest.mark.asyncio
    async def test_check_constraints_created(
        self, migration_session: AsyncSession
    ) -> None:
        """All CHECK constraints are created on metering tables."""
        result = await migration_session.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE contype = 'c' "
                "AND conname LIKE 'ck_%'"
            )
        )
        constraint_names = {row[0] for row in result.fetchall()}
        expected = {
            "ck_usage_input_tokens_nonneg",
            "ck_usage_output_tokens_nonneg",
            "ck_usage_raw_cost_nonneg",
            "ck_usage_billed_cost_nonneg",
            "ck_usage_margin_positive",
            "ck_credit_txn_type_valid",
        }
        assert expected.issubset(constraint_names), (
            f"Missing constraints: {expected - constraint_names}"
        )


class TestMigration020Downgrade:
    """Verify migration 020 can be cleanly downgraded."""

    @pytest.mark.asyncio
    async def test_downgrade_removes_tables_and_column(self) -> None:
        """Downgrading 020 removes metering tables and balance_usd column."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            # Upgrade to 020
            await asyncio.to_thread(command.upgrade, alembic_cfg, "020_token_metering")

            # Verify tables exist
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN "
                        "('llm_usage_records', 'credit_transactions')"
                    )
                )
                tables = {row[0] for row in result.fetchall()}
                assert tables == {"llm_usage_records", "credit_transactions"}

            # Downgrade to 019
            await asyncio.to_thread(
                command.downgrade,
                alembic_cfg,
                "019_race_condition_indexes",
            )

            # Verify tables removed
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN "
                        "('llm_usage_records', 'credit_transactions')"
                    )
                )
                assert {row[0] for row in result.fetchall()} == set()

                # Verify balance_usd column removed
                result = await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'users' "
                        "AND column_name = 'balance_usd'"
                    )
                )
                assert result.fetchone() is None
        finally:
            settings.database_name = original_name
            async with engine.begin() as conn:
                await _reset_schema(conn)
            await engine.dispose()
