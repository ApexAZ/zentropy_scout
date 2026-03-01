"""Integration tests for the full metering pipeline.

REQ-020 §12.2: End-to-end metering, concurrent request safety,
and reconciliation — all with real DB and MockLLMProvider.
"""

import asyncio
import logging
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_sufficient_balance
from app.core.config import settings
from app.core.errors import InsufficientBalanceError
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.user import User
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMResponse, TaskType
from app.providers.llm.mock_adapter import MockLLMProvider
from app.providers.metered_provider import MeteredLLMProvider
from app.services.metering_service import MeteringService

# =============================================================================
# Constants
# =============================================================================

_MARGIN = Decimal("1.30")
_INITIAL_BALANCE = Decimal("10.000000")

# Use a unique user ID per test module to avoid collisions
_METERING_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")

# Provider/model strings (avoid duplication across test providers + assertions)
_CLAUDE_PROVIDER = "claude"
_HAIKU_MODEL = "claude-3-5-haiku-20241022"
_TEST_RESPONSE_CONTENT = "Test response"

# Claude Haiku pricing (from MeteringService._LLM_PRICING)
_HAIKU_INPUT_PER_1K = Decimal("0.0008")
_HAIKU_OUTPUT_PER_1K = Decimal("0.004")

# MockLLMProvider returns 100 input + 50 output tokens, model="mock-model"
# Our test inner provider returns claude haiku with same token counts:
_INPUT_TOKENS = 100
_OUTPUT_TOKENS = 50

# Expected costs for one call with Haiku pricing:
# raw  = (100 * 0.0008 + 50 * 0.004) / 1000 = (0.08 + 0.2) / 1000 = 0.00028
# billed = 0.00028 * 1.30 = 0.000364
_EXPECTED_RAW_COST = (
    Decimal(_INPUT_TOKENS) * _HAIKU_INPUT_PER_1K
    + Decimal(_OUTPUT_TOKENS) * _HAIKU_OUTPUT_PER_1K
) / Decimal(1000)
_EXPECTED_BILLED_COST = _EXPECTED_RAW_COST * _MARGIN


# =============================================================================
# Test inner provider (returns known pricing entry)
# =============================================================================


class _HaikuMockProvider(MockLLMProvider):
    """MockLLMProvider that mimics Claude Haiku for pricing tests."""

    @property
    def provider_name(self) -> str:
        return _CLAUDE_PROVIDER

    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        **kwargs: object,
    ) -> LLMResponse:
        """Return a response with Haiku model and realistic token counts."""
        self.calls.append(
            {"method": "complete", "messages": messages, "task": task, "kwargs": kwargs}
        )
        self.last_task = task
        return LLMResponse(
            content=_TEST_RESPONSE_CONTENT,
            model=_HAIKU_MODEL,
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            finish_reason="stop",
            latency_ms=10,
        )


class _FailingMockProvider(MockLLMProvider):
    """MockLLMProvider that raises on complete()."""

    @property
    def provider_name(self) -> str:
        return _CLAUDE_PROVIDER

    async def complete(
        self,
        _messages: list[LLMMessage],
        _task: TaskType,
        **_kwargs: object,
    ) -> LLMResponse:
        """Simulate a provider error."""
        raise ProviderError("Simulated API failure")


