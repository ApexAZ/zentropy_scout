"""Tests for Usage API endpoints.

REQ-020 §8: Tests for all 4 usage endpoints:
- GET /api/v1/usage/balance
- GET /api/v1/usage/summary
- GET /api/v1/usage/history
- GET /api/v1/usage/transactions

Tests verify:
- Correct response shapes and field types
- Monetary values formatted as strings with 6 decimal places
- Pagination works (page, per_page, total, total_pages)
- Filters applied (task_type, provider, transaction type)
- Auth required (401 without)
- Default period is current month for summary
- Empty results return empty lists
- Non-exposure of sensitive fields (raw_cost, margin, reference_id)
- Date range validation (inverted period → 422)

NOTE: File exceeds 300-line guideline. 4 test classes for 4 endpoints with
shared helpers and thorough coverage justify keeping them co-located.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction, LLMUsageRecord
from tests.conftest import TEST_USER_ID

# =============================================================================
# URL constants
# =============================================================================

_URL_BALANCE = "/api/v1/usage/balance"
_URL_SUMMARY = "/api/v1/usage/summary"
_URL_HISTORY = "/api/v1/usage/history"
_URL_TRANSACTIONS = "/api/v1/usage/transactions"

# =============================================================================
# Helpers
# =============================================================================


async def _create_usage_record(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    provider: str = "claude",
    model: str = "claude-3-5-haiku-20241022",
    task_type: str = "extraction",
    input_tokens: int = 1200,
    output_tokens: int = 450,
    raw_cost_usd: Decimal = Decimal("0.001000"),
    billed_cost_usd: Decimal = Decimal("0.001300"),
    margin_multiplier: Decimal = Decimal("1.30"),
    created_at: datetime | None = None,
) -> LLMUsageRecord:
    """Insert a usage record for testing."""
    record = LLMUsageRecord(
        user_id=user_id,
        provider=provider,
        model=model,
        task_type=task_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_cost_usd=raw_cost_usd,
        billed_cost_usd=billed_cost_usd,
        margin_multiplier=margin_multiplier,
    )
    if created_at is not None:
        record.created_at = created_at
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def _create_credit_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount_usd: Decimal = Decimal("10.000000"),
    transaction_type: str = "purchase",
    description: str | None = "Standard Credit Pack",
    created_at: datetime | None = None,
) -> CreditTransaction:
    """Insert a credit transaction for testing."""
    txn = CreditTransaction(
        user_id=user_id,
        amount_usd=amount_usd,
        transaction_type=transaction_type,
        description=description,
    )
    if created_at is not None:
        txn.created_at = created_at
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return txn


# =============================================================================
# GET /api/v1/usage/balance
# =============================================================================


class TestGetBalance:
    """Tests for GET /api/v1/usage/balance."""

    @pytest.mark.asyncio
    async def test_returns_balance(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Balance endpoint returns current balance as string."""
        response = await client.get(_URL_BALANCE)
        assert response.status_code == 200
        data = response.json()["data"]
        assert "balance_usd" in data
        assert "as_of" in data
        # Default balance is 0
        assert data["balance_usd"] == "0.000000"

    @pytest.mark.asyncio
    async def test_balance_format_six_decimals(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Balance value has exactly 6 decimal places."""
        from sqlalchemy import text

        await db_session.execute(
            text("UPDATE users SET balance_usd = :bal WHERE id = :uid"),
            {"bal": Decimal("4.230000"), "uid": TEST_USER_ID},
        )
        await db_session.commit()

        response = await client.get(_URL_BALANCE)
        data = response.json()["data"]
        assert data["balance_usd"] == "4.230000"

    @pytest.mark.asyncio
    async def test_balance_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Balance endpoint returns 401 without authentication."""
        response = await unauthenticated_client.get(_URL_BALANCE)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_balance_as_of_is_recent(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """as_of timestamp should be within the last few seconds."""
        response = await client.get(_URL_BALANCE)
        data = response.json()["data"]
        as_of = datetime.fromisoformat(data["as_of"])
        now = datetime.now(UTC)
        assert abs((now - as_of).total_seconds()) < 10


# =============================================================================
# GET /api/v1/usage/summary
# =============================================================================


class TestGetSummary:
    """Tests for GET /api/v1/usage/summary."""

    @pytest.mark.asyncio
    async def test_summary_empty_month(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Summary with no usage returns zero totals and empty lists."""
        response = await client.get(_URL_SUMMARY)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_calls"] == 0
        assert data["total_input_tokens"] == 0
        assert data["total_output_tokens"] == 0
        assert data["total_raw_cost_usd"] == "0.000000"
        assert data["total_billed_cost_usd"] == "0.000000"
        assert data["by_task_type"] == []
        assert data["by_provider"] == []

    @pytest.mark.asyncio
    async def test_summary_with_usage(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Summary aggregates usage records correctly."""

        now = datetime.now(UTC)
        await _create_usage_record(
            db_session,
            TEST_USER_ID,
            task_type="extraction",
            input_tokens=1000,
            output_tokens=500,
            raw_cost_usd=Decimal("0.002000"),
            billed_cost_usd=Decimal("0.002600"),
            created_at=now,
        )
        await _create_usage_record(
            db_session,
            TEST_USER_ID,
            task_type="cover_letter",
            provider="openai",
            input_tokens=2000,
            output_tokens=1000,
            raw_cost_usd=Decimal("0.010000"),
            billed_cost_usd=Decimal("0.013000"),
            created_at=now,
        )
        await db_session.commit()

        response = await client.get(_URL_SUMMARY)
        data = response.json()["data"]
        assert data["total_calls"] == 2
        assert data["total_input_tokens"] == 3000
        assert data["total_output_tokens"] == 1500
        assert len(data["by_task_type"]) == 2
        assert len(data["by_provider"]) == 2

    @pytest.mark.asyncio
    async def test_summary_custom_period(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Summary respects custom period_start and period_end."""

        # Record in January
        jan = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        await _create_usage_record(db_session, TEST_USER_ID, created_at=jan)
        # Record in February
        feb = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)
        await _create_usage_record(db_session, TEST_USER_ID, created_at=feb)
        await db_session.commit()

        # Query only January
        response = await client.get(
            _URL_SUMMARY,
            params={"period_start": "2026-01-01", "period_end": "2026-01-31"},
        )
        data = response.json()["data"]
        assert data["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_summary_default_period_is_current_month(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Summary without period params defaults to current UTC month."""
        response = await client.get(_URL_SUMMARY)
        data = response.json()["data"]
        today_utc = datetime.now(UTC).date()
        assert data["period_start"] == today_utc.replace(day=1).isoformat()
        assert data["period_end"] == today_utc.isoformat()

    @pytest.mark.asyncio
    async def test_summary_rejects_inverted_period(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Summary returns 422 when period_start > period_end."""
        response = await client.get(
            _URL_SUMMARY,
            params={"period_start": "2026-02-28", "period_end": "2026-02-01"},
        )
        assert response.status_code == 422
        error = response.json()["detail"]
        assert error["code"] == "INVALID_DATE_RANGE"

    @pytest.mark.asyncio
    async def test_summary_does_not_expose_margin_multiplier(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Summary response does not leak margin_multiplier."""
        await _create_usage_record(db_session, TEST_USER_ID)
        await db_session.commit()

        response = await client.get(_URL_SUMMARY)
        data = response.json()["data"]
        assert "margin_multiplier" not in data
        for entry in data["by_task_type"]:
            assert "margin_multiplier" not in entry

    @pytest.mark.asyncio
    async def test_summary_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Summary endpoint returns 401 without authentication."""
        response = await unauthenticated_client.get(_URL_SUMMARY)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_summary_monetary_values_are_strings(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """All monetary values in summary are strings, not numbers."""

        await _create_usage_record(db_session, TEST_USER_ID)
        await db_session.commit()

        response = await client.get(_URL_SUMMARY)
        data = response.json()["data"]
        # Top-level costs are formatted as 6-decimal strings, not numbers
        assert "." in data["total_raw_cost_usd"]
        assert len(data["total_raw_cost_usd"].split(".")[1]) == 6
        assert "." in data["total_billed_cost_usd"]
        assert len(data["total_billed_cost_usd"].split(".")[1]) == 6
        # Breakdown costs are also 6-decimal strings
        for entry in data["by_task_type"]:
            assert len(entry["billed_cost_usd"].split(".")[1]) == 6
        for entry in data["by_provider"]:
            assert len(entry["billed_cost_usd"].split(".")[1]) == 6


# =============================================================================
# GET /api/v1/usage/history
# =============================================================================


class TestGetHistory:
    """Tests for GET /api/v1/usage/history."""

    @pytest.mark.asyncio
    async def test_history_empty(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """History with no records returns empty list with pagination."""
        response = await client.get(_URL_HISTORY)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0
        assert body["meta"]["page"] == 1

    @pytest.mark.asyncio
    async def test_history_returns_records(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """History returns usage records with correct fields."""

        await _create_usage_record(db_session, TEST_USER_ID)
        await db_session.commit()

        response = await client.get(_URL_HISTORY)
        body = response.json()
        assert body["meta"]["total"] == 1
        record = body["data"][0]
        assert "id" in record
        assert record["provider"] == "claude"
        assert record["model"] == "claude-3-5-haiku-20241022"
        assert record["task_type"] == "extraction"
        assert record["input_tokens"] == 1200
        assert record["output_tokens"] == 450
        assert len(record["billed_cost_usd"].split(".")[1]) == 6
        assert "created_at" in record
        # Should NOT expose raw_cost_usd or margin_multiplier
        assert "raw_cost_usd" not in record
        assert "margin_multiplier" not in record

    @pytest.mark.asyncio
    async def test_history_pagination(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """History supports pagination with page and per_page."""

        for i in range(5):
            await _create_usage_record(
                db_session,
                TEST_USER_ID,
                created_at=datetime.now(UTC) - timedelta(hours=i),
            )
        await db_session.commit()

        # Page 1 with 2 per page
        response = await client.get(
            _URL_HISTORY,
            params={"page": 1, "per_page": 2},
        )
        body = response.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] == 5
        assert body["meta"]["page"] == 1
        assert body["meta"]["per_page"] == 2
        assert body["meta"]["total_pages"] == 3

        # Page 3 with 2 per page (last page, 1 item)
        response = await client.get(
            _URL_HISTORY,
            params={"page": 3, "per_page": 2},
        )
        body = response.json()
        assert len(body["data"]) == 1

    @pytest.mark.asyncio
    async def test_history_filter_by_task_type(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """History filters by task_type parameter."""

        await _create_usage_record(db_session, TEST_USER_ID, task_type="extraction")
        await _create_usage_record(db_session, TEST_USER_ID, task_type="cover_letter")
        await db_session.commit()

        response = await client.get(
            _URL_HISTORY,
            params={"task_type": "extraction"},
        )
        body = response.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["task_type"] == "extraction"

    @pytest.mark.asyncio
    async def test_history_filter_by_provider(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """History filters by provider parameter."""

        await _create_usage_record(db_session, TEST_USER_ID, provider="claude")
        await _create_usage_record(db_session, TEST_USER_ID, provider="openai")
        await db_session.commit()

        response = await client.get(
            _URL_HISTORY,
            params={"provider": "openai"},
        )
        body = response.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_history_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """History endpoint returns 401 without authentication."""
        response = await unauthenticated_client.get(_URL_HISTORY)
        assert response.status_code == 401


# =============================================================================
# GET /api/v1/usage/transactions
# =============================================================================


class TestGetTransactions:
    """Tests for GET /api/v1/usage/transactions."""

    @pytest.mark.asyncio
    async def test_transactions_empty(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Transactions with no records returns empty list."""
        response = await client.get(_URL_TRANSACTIONS)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_transactions_returns_records(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Transactions returns records with correct fields."""

        await _create_credit_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("15.000000"),
            transaction_type="purchase",
            description="Standard Credit Pack",
        )
        await db_session.commit()

        response = await client.get(_URL_TRANSACTIONS)
        body = response.json()
        assert body["meta"]["total"] == 1
        txn = body["data"][0]
        assert "id" in txn
        assert txn["amount_usd"] == "15.000000"
        assert txn["transaction_type"] == "purchase"
        assert txn["description"] == "Standard Credit Pack"
        assert "created_at" in txn
        # Should NOT expose reference_id
        assert "reference_id" not in txn

    @pytest.mark.asyncio
    async def test_transactions_debit_is_negative(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Debit transactions have negative amount_usd."""

        await _create_credit_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("-0.033150"),
            transaction_type="usage_debit",
            description="Cover letter generation",
        )
        await db_session.commit()

        response = await client.get(_URL_TRANSACTIONS)
        txn = response.json()["data"][0]
        assert txn["amount_usd"] == "-0.033150"
        assert txn["transaction_type"] == "usage_debit"

    @pytest.mark.asyncio
    async def test_transactions_pagination(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Transactions supports pagination."""

        for _ in range(3):
            await _create_credit_transaction(db_session, TEST_USER_ID)
        await db_session.commit()

        response = await client.get(
            _URL_TRANSACTIONS,
            params={"page": 1, "per_page": 2},
        )
        body = response.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] == 3
        assert body["meta"]["total_pages"] == 2

    @pytest.mark.asyncio
    async def test_transactions_filter_by_type(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Transactions filters by type parameter."""

        await _create_credit_transaction(
            db_session, TEST_USER_ID, transaction_type="purchase"
        )
        await _create_credit_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("-0.001000"),
            transaction_type="usage_debit",
        )
        await db_session.commit()

        response = await client.get(
            _URL_TRANSACTIONS,
            params={"type": "purchase"},
        )
        body = response.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["transaction_type"] == "purchase"

    @pytest.mark.asyncio
    async def test_transactions_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Transactions endpoint returns 401 without authentication."""
        response = await unauthenticated_client.get(_URL_TRANSACTIONS)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_transactions_null_description(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
        db_session: AsyncSession,
    ) -> None:
        """Transactions with null description returns null."""

        await _create_credit_transaction(db_session, TEST_USER_ID, description=None)
        await db_session.commit()

        response = await client.get(_URL_TRANSACTIONS)
        txn = response.json()["data"][0]
        assert txn["description"] is None

    @pytest.mark.asyncio
    async def test_transactions_rejects_invalid_type(
        self,
        client: AsyncClient,
        test_user: None,  # noqa: ARG002
    ) -> None:
        """Transactions rejects invalid type filter values."""
        response = await client.get(
            _URL_TRANSACTIONS,
            params={"type": "invalid_type"},
        )
        # FastAPI Literal validation → 400 (custom error handler) or 422
        assert response.status_code in (400, 422)
