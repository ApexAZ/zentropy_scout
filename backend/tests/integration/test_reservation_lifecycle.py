"""Integration tests for reservation lifecycle — core pipeline.

REQ-030 §15.2: End-to-end tests verifying the full reservation pipeline —
reserve→settle happy path, reserve→release on failure. Uses real PostgreSQL
database with savepoint isolation.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.usage_reservation import UsageReservation
from app.providers.errors import ProviderError
from app.providers.llm.base import TaskType
from tests.integration._reservation_helpers import (
    BALANCE_QUERY,
    INITIAL_BALANCE,
    MARGIN,
    MODEL,
    PROVIDER,
    ZERO,
    make_metered_provider,
    mock_inner_adapter,
    seed_all,
)

_TEST_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000080")


# ===========================================================================
# Reserve → Settle (Happy Path)
# ===========================================================================


@pytest.mark.asyncio
class TestReserveSettleHappyPath:
    """REQ-030 §15.2: Reserve → complete → settle → balance correct."""

    async def test_settle_produces_correct_reservation_and_balance(
        self, db_session: AsyncSession
    ) -> None:
        """Full reserve→call→settle pipeline: reservation settled, balance debited."""
        user = await seed_all(db_session, _TEST_USER_ID)
        provider, _ = make_metered_provider(db_session, user.id)

        response = await provider.complete([], TaskType.EXTRACTION)
        await db_session.flush()

        assert response.content == "Test response"

        # Reservation is settled with actual cost
        res_result = await db_session.execute(
            select(UsageReservation).where(UsageReservation.user_id == user.id)
        )
        reservation = res_result.scalar_one()
        assert reservation.status == "settled"
        assert reservation.actual_cost_usd is not None
        assert reservation.settled_at is not None

        # Balance decreased, hold fully released
        bal = await db_session.execute(text(BALANCE_QUERY), {"uid": user.id})
        row = bal.one()
        assert row.balance_usd < INITIAL_BALANCE
        assert row.held_balance_usd == ZERO

    async def test_settle_creates_usage_record_and_transaction(
        self, db_session: AsyncSession
    ) -> None:
        """Settlement creates LLMUsageRecord and debit CreditTransaction."""
        user = await seed_all(db_session, _TEST_USER_ID)
        provider, _ = make_metered_provider(db_session, user.id)

        await provider.complete([], TaskType.EXTRACTION)
        await db_session.flush()

        # Usage record with correct tokens
        usage_result = await db_session.execute(
            select(LLMUsageRecord).where(LLMUsageRecord.user_id == user.id)
        )
        usage = usage_result.scalar_one()
        assert usage.provider == PROVIDER
        assert usage.model == MODEL
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.margin_multiplier == MARGIN

        # Debit transaction
        txn_result = await db_session.execute(
            select(CreditTransaction).where(CreditTransaction.user_id == user.id)
        )
        txn = txn_result.scalar_one()
        assert txn.transaction_type == "usage_debit"
        assert txn.amount_usd < 0


# ===========================================================================
# Reserve → Release (Failure Path)
# ===========================================================================


@pytest.mark.asyncio
class TestReserveReleaseOnFailure:
    """REQ-030 §15.2: Reserve → provider error → release → balance restored."""

    async def test_provider_error_releases_hold_and_restores_balance(
        self, db_session: AsyncSession
    ) -> None:
        """When inner adapter raises, hold is released and balance is unchanged."""
        user = await seed_all(db_session, _TEST_USER_ID)
        inner = mock_inner_adapter()
        inner.complete.side_effect = ProviderError("LLM service unavailable")
        provider, _ = make_metered_provider(db_session, user.id, inner)

        with pytest.raises(ProviderError):
            await provider.complete([], TaskType.EXTRACTION)

        await db_session.flush()

        # Reservation is released (not settled)
        res_result = await db_session.execute(
            select(UsageReservation).where(UsageReservation.user_id == user.id)
        )
        reservation = res_result.scalar_one()
        assert reservation.status == "released"
        assert reservation.actual_cost_usd is None

        # Balance unchanged — hold released, no debit occurred
        bal = await db_session.execute(text(BALANCE_QUERY), {"uid": user.id})
        row = bal.one()
        assert row.balance_usd == INITIAL_BALANCE
        assert row.held_balance_usd == ZERO

        # No usage record or transaction created
        usage_count = await db_session.execute(
            text("SELECT COUNT(*) FROM llm_usage_records WHERE user_id = :uid"),
            {"uid": user.id},
        )
        assert usage_count.scalar_one() == 0