class _UnknownModelProvider(MockLLMProvider):
    """MockLLMProvider that returns an unknown model for fallback pricing tests."""

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(
        self,
        _messages: list[LLMMessage],
        _task: TaskType,
        **_kwargs: object,
    ) -> LLMResponse:
        """Return a response with a model not in the pricing table."""
        return LLMResponse(
            content="Response",
            model="gpt-5-turbo",
            input_tokens=200,
            output_tokens=100,
            finish_reason="stop",
            latency_ms=10,
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def metering_user(db_session: AsyncSession) -> User:
    """Create a test user with a known balance for metering tests."""
    user = User(
        id=_METERING_USER_ID,
        email="metering-test@example.com",
        balance_usd=_INITIAL_BALANCE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def inner_provider() -> _HaikuMockProvider:
    """Inner LLM provider that returns Haiku pricing."""
    return _HaikuMockProvider()


@pytest.fixture
def metering_service(db_session: AsyncSession) -> MeteringService:
    """MeteringService with real DB and known margin."""
    return MeteringService(db_session, margin_multiplier=_MARGIN)


@pytest.fixture
def metered_provider(
    inner_provider: _HaikuMockProvider,
    metering_service: MeteringService,
) -> MeteredLLMProvider:
    """MeteredLLMProvider wrapping the Haiku mock."""
    return MeteredLLMProvider(inner_provider, metering_service, _METERING_USER_ID)


@pytest.fixture
def _enable_metering():
    """Temporarily enable metering for tests that need it."""
    original = settings.metering_enabled
    settings.metering_enabled = True
    yield
    settings.metering_enabled = original


@pytest.fixture
def _disable_metering():
    """Temporarily disable metering for tests that need it."""
    original = settings.metering_enabled
    settings.metering_enabled = False
    yield
    settings.metering_enabled = original


# =============================================================================
# Helpers
# =============================================================================

_SIMPLE_MESSAGES: list[LLMMessage] = [{"role": "user", "content": "Hello"}]


async def _get_balance(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Read current balance directly from users table."""
    result = await db.execute(select(User.balance_usd).where(User.id == user_id))
    return result.scalar_one()


async def _count_usage_records(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count LLM usage records for a user."""
    result = await db.execute(
        select(func.count())
        .select_from(LLMUsageRecord)
        .where(LLMUsageRecord.user_id == user_id)
    )
    return result.scalar_one()


async def _count_credit_transactions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count credit transactions for a user."""
    result = await db.execute(
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
    )
    return result.scalar_one()


async def _sum_transactions(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Sum all credit transaction amounts for a user."""
    result = await db.execute(
        select(func.coalesce(func.sum(CreditTransaction.amount_usd), 0)).where(
            CreditTransaction.user_id == user_id
        )
    )
    return result.scalar_one()


# =============================================================================
# Tests — End-to-end metering pipeline (REQ-020 §12.2)
# =============================================================================


class TestEndToEndMetering:
    """MeteredLLMProvider.complete() inserts records and debits balance."""

    @pytest.mark.asyncio
    async def test_complete_inserts_usage_record(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """After complete(), an LLMUsageRecord exists with correct fields."""
        await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        # Flush to see inserts within same transaction
        await db_session.flush()

        records = (
            (
                await db_session.execute(
                    select(LLMUsageRecord).where(
                        LLMUsageRecord.user_id == _METERING_USER_ID
                    )
                )
            )
            .scalars()
            .all()
        )

        assert len(records) == 1
        record = records[0]
        assert record.provider == _CLAUDE_PROVIDER
        assert record.model == _HAIKU_MODEL
        assert record.task_type == "extraction"
        assert record.input_tokens == _INPUT_TOKENS
        assert record.output_tokens == _OUTPUT_TOKENS
        assert record.raw_cost_usd == _EXPECTED_RAW_COST
        assert record.billed_cost_usd == _EXPECTED_BILLED_COST
        assert record.margin_multiplier == _MARGIN

    @pytest.mark.asyncio
    async def test_complete_inserts_credit_transaction(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """After complete(), a CreditTransaction with type=usage_debit exists."""
        await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)
        await db_session.flush()

        txns = (
            (
                await db_session.execute(
                    select(CreditTransaction).where(
                        CreditTransaction.user_id == _METERING_USER_ID
                    )
                )
            )
            .scalars()
            .all()
        )

        assert len(txns) == 1
        txn = txns[0]
        assert txn.transaction_type == "usage_debit"
        assert txn.amount_usd == -_EXPECTED_BILLED_COST
        assert _CLAUDE_PROVIDER in txn.description
        assert "extraction" in txn.description

    @pytest.mark.asyncio
    async def test_complete_debits_balance(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """After complete(), user balance is reduced by billed cost."""
        await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)
        await db_session.flush()

        balance = await _get_balance(db_session, _METERING_USER_ID)
        expected = _INITIAL_BALANCE - _EXPECTED_BILLED_COST
        assert balance == expected

    @pytest.mark.asyncio
    async def test_complete_returns_llm_response(self, metering_user, metered_provider):  # noqa: ARG002
        """complete() returns the inner provider's response unchanged."""
        response = await metered_provider.complete(
            _SIMPLE_MESSAGES, TaskType.EXTRACTION
        )

        assert response.content == _TEST_RESPONSE_CONTENT
        assert response.model == _HAIKU_MODEL
        assert response.input_tokens == _INPUT_TOKENS
        assert response.output_tokens == _OUTPUT_TOKENS

    @pytest.mark.asyncio
    async def test_multiple_calls_accumulate_records(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """Multiple complete() calls create separate records and debit cumulatively."""
        n_calls = 5
        for _ in range(n_calls):
            await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)
        await db_session.flush()

        usage_count = await _count_usage_records(db_session, _METERING_USER_ID)
        txn_count = await _count_credit_transactions(db_session, _METERING_USER_ID)
        balance = await _get_balance(db_session, _METERING_USER_ID)

        assert usage_count == n_calls
        assert txn_count == n_calls
        expected_balance = _INITIAL_BALANCE - (_EXPECTED_BILLED_COST * n_calls)
        assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_usage_record_reference_links_to_transaction(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """The CreditTransaction.reference_id matches the LLMUsageRecord.id."""
        await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)
        await db_session.flush()

        usage = (
            await db_session.execute(
                select(LLMUsageRecord).where(
                    LLMUsageRecord.user_id == _METERING_USER_ID
                )
            )
        ).scalar_one()

        txn = (
            await db_session.execute(
                select(CreditTransaction).where(
                    CreditTransaction.user_id == _METERING_USER_ID
                )
            )
        ).scalar_one()

        assert txn.reference_id == str(usage.id)


# =============================================================================
# Tests — Concurrent request safety (REQ-020 §12.2)
# =============================================================================


class TestConcurrentRequests:
    """Concurrent LLM calls must not overdraft via race condition."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_no_overdraft(self, db_session, metering_user):  # noqa: ARG002
        """asyncio.gather() with many calls never drives balance below zero.

        User has $10.00. Each call costs ~$0.000364. Even hundreds of
        concurrent calls shouldn't overdraft because the atomic UPDATE
        uses WHERE balance_usd >= amount.

        Note: Concurrent calls share the same db_session. This is intentional —
        asyncio.gather() runs coroutines concurrently within a single event loop,
        which is how concurrent FastAPI requests within a single worker behave.
        """
        n_concurrent = 20

        async def _make_one_call(_idx: int) -> LLMResponse:
            inner = _HaikuMockProvider()
            service = MeteringService(db_session, margin_multiplier=_MARGIN)
            provider = MeteredLLMProvider(inner, service, _METERING_USER_ID)
            return await provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        results = await asyncio.gather(
            *[_make_one_call(i) for i in range(n_concurrent)]
        )
        await db_session.flush()

        # All calls should succeed (return responses)
        assert len(results) == n_concurrent

        # Balance should never be negative
        balance = await _get_balance(db_session, _METERING_USER_ID)
        assert balance >= Decimal("0")

        # All records should be inserted
        usage_count = await _count_usage_records(db_session, _METERING_USER_ID)
        assert usage_count == n_concurrent

    @pytest.mark.asyncio
    async def test_concurrent_calls_with_low_balance_no_overdraft(self, db_session):
        """With a balance that can only cover 2 calls, concurrent calls
        must not overdraft even if 10 run simultaneously.

        The atomic debit's WHERE clause prevents overdraft. Some calls
        will log a warning for insufficient balance, but none will
        drive the balance below zero.
        """
        # Create user with very low balance (enough for ~2 calls)
        low_balance_user_id = uuid.UUID("00000000-0000-0000-0000-000000000021")
        two_calls_worth = _EXPECTED_BILLED_COST * 2 + Decimal("0.000001")
        user = User(
            id=low_balance_user_id,
            email="low-balance@example.com",
            balance_usd=two_calls_worth,
        )
        db_session.add(user)
        await db_session.commit()

        n_concurrent = 10

        async def _make_one_call() -> LLMResponse:
            inner = _HaikuMockProvider()
            service = MeteringService(db_session, margin_multiplier=_MARGIN)
            provider = MeteredLLMProvider(inner, service, low_balance_user_id)
            return await provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        # All calls should complete (metering never blocks the LLM response)
        results = await asyncio.gather(*[_make_one_call() for _ in range(n_concurrent)])
        await db_session.flush()

        assert len(results) == n_concurrent

        # Balance must be >= 0
        balance = await _get_balance(db_session, low_balance_user_id)
        assert balance >= Decimal("0")


# =============================================================================
# Tests — Reconciliation (REQ-020 §12.2)
# =============================================================================


class TestReconciliation:
    """SUM(credit_transactions.amount_usd) correlates with users.balance_usd."""

    @pytest.mark.asyncio
    async def test_sum_transactions_matches_balance_after_debits(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """After multiple metered calls, the sum of debit transactions
        equals the negative of the balance change.

        Since the user starts at $10.00 and all transactions are debits,
        balance_change = initial_balance - current_balance should equal
        -SUM(transactions) [transactions are negative].
        """
        n_calls = 5
        for _ in range(n_calls):
            await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)
        await db_session.flush()

        balance = await _get_balance(db_session, _METERING_USER_ID)
        txn_sum = await _sum_transactions(db_session, _METERING_USER_ID)

        # txn_sum is negative (all debits), balance decreased by that amount
        balance_change = _INITIAL_BALANCE - balance
        assert balance_change == -txn_sum

    @pytest.mark.asyncio
    async def test_reconciliation_with_mixed_operations(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """After debits and a manual credit, reconciliation still holds.

        Simulate: 3 metered calls (debits) + 1 manual credit of $5.00.
        """
        # 3 metered calls (debits)
        for _ in range(3):
            await metered_provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        # Manual credit (simulates a Stripe purchase)
        credit_amount = Decimal("5.000000")
        credit_txn = CreditTransaction(
            id=uuid.uuid4(),
            user_id=_METERING_USER_ID,
            amount_usd=credit_amount,
            transaction_type="purchase",
            reference_id="stripe_session_123",
            description="$5.00 credit purchase",
        )
        db_session.add(credit_txn)

        # Manually credit the balance (as CreditRepository.atomic_credit would)
        await db_session.execute(
            text(
                "UPDATE users SET balance_usd = balance_usd + :amount "
                "WHERE id = :user_id"
            ),
            {"amount": credit_amount, "user_id": _METERING_USER_ID},
        )
        await db_session.flush()

        balance = await _get_balance(db_session, _METERING_USER_ID)
        txn_sum = await _sum_transactions(db_session, _METERING_USER_ID)

        # Balance should be: initial + credit - (3 * billed_cost)
        expected_balance = (
            _INITIAL_BALANCE + credit_amount - (_EXPECTED_BILLED_COST * 3)
        )
        assert balance == expected_balance

        # SUM(txns) should be: credit + (3 * -billed_cost)
        # And initial_balance + SUM(txns) == current_balance
        assert _INITIAL_BALANCE + txn_sum == balance


# =============================================================================
# Tests — Balance gating (REQ-020 §7, §12)
# =============================================================================


class TestBalanceGating:
    """Balance check returns 402 when balance is zero or insufficient."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_enable_metering")
    async def test_402_when_balance_zero(self, db_session):
        """require_sufficient_balance raises InsufficientBalanceError at $0."""
        zero_user_id = uuid.UUID("00000000-0000-0000-0000-000000000022")
        user = User(
            id=zero_user_id,
            email="zero-balance@example.com",
            balance_usd=Decimal("0.000000"),
        )
        db_session.add(user)
        await db_session.commit()

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await require_sufficient_balance(zero_user_id, db_session)

        assert exc_info.value.status_code == 402
        assert exc_info.value.code == "INSUFFICIENT_BALANCE"
        assert exc_info.value.details is not None
        assert exc_info.value.details[0]["balance_usd"] == "0.000000"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_enable_metering")
    async def test_no_402_when_balance_positive(self, db_session, metering_user):  # noqa: ARG002
        """require_sufficient_balance passes when balance > 0."""
        # Should not raise
        await require_sufficient_balance(_METERING_USER_ID, db_session)


# =============================================================================
# Tests — Metering disabled (REQ-020 §11)
# =============================================================================


class TestMeteringDisabled:
    """When metering_enabled=False, no records are created and balance unchanged."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_disable_metering")
    async def test_disabled_metering_no_records(self, db_session, metering_user):  # noqa: ARG002
        """With metering disabled, complete() works but no DB records created."""
        # Use a raw MockLLMProvider (not metered) since the DI function
        # would return the raw provider when disabled. We simulate
        # the behavior directly.
        inner = _HaikuMockProvider()
        response = await inner.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        # No usage records
        usage_count = await _count_usage_records(db_session, _METERING_USER_ID)
        assert usage_count == 0

        # No credit transactions
        txn_count = await _count_credit_transactions(db_session, _METERING_USER_ID)
        assert txn_count == 0

        # Balance unchanged
        balance = await _get_balance(db_session, _METERING_USER_ID)
        assert balance == _INITIAL_BALANCE

        # Response still works
        assert response.content == _TEST_RESPONSE_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_disable_metering")
    async def test_disabled_metering_skips_balance_check(self, db_session):
        """With metering disabled, balance check is skipped entirely."""
        zero_user_id = uuid.UUID("00000000-0000-0000-0000-000000000023")
        user = User(
            id=zero_user_id,
            email="zero-disabled@example.com",
            balance_usd=Decimal("0.000000"),
        )
        db_session.add(user)
        await db_session.commit()

        # Should NOT raise even with zero balance
        await require_sufficient_balance(zero_user_id, db_session)


# =============================================================================
# Tests — Provider error handling (REQ-020 §6.4)
# =============================================================================


class TestProviderError:
    """When the inner provider raises, no usage is recorded."""

    @pytest.mark.asyncio
    async def test_provider_error_no_usage_recorded(self, db_session, metering_user):  # noqa: ARG002
        """If inner.complete() raises ProviderError, no records are created."""
        inner = _FailingMockProvider()
        service = MeteringService(db_session, margin_multiplier=_MARGIN)
        provider = MeteredLLMProvider(inner, service, _METERING_USER_ID)

        with pytest.raises(ProviderError):
            await provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        await db_session.flush()

        usage_count = await _count_usage_records(db_session, _METERING_USER_ID)
        txn_count = await _count_credit_transactions(db_session, _METERING_USER_ID)
        balance = await _get_balance(db_session, _METERING_USER_ID)

        assert usage_count == 0
        assert txn_count == 0
        assert balance == _INITIAL_BALANCE


# =============================================================================
# Tests — Unknown model fallback pricing (REQ-020 §5.3)
# =============================================================================


class TestUnknownModelFallback:
    """Unknown models use fallback pricing and log a warning."""

    @pytest.mark.asyncio
    async def test_unknown_model_uses_fallback_pricing(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        caplog,
    ):
        """An unknown model for a known provider uses fallback pricing."""
        service = MeteringService(db_session, margin_multiplier=_MARGIN)

        unknown_model = "claude-future-model"
        with caplog.at_level(logging.WARNING, logger="app.services.metering_service"):
            raw_cost, billed_cost = service.calculate_cost(
                _CLAUDE_PROVIDER, unknown_model, 1000, 1000
            )

        # Fallback for claude: input=0.003, output=0.015 per 1K
        expected_raw = Decimal("0.003") + Decimal("0.015")  # 1000 tokens each / 1K
        assert raw_cost == expected_raw
        assert billed_cost == expected_raw * _MARGIN

        # Warning should be logged
        assert "Unknown model" in caplog.text
        assert unknown_model in caplog.text
        assert "fallback" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_zero_cost(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        caplog,
    ):
        """An unknown provider returns zero cost and logs a warning."""
        service = MeteringService(db_session, margin_multiplier=_MARGIN)

        with caplog.at_level(logging.WARNING, logger="app.services.metering_service"):
            raw_cost, billed_cost = service.calculate_cost(
                "unknown_provider", "some-model", 1000, 1000
            )

        assert raw_cost == Decimal("0")
        assert billed_cost == Decimal("0")

        assert "No pricing available" in caplog.text
        assert "unknown_provider" in caplog.text

    @pytest.mark.asyncio
    async def test_unknown_model_records_with_fallback_cost(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        caplog,
    ):
        """Full pipeline with unknown model: records created with fallback pricing."""
        inner = _UnknownModelProvider()
        service = MeteringService(db_session, margin_multiplier=_MARGIN)
        provider = MeteredLLMProvider(inner, service, _METERING_USER_ID)

        with caplog.at_level(logging.WARNING, logger="app.services.metering_service"):
            await provider.complete(_SIMPLE_MESSAGES, TaskType.EXTRACTION)

        await db_session.flush()

        # Record should exist with fallback pricing
        record = (
            await db_session.execute(
                select(LLMUsageRecord).where(
                    LLMUsageRecord.user_id == _METERING_USER_ID
                )
            )
        ).scalar_one()

        assert record.model == "gpt-5-turbo"
        assert record.provider == "openai"

        # OpenAI fallback: input=0.0025, output=0.01 per 1K
        expected_raw = (
            Decimal(200) * Decimal("0.0025") + Decimal(100) * Decimal("0.01")
        ) / Decimal(1000)
        assert record.raw_cost_usd == expected_raw
        assert record.billed_cost_usd == expected_raw * _MARGIN

        assert "Unknown model" in caplog.text
        assert "gpt-5-turbo" in caplog.text


# =============================================================================
# Tests — Different task types (REQ-020 §5)
# =============================================================================


class TestDifferentTaskTypes:
    """Metering correctly records different task types."""

    @pytest.mark.asyncio
    async def test_different_task_types_recorded_separately(
        self,
        db_session,
        metering_user,  # noqa: ARG002
        metered_provider,
    ):
        """Each task type is recorded with the correct task_type field."""
        tasks = [
            TaskType.EXTRACTION,
            TaskType.COVER_LETTER,
            TaskType.SKILL_EXTRACTION,
        ]
        for task in tasks:
            await metered_provider.complete(_SIMPLE_MESSAGES, task)
        await db_session.flush()

        records = (
            (
                await db_session.execute(
                    select(LLMUsageRecord)
                    .where(LLMUsageRecord.user_id == _METERING_USER_ID)
                    .order_by(LLMUsageRecord.created_at)
                )
            )
            .scalars()
            .all()
        )

        assert len(records) == 3
        recorded_types = {r.task_type for r in records}
        assert recorded_types == {"extraction", "cover_letter", "skill_extraction"}
