"""Tests for UsageRepository.get_summary() — usage aggregation.

REQ-020 §8.2: Verifies summary aggregation with period filtering,
task_type/provider breakdowns, and cross-user isolation.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import LLMUsageRecord
from app.models.user import User
from app.repositories.usage_repository import UsageRepository

# =============================================================================
# Helpers
# =============================================================================


async def _insert_record(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    provider: str = "claude",
    model: str = "claude-3-5-haiku-20241022",
    task_type: str = "extraction",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    raw_cost_usd: Decimal = Decimal("0.002800"),
    billed_cost_usd: Decimal = Decimal("0.003640"),
    margin_multiplier: Decimal = Decimal("1.30"),
    created_at: datetime | None = None,
) -> LLMUsageRecord:
    """Insert a usage record via ORM for test setup."""
    kwargs: dict[str, object] = {
        "user_id": user_id,
        "provider": provider,
        "model": model,
        "task_type": task_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "raw_cost_usd": raw_cost_usd,
        "billed_cost_usd": billed_cost_usd,
        "margin_multiplier": margin_multiplier,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    record = LLMUsageRecord(**kwargs)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


# =============================================================================
# TestGetSummary
# =============================================================================


class TestGetSummary:
    """Tests for UsageRepository.get_summary()."""

    async def test_aggregates_totals(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Summary includes correct aggregate totals."""
        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        await _insert_record(
            db_session,
            user_a.id,
            input_tokens=1000,
            output_tokens=500,
            raw_cost_usd=Decimal("0.002800"),
            billed_cost_usd=Decimal("0.003640"),
        )
        await _insert_record(
            db_session,
            user_a.id,
            input_tokens=2000,
            output_tokens=1000,
            raw_cost_usd=Decimal("0.005600"),
            billed_cost_usd=Decimal("0.007280"),
        )

        summary = await UsageRepository.get_summary(db_session, user_a.id, start, end)
        assert summary["total_calls"] == 2
        assert summary["total_input_tokens"] == 3000
        assert summary["total_output_tokens"] == 1500
        assert summary["total_raw_cost_usd"] == Decimal("0.008400")
        assert summary["total_billed_cost_usd"] == Decimal("0.010920")

    async def test_by_task_type_breakdown(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Summary breaks down costs by task type."""
        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        await _insert_record(
            db_session,
            user_a.id,
            task_type="extraction",
            input_tokens=1000,
            output_tokens=500,
            billed_cost_usd=Decimal("0.003640"),
        )
        await _insert_record(
            db_session,
            user_a.id,
            task_type="extraction",
            input_tokens=1000,
            output_tokens=500,
            billed_cost_usd=Decimal("0.003640"),
        )
        await _insert_record(
            db_session,
            user_a.id,
            task_type="cover_letter",
            input_tokens=2000,
            output_tokens=1000,
            billed_cost_usd=Decimal("0.007280"),
        )

        summary = await UsageRepository.get_summary(db_session, user_a.id, start, end)
        by_task = {item["task_type"]: item for item in summary["by_task_type"]}
        assert len(by_task) == 2
        assert by_task["extraction"]["call_count"] == 2
        assert by_task["extraction"]["input_tokens"] == 2000
        assert by_task["extraction"]["output_tokens"] == 1000
        assert by_task["extraction"]["billed_cost_usd"] == Decimal("0.007280")
        assert by_task["cover_letter"]["call_count"] == 1

    async def test_by_provider_breakdown(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Summary breaks down costs by provider."""
        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        await _insert_record(
            db_session,
            user_a.id,
            provider="claude",
            billed_cost_usd=Decimal("0.003640"),
        )
        await _insert_record(
            db_session,
            user_a.id,
            provider="openai",
            billed_cost_usd=Decimal("0.001000"),
        )

        summary = await UsageRepository.get_summary(db_session, user_a.id, start, end)
        by_prov = {item["provider"]: item for item in summary["by_provider"]}
        assert len(by_prov) == 2
        assert by_prov["claude"]["call_count"] == 1
        assert by_prov["claude"]["billed_cost_usd"] == Decimal("0.003640")
        assert by_prov["openai"]["call_count"] == 1

    async def test_period_filtering_excludes_outside_range(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Records outside the period range are excluded."""
        jan = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        feb = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)
        mar = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

        await _insert_record(db_session, user_a.id, created_at=jan)
        await _insert_record(db_session, user_a.id, created_at=feb)
        await _insert_record(db_session, user_a.id, created_at=mar)

        # Query February only [Feb 1, Mar 1)
        period_start = datetime(2026, 2, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 1, tzinfo=UTC)

        summary = await UsageRepository.get_summary(
            db_session, user_a.id, period_start, period_end
        )
        assert summary["total_calls"] == 1

    async def test_empty_period_returns_zeros(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Empty period returns zero aggregates and empty breakdowns."""
        now = datetime.now(UTC)
        summary = await UsageRepository.get_summary(
            db_session,
            user_a.id,
            now - timedelta(hours=1),
            now + timedelta(hours=1),
        )
        assert summary["total_calls"] == 0
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["total_raw_cost_usd"] == Decimal("0")
        assert summary["total_billed_cost_usd"] == Decimal("0")
        assert summary["by_task_type"] == []
        assert summary["by_provider"] == []

    async def test_cross_user_isolation(
        self, db_session: AsyncSession, user_a: User, other_user: User
    ) -> None:
        """Summary only includes records for the specified user."""
        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        await _insert_record(db_session, user_a.id)
        await _insert_record(db_session, other_user.id)

        summary = await UsageRepository.get_summary(db_session, user_a.id, start, end)
        assert summary["total_calls"] == 1
