"""Integration tests for reservation advanced scenarios.

REQ-030 §15.2: Concurrent reservations, stale reservation sweep, and
ledger integrity after full reservation cycle. Uses real PostgreSQL
database with savepoint isolation.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction
from app.providers.errors import ProviderError
from app.providers.llm.base import TaskType
from app.services.reservation_sweep import sweep_stale_reservations
from tests.integration._reservation_helpers import (
    BALANCE_QUERY,
    HELD_QUERY,
    INITIAL_BALANCE,
    MODEL,
    PROVIDER,
    TASK,
    ZERO,
    make_metered_provider,
    make_services,
    mock_inner_adapter,
    seed_all,
)

_TEST_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000081")


# ===========================================================================
# Concurrent Reservations
# ===========================================================================


@pytest.mark.asyncio
class TestConcurrentReservations:
    """REQ-030 §15.2: Two concurrent reserves → one settles, one released."""

    async def test_concurrent_reserves_correct_held_balance(
        self, db_session: AsyncSession
    ) -> None:
        """Two reserves accumulate held_balance; settle+release clear it."""
        user = await seed_all(db_session, _TEST_USER_ID)
        metering, _ = make_services(db_session)

        # Reserve twice (simulating concurrent requests)
        r1 = await metering.reserve(user.id, TASK, max_tokens=4096)
        r2 = await metering.reserve(user.id, TASK, max_tokens=4096)
        await db_session.flush()

        # Refresh to get DB-rounded Numeric(10,6) values
        await db_session.refresh(r1)
        await db_session.refresh(r2)

        # Both held
        assert r1.status == "held"
        assert r2.status == "held"

        # held_balance reflects both reservations
        held_result = await db_session.execute(text(HELD_QUERY), {"uid": user.id})
        held = held_result.scalar_one()
        assert held == r1.estimated_cost_usd + r2.estimated_cost_usd

        # Settle r1 (LLM call succeeded)
        await metering.settle(r1, PROVIDER, MODEL, 1000, 500)
        # Release r2 (LLM call failed)
        await metering.release(r2)
        await db_session.flush()

        # Verify final statuses
        await db_session.refresh(r1)
        await db_session.refresh(r2)
        assert r1.status == "settled"
        assert r2.status == "released"

        # held_balance fully cleared
        held_result = await db_session.execute(text(HELD_QUERY), {"uid": user.id})
        assert held_result.scalar_one() == ZERO

        # Balance reduced by only r1's actual cost
        bal = await db_session.execute(text(BALANCE_QUERY), {"uid": user.id})
        row = bal.one()
        assert row.balance_usd < INITIAL_BALANCE
        assert row.balance_usd == INITIAL_BALANCE - r1.actual_cost_usd


# ===========================================================================
# Stale Reservation Sweep
# ===========================================================================


@pytest.mark.asyncio
class TestStaleReservationSweepIntegration:
    """REQ-030 §15.2: Old held reservation → sweep → stale, held decremented."""

    async def test_sweep_marks_stale_and_decrements_held_balance(
        self, db_session: AsyncSession
    ) -> None:
        """Stale reservation swept: status=stale, held_balance back to zero."""
        user = await seed_all(db_session, _TEST_USER_ID)
        metering, _ = make_services(db_session)

        # Create a reservation via the service (proper held_balance increment)
        reservation = await metering.reserve(user.id, TASK, max_tokens=4096)
        await db_session.flush()

        # Verify held_balance was incremented
        held_result = await db_session.execute(text(HELD_QUERY), {"uid": user.id})
        assert held_result.scalar_one() > 0

        # Backdate to simulate TTL expiry
        old_time = datetime.now(UTC) - timedelta(seconds=600)
        await db_session.execute(
            text("UPDATE usage_reservations SET created_at = :ts WHERE id = :id"),
            {"ts": old_time, "id": reservation.id},
        )

        # Run sweep with 300s TTL
        released = await sweep_stale_reservations(db_session, ttl_seconds=300)
        assert released == 1

        # Reservation marked stale
        row = await db_session.execute(
            text("SELECT status FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        assert row.scalar_one() == "stale"

        # held_balance decremented back to zero
        held_result = await db_session.execute(text(HELD_QUERY), {"uid": user.id})
        assert held_result.scalar_one() == ZERO

        # Balance unchanged (sweep doesn't debit balance)
        bal_result = await db_session.execute(
            text("SELECT balance_usd FROM users WHERE id = :uid"),
            {"uid": user.id},
        )
        assert bal_result.scalar_one() == INITIAL_BALANCE


# ===========================================================================
# Ledger Integrity
# ===========================================================================


@pytest.mark.asyncio
class TestLedgerIntegrity:
    """REQ-030 §15.2: After reservation cycle, ledger matches balance."""

    async def test_balance_equals_ledger_sum_after_settle(
        self, db_session: AsyncSession
    ) -> None:
        """After settle, balance_usd == SUM(credit_transactions.amount_usd)."""
        user = await seed_all(db_session, _TEST_USER_ID)

        # Seed initial purchase so ledger starts in sync with balance
        init_txn = CreditTransaction(
            user_id=user.id,
            amount_usd=INITIAL_BALANCE,
            transaction_type="purchase",
            description="Initial funding",
        )
        db_session.add(init_txn)
        await db_session.flush()

        # Run a full reservation cycle
        provider, _ = make_metered_provider(db_session, user.id)
        await provider.complete([], TaskType.EXTRACTION)
        await db_session.flush()

        # Compare balance against ledger sum
        bal_result = await db_session.execute(
            text("SELECT balance_usd FROM users WHERE id = :uid"),
            {"uid": user.id},
        )
        balance = bal_result.scalar_one()

        ledger_result = await db_session.execute(
            text(
                "SELECT COALESCE(SUM(amount_usd), 0) AS ledger_sum "
                "FROM credit_transactions WHERE user_id = :uid"
            ),
            {"uid": user.id},
        )
        ledger_sum = ledger_result.scalar_one()

        assert balance == ledger_sum

    async def test_ledger_intact_after_release(self, db_session: AsyncSession) -> None:
        """After release (no settle), no debit transaction exists."""
        user = await seed_all(db_session, _TEST_USER_ID)
        inner = mock_inner_adapter()
        inner.complete.side_effect = ProviderError("fail")
        provider, _ = make_metered_provider(db_session, user.id, inner)

        with pytest.raises(ProviderError):
            await provider.complete([], TaskType.EXTRACTION)

        await db_session.flush()

        # No credit transactions should exist (release doesn't create one)
        txn_count = await db_session.execute(
            text("SELECT COUNT(*) FROM credit_transactions WHERE user_id = :uid"),
            {"uid": user.id},
        )
        assert txn_count.scalar_one() == 0
