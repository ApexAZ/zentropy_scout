"""Tests for MeteringService — pricing and cost calculation.

REQ-020 §5: Verifies pricing table, cost formula, margin application,
fallback pricing, and the record_and_debit pipeline.
"""

import logging
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.metering_service import MeteringService

# =============================================================================
# Constants
# =============================================================================

_DEFAULT_MARGIN = Decimal("1.30")
_USER_ID = uuid.uuid4()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mocked AsyncSession for unit tests."""
    db = AsyncMock()
    db.add = MagicMock()  # add() is synchronous in SQLAlchemy
    mock_result = MagicMock()
    mock_result.rowcount = 1  # Default: successful debit
    db.execute.return_value = mock_result
    return db


@pytest.fixture
def service(mock_db: AsyncMock) -> MeteringService:
    """MeteringService with mocked database and default margin."""
    return MeteringService(mock_db, margin_multiplier=_DEFAULT_MARGIN)


# =============================================================================
# TestCalculateCost
# =============================================================================


class TestCalculateCost:
    """Tests for MeteringService.calculate_cost()."""

    @pytest.mark.parametrize(
        ("provider", "model", "input_tokens", "output_tokens", "expected_raw"),
        [
            # Claude models (REQ-020 §5.1)
            (
                "claude",
                "claude-3-5-haiku-20241022",
                1000,
                1000,
                Decimal("0.0008") + Decimal("0.004"),
            ),
            (
                "claude",
                "claude-3-5-sonnet-20241022",
                1000,
                1000,
                Decimal("0.003") + Decimal("0.015"),
            ),
            # OpenAI models (REQ-020 §5.1)
            (
                "openai",
                "gpt-4o-mini",
                1000,
                1000,
                Decimal("0.00015") + Decimal("0.0006"),
            ),
            (
                "openai",
                "gpt-4o",
                1000,
                1000,
                Decimal("0.0025") + Decimal("0.01"),
            ),
            # Gemini models (REQ-020 §5.1)
            (
                "gemini",
                "gemini-2.0-flash",
                1000,
                1000,
                Decimal("0.0001") + Decimal("0.0004"),
            ),
            (
                "gemini",
                "gemini-2.5-flash",
                1000,
                1000,
                Decimal("0.00015") + Decimal("0.0035"),
            ),
            # Embedding models (REQ-020 §5.2) — output_tokens=0
            (
                "openai",
                "text-embedding-3-small",
                1000,
                0,
                Decimal("0.00002"),
            ),
            (
                "openai",
                "text-embedding-3-large",
                1000,
                0,
                Decimal("0.00013"),
            ),
        ],
        ids=[
            "claude-haiku",
            "claude-sonnet",
            "openai-gpt4o-mini",
            "openai-gpt4o",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "embedding-small",
            "embedding-large",
        ],
    )
    def test_known_model_pricing(
        self,
        service: MeteringService,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        expected_raw: Decimal,
    ) -> None:
        """Each known model produces correct raw cost for 1K tokens."""
        raw, billed = service.calculate_cost(
            provider, model, input_tokens, output_tokens
        )
        assert raw == expected_raw
        assert billed == expected_raw * _DEFAULT_MARGIN

    def test_margin_applied_correctly(self, service: MeteringService) -> None:
        """Billed cost equals raw cost multiplied by margin."""
        raw, billed = service.calculate_cost(
            "claude", "claude-3-5-haiku-20241022", 2000, 500
        )
        assert billed == raw * _DEFAULT_MARGIN

    def test_worked_example_from_spec(self, service: MeteringService) -> None:
        """Verify the exact worked example from REQ-020 §5.4."""
        raw, billed = service.calculate_cost(
            "claude", "claude-3-5-sonnet-20241022", 2500, 1200
        )
        assert raw == Decimal("0.0255")
        assert billed == Decimal("0.03315")

    def test_zero_tokens_returns_zero_cost(self, service: MeteringService) -> None:
        """Zero input and output tokens produce zero cost."""
        raw, billed = service.calculate_cost(
            "claude", "claude-3-5-haiku-20241022", 0, 0
        )
        assert raw == Decimal("0")
        assert billed == Decimal("0")

    def test_zero_input_only_charges_output(self, service: MeteringService) -> None:
        """Only output cost when input tokens are zero."""
        raw, _ = service.calculate_cost("claude", "claude-3-5-haiku-20241022", 0, 1000)
        assert raw == Decimal("0.004")

    def test_zero_output_only_charges_input(self, service: MeteringService) -> None:
        """Only input cost when output tokens are zero."""
        raw, _ = service.calculate_cost("claude", "claude-3-5-haiku-20241022", 1000, 0)
        assert raw == Decimal("0.0008")

    @pytest.mark.parametrize(
        ("provider", "expected_raw"),
        [
            ("claude", Decimal("0.003") + Decimal("0.015")),
            ("openai", Decimal("0.0025") + Decimal("0.01")),
            ("gemini", Decimal("0.00015") + Decimal("0.0035")),
        ],
        ids=["claude-fallback", "openai-fallback", "gemini-fallback"],
    )
    def test_unknown_model_uses_provider_fallback(
        self,
        service: MeteringService,
        provider: str,
        expected_raw: Decimal,
    ) -> None:
        """Unknown model for known provider falls back to highest tier."""
        raw, billed = service.calculate_cost(provider, "nonexistent-model", 1000, 1000)
        assert raw == expected_raw
        assert billed == expected_raw * _DEFAULT_MARGIN

    def test_unknown_model_logs_warning(
        self, service: MeteringService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown model logs a warning about fallback usage."""
        with caplog.at_level(logging.WARNING):
            service.calculate_cost("claude", "nonexistent-model", 1000, 1000)
        assert "nonexistent-model" in caplog.text
        assert "fallback" in caplog.text.lower()

    def test_unknown_provider_returns_zero(self, service: MeteringService) -> None:
        """Completely unknown provider returns zero cost."""
        raw, billed = service.calculate_cost(
            "unknown-provider", "unknown-model", 1000, 1000
        )
        assert raw == Decimal("0")
        assert billed == Decimal("0")

    def test_unknown_provider_logs_warning(
        self, service: MeteringService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown provider logs a warning."""
        with caplog.at_level(logging.WARNING):
            service.calculate_cost("unknown-provider", "unknown-model", 1000, 1000)
        assert "unknown-provider" in caplog.text

    def test_decimal_precision_no_float_drift(self, service: MeteringService) -> None:
        """Decimal arithmetic avoids float precision issues.

        With floats: 0.1 + 0.2 = 0.30000000000000004
        With Decimals: Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
        """
        # gpt-4o-mini: input $0.00015, output $0.0006
        # Use token counts that would produce float drift
        raw, _ = service.calculate_cost("openai", "gpt-4o-mini", 3333, 1667)
        expected = (
            Decimal("3333") * Decimal("0.00015") + Decimal("1667") * Decimal("0.0006")
        ) / Decimal("1000")
        assert raw == expected

    def test_custom_margin_multiplier(self, mock_db: AsyncMock) -> None:
        """Service respects custom margin multiplier."""
        custom_margin = Decimal("1.50")
        svc = MeteringService(mock_db, margin_multiplier=custom_margin)
        raw, billed = svc.calculate_cost(
            "claude", "claude-3-5-haiku-20241022", 1000, 1000
        )
        assert billed == raw * custom_margin


# =============================================================================
# TestRecordAndDebit
# =============================================================================


class TestRecordAndDebit:
    """Tests for MeteringService.record_and_debit()."""

    @pytest.mark.asyncio
    async def test_adds_usage_record_to_session(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Usage record is added to the database session."""
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        added_objects = [c[0][0] for c in mock_db.add.call_args_list]
        usage_record = added_objects[0]
        assert usage_record.provider == "claude"
        assert usage_record.model == "claude-3-5-haiku-20241022"
        assert usage_record.task_type == "extraction"
        assert usage_record.input_tokens == 1000
        assert usage_record.output_tokens == 500

    @pytest.mark.asyncio
    async def test_adds_debit_transaction_to_session(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Debit transaction is added with negative amount."""
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        added_objects = [c[0][0] for c in mock_db.add.call_args_list]
        credit_txn = added_objects[1]
        assert credit_txn.transaction_type == "usage_debit"
        assert credit_txn.amount_usd < Decimal("0")

    @pytest.mark.asyncio
    async def test_debit_transaction_references_usage_record(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Debit transaction's reference_id links to usage record."""
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        added_objects = [c[0][0] for c in mock_db.add.call_args_list]
        usage_record = added_objects[0]
        credit_txn = added_objects[1]
        assert credit_txn.reference_id == str(usage_record.id)

    @pytest.mark.asyncio
    async def test_executes_atomic_debit(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Atomic debit SQL is executed against the user's balance."""
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_insufficient_balance_logs_warning(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs warning when atomic debit fails (insufficient balance)."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        with caplog.at_level(logging.WARNING):
            await service.record_and_debit(
                _USER_ID,
                "claude",
                "claude-3-5-haiku-20241022",
                "extraction",
                1000,
                500,
            )
        assert "insufficient" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_insufficient_balance_does_not_raise(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Service does not raise when debit fails — user already got response."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        # Should not raise
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )

    @pytest.mark.asyncio
    async def test_db_error_logs_and_does_not_raise(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Database errors are logged but do not propagate."""
        mock_db.flush.side_effect = Exception("DB connection lost")

        with caplog.at_level(logging.ERROR):
            await service.record_and_debit(
                _USER_ID,
                "claude",
                "claude-3-5-haiku-20241022",
                "extraction",
                1000,
                500,
            )
        assert "failed to record usage" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_usage_record_costs_match_calculation(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Usage record costs match calculate_cost() output."""
        raw, billed = service.calculate_cost(
            "claude", "claude-3-5-haiku-20241022", 1000, 500
        )
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        added_objects = [c[0][0] for c in mock_db.add.call_args_list]
        usage_record = added_objects[0]
        assert usage_record.raw_cost_usd == raw
        assert usage_record.billed_cost_usd == billed

    @pytest.mark.asyncio
    async def test_margin_snapshot_stored_on_usage_record(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Margin multiplier at call time is stored on usage record."""
        await service.record_and_debit(
            _USER_ID,
            "claude",
            "claude-3-5-haiku-20241022",
            "extraction",
            1000,
            500,
        )
        added_objects = [c[0][0] for c in mock_db.add.call_args_list]
        usage_record = added_objects[0]
        assert usage_record.margin_multiplier == _DEFAULT_MARGIN
