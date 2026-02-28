"""Tests for UsageRepository — CRUD + list with pagination/filters.

REQ-020 §4, §8: Verifies create and list_by_user operations.
Summary aggregation tests are in test_usage_repository_summary.py.
"""

import uuid
from datetime import UTC, datetime
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
    provider="claude",
    model="claude-3-5-haiku-20241022",
    task_type="extraction",
    input_tokens=1000,
    output_tokens=500,
    raw_cost_usd=Decimal("0.002800"),
    billed_cost_usd=Decimal("0.003640"),
    margin_multiplier=Decimal("1.30"),
    created_at=None,
) -> LLMUsageRecord:
    """Insert a usage record via ORM for test setup.

    Supports explicit created_at for ordering and period tests.
    """
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
# TestCreate
# =============================================================================


class TestCreate:
    """Tests for UsageRepository.create()."""

    async def test_creates_record_with_all_fields(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Create returns record with all fields populated."""
        record = await UsageRepository.create(
            db_session,
            user_id=user_a.id,
            provider="claude",
            model="claude-3-5-haiku-20241022",
            task_type="extraction",
            input_tokens=1000,
            output_tokens=500,
            raw_cost_usd=Decimal("0.002800"),
            billed_cost_usd=Decimal("0.003640"),
            margin_multiplier=Decimal("1.30"),
        )
        assert record.id is not None
        assert record.user_id == user_a.id
        assert record.provider == "claude"
        assert record.model == "claude-3-5-haiku-20241022"
        assert record.task_type == "extraction"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.raw_cost_usd == Decimal("0.002800")
        assert record.billed_cost_usd == Decimal("0.003640")
        assert record.margin_multiplier == Decimal("1.30")

    async def test_created_at_set_automatically(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Server sets created_at on insert."""
        record = await UsageRepository.create(
            db_session,
            user_id=user_a.id,
            provider="claude",
            model="claude-3-5-haiku-20241022",
            task_type="extraction",
            input_tokens=1000,
            output_tokens=500,
            raw_cost_usd=Decimal("0.002800"),
            billed_cost_usd=Decimal("0.003640"),
            margin_multiplier=Decimal("1.30"),
        )
        assert record.created_at is not None

    async def test_decimal_values_roundtrip(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Sub-cent Decimal values survive DB roundtrip."""
        record = await UsageRepository.create(
            db_session,
            user_id=user_a.id,
            provider="openai",
            model="text-embedding-3-small",
            task_type="embedding",
            input_tokens=1000,
            output_tokens=0,
            raw_cost_usd=Decimal("0.000020"),
            billed_cost_usd=Decimal("0.000026"),
            margin_multiplier=Decimal("1.30"),
        )
        assert record.raw_cost_usd == Decimal("0.000020")
        assert record.billed_cost_usd == Decimal("0.000026")


# =============================================================================
# TestListByUser
# =============================================================================


class TestListByUser:
    """Tests for UsageRepository.list_by_user()."""

    async def test_returns_records_for_user(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns all records for the specified user."""
        await _insert_record(db_session, user_a.id)
        await _insert_record(db_session, user_a.id)
        records, total = await UsageRepository.list_by_user(db_session, user_a.id)
        assert len(records) == 2
        assert total == 2

    async def test_pagination_page_one(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """First page returns correct subset."""
        for _ in range(5):
            await _insert_record(db_session, user_a.id)
        records, total = await UsageRepository.list_by_user(
            db_session, user_a.id, offset=0, limit=3
        )
        assert len(records) == 3
        assert total == 5

    async def test_pagination_page_two(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Second page returns remaining records."""
        for _ in range(5):
            await _insert_record(db_session, user_a.id)
        records, total = await UsageRepository.list_by_user(
            db_session, user_a.id, offset=3, limit=3
        )
        assert len(records) == 2
        assert total == 5

    async def test_filter_by_task_type(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Filters records by task_type."""
        await _insert_record(db_session, user_a.id, task_type="extraction")
        await _insert_record(db_session, user_a.id, task_type="cover_letter")
        await _insert_record(db_session, user_a.id, task_type="extraction")
        records, total = await UsageRepository.list_by_user(
            db_session, user_a.id, task_type="extraction"
        )
        assert len(records) == 2
        assert total == 2
        assert all(r.task_type == "extraction" for r in records)

    async def test_filter_by_provider(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Filters records by provider."""
        await _insert_record(db_session, user_a.id, provider="claude")
        await _insert_record(db_session, user_a.id, provider="openai")
        records, total = await UsageRepository.list_by_user(
            db_session, user_a.id, provider="claude"
        )
        assert len(records) == 1
        assert total == 1
        assert records[0].provider == "claude"

    async def test_combined_filters(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Both task_type and provider filters applied together."""
        await _insert_record(
            db_session, user_a.id, provider="claude", task_type="extraction"
        )
        await _insert_record(
            db_session, user_a.id, provider="claude", task_type="cover_letter"
        )
        await _insert_record(
            db_session, user_a.id, provider="openai", task_type="extraction"
        )
        records, total = await UsageRepository.list_by_user(
            db_session, user_a.id, task_type="extraction", provider="claude"
        )
        assert len(records) == 1
        assert total == 1

    async def test_ordered_by_created_at_desc(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Results ordered by created_at descending (most recent first)."""
        r_old = await _insert_record(
            db_session,
            user_a.id,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        r_new = await _insert_record(
            db_session,
            user_a.id,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        records, _ = await UsageRepository.list_by_user(db_session, user_a.id)
        assert records[0].id == r_new.id
        assert records[1].id == r_old.id

    async def test_cross_user_isolation(
        self, db_session: AsyncSession, user_a: User, other_user: User
    ) -> None:
        """Records from other users are not returned."""
        await _insert_record(db_session, user_a.id)
        await _insert_record(db_session, other_user.id)
        records, total = await UsageRepository.list_by_user(db_session, user_a.id)
        assert len(records) == 1
        assert total == 1

    async def test_empty_result(self, db_session: AsyncSession, user_a: User) -> None:
        """No records returns empty list and zero count."""
        records, total = await UsageRepository.list_by_user(db_session, user_a.id)
        assert records == []
        assert total == 0
