"""Tests for MeteringService — DB-backed pricing and cost calculation.

REQ-022 §7: Verifies pricing lookup via AdminConfigService, per-model margins,
unregistered model blocking, and the record_and_debit pipeline.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import NoPricingConfigError, UnregisteredModelError
from app.services.admin_config_service import PricingResult
from app.services.metering_service import MeteringService

# =============================================================================
# Constants
# =============================================================================

_USER_ID = uuid.uuid4()
_PROVIDER = "claude"
_HAIKU_MODEL = "claude-3-5-haiku-20241022"
_SONNET_MODEL = "claude-3-5-sonnet-20241022"
_TASK_TYPE = "extraction"

# Pricing fixtures — simulate different models with different margins
_HAIKU_PRICING = PricingResult(
    input_cost_per_1k=Decimal("0.0008"),
    output_cost_per_1k=Decimal("0.004"),
    margin_multiplier=Decimal("3.00"),
    effective_date=date(2026, 1, 1),
)

_SONNET_PRICING = PricingResult(
    input_cost_per_1k=Decimal("0.003"),
    output_cost_per_1k=Decimal("0.015"),
    margin_multiplier=Decimal("1.10"),
    effective_date=date(2026, 1, 1),
)

_EMBEDDING_PRICING = PricingResult(
    input_cost_per_1k=Decimal("0.00002"),
    output_cost_per_1k=Decimal("0"),
    margin_multiplier=Decimal("1.30"),
    effective_date=date(2026, 1, 1),
)


# =============================================================================
# Helpers
# =============================================================================


def _added_objects(mock_db: AsyncMock) -> list:
    """Extract objects added to the mocked DB session."""
    return [c[0][0] for c in mock_db.add.call_args_list]


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
def mock_admin_config() -> AsyncMock:
    """Mocked AdminConfigService returning haiku pricing by default."""
    config = AsyncMock()
    config.is_model_registered.return_value = True
    config.get_pricing.return_value = _HAIKU_PRICING
    return config


@pytest.fixture
def service(mock_db: AsyncMock, mock_admin_config: AsyncMock) -> MeteringService:
    """MeteringService with mocked database and admin config."""
    return MeteringService(mock_db, mock_admin_config)


# =============================================================================
# TestCalculateCost
# =============================================================================


class TestCalculateCost:
    """Tests for MeteringService.calculate_cost() — DB-backed pricing."""

    @pytest.mark.asyncio
    async def test_uses_db_pricing_for_known_model(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """calculate_cost retrieves pricing from AdminConfigService."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        raw, billed = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 1000, 1000)
        expected_raw = Decimal("0.0008") + Decimal("0.004")
        assert raw == expected_raw
        assert billed == expected_raw * Decimal("3.00")

    @pytest.mark.asyncio
    async def test_per_model_margin_cheap_model(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Cheap model with high margin (3x) produces correct billed cost."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        raw, billed = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 1000, 1000)
        assert billed == raw * Decimal("3.00")

    @pytest.mark.asyncio
    async def test_per_model_margin_expensive_model(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Expensive model with thin margin (1.1x) produces correct billed cost."""
        mock_admin_config.get_pricing.return_value = _SONNET_PRICING
        raw, billed = await service.calculate_cost(_PROVIDER, _SONNET_MODEL, 1000, 1000)
        expected_raw = Decimal("0.003") + Decimal("0.015")
        assert raw == expected_raw
        assert billed == expected_raw * Decimal("1.10")

    @pytest.mark.asyncio
    async def test_embedding_pricing_output_zero(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Embedding pricing with output_cost=0 only charges input."""
        mock_admin_config.get_pricing.return_value = _EMBEDDING_PRICING
        raw, billed = await service.calculate_cost(
            "openai", "text-embedding-3-small", 1000, 0
        )
        assert raw == Decimal("0.00002")
        assert billed == Decimal("0.00002") * Decimal("1.30")

    @pytest.mark.asyncio
    async def test_zero_tokens_returns_zero_cost(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Zero input and output tokens produce zero cost."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        raw, billed = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 0, 0)
        assert raw == Decimal("0")
        assert billed == Decimal("0")

    @pytest.mark.asyncio
    async def test_zero_input_only_charges_output(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Only output cost when input tokens are zero."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        raw, _ = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 0, 1000)
        assert raw == Decimal("0.004")

    @pytest.mark.asyncio
    async def test_zero_output_only_charges_input(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Only input cost when output tokens are zero."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        raw, _ = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 1000, 0)
        assert raw == Decimal("0.0008")

    @pytest.mark.asyncio
    async def test_decimal_precision_no_float_drift(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Decimal arithmetic avoids float precision issues."""
        pricing = PricingResult(
            input_cost_per_1k=Decimal("0.00015"),
            output_cost_per_1k=Decimal("0.0006"),
            margin_multiplier=Decimal("1.30"),
            effective_date=date(2026, 1, 1),
        )
        mock_admin_config.get_pricing.return_value = pricing
        raw, _ = await service.calculate_cost("openai", "gpt-4o-mini", 3333, 1667)
        expected = (
            Decimal("3333") * Decimal("0.00015") + Decimal("1667") * Decimal("0.0006")
        ) / Decimal("1000")
        assert raw == expected

    @pytest.mark.asyncio
    async def test_unregistered_model_raises_error(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Unregistered model raises UnregisteredModelError."""
        mock_admin_config.is_model_registered.return_value = False
        with pytest.raises(UnregisteredModelError) as exc_info:
            await service.calculate_cost(_PROVIDER, "nonexistent-model", 1000, 1000)
        assert exc_info.value.code == "UNREGISTERED_MODEL"

    @pytest.mark.asyncio
    async def test_no_pricing_config_raises_error(
        self, service: MeteringService, mock_admin_config: AsyncMock
    ) -> None:
        """Registered model with no pricing raises NoPricingConfigError."""
        mock_admin_config.is_model_registered.return_value = True
        mock_admin_config.get_pricing.return_value = None
        with pytest.raises(NoPricingConfigError) as exc_info:
            await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 1000, 0)
        assert exc_info.value.code == "NO_PRICING_CONFIG"


# =============================================================================
# TestRecordAndDebit
# =============================================================================


class TestRecordAndDebit:
    """Tests for MeteringService.record_and_debit() — DB-backed pricing."""

    @pytest.mark.asyncio
    async def test_adds_usage_record_to_session(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Usage record is added to the database session."""
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )
        usage_record = _added_objects(mock_db)[0]
        assert usage_record.provider == _PROVIDER
        assert usage_record.model == _HAIKU_MODEL
        assert usage_record.task_type == _TASK_TYPE
        assert usage_record.input_tokens == 1000
        assert usage_record.output_tokens == 500

    @pytest.mark.asyncio
    async def test_adds_debit_transaction_to_session(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Debit transaction is added with negative amount."""
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )
        credit_txn = _added_objects(mock_db)[1]
        assert credit_txn.transaction_type == "usage_debit"
        assert credit_txn.amount_usd < Decimal("0")

    @pytest.mark.asyncio
    async def test_debit_transaction_references_usage_record(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Debit transaction's reference_id links to usage record."""
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )
        objects = _added_objects(mock_db)
        usage_record = objects[0]
        credit_txn = objects[1]
        assert credit_txn.reference_id == str(usage_record.id)

    @pytest.mark.asyncio
    async def test_executes_atomic_debit(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Atomic debit SQL is executed against the user's balance."""
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
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
                _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
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
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
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
                _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
            )
        assert "failed to record usage" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_usage_record_costs_match_calculation(
        self, service: MeteringService, mock_db: AsyncMock
    ) -> None:
        """Usage record costs match calculate_cost() output."""
        raw, billed = await service.calculate_cost(_PROVIDER, _HAIKU_MODEL, 1000, 500)
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )
        usage_record = _added_objects(mock_db)[0]
        assert usage_record.raw_cost_usd == raw
        assert usage_record.billed_cost_usd == billed

    @pytest.mark.asyncio
    async def test_per_model_margin_stored_on_usage_record(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Per-model margin from DB is stored on usage record."""
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )
        usage_record = _added_objects(mock_db)[0]
        assert usage_record.margin_multiplier == Decimal("3.00")

    @pytest.mark.asyncio
    async def test_different_models_get_different_margins(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Different models produce different billed costs due to per-model margins."""
        service = MeteringService(mock_db, mock_admin_config)

        # Cheap model: 3x margin
        mock_admin_config.get_pricing.return_value = _HAIKU_PRICING
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 1000
        )
        haiku_record = mock_db.add.call_args_list[0][0][0]

        # Reset mock
        mock_db.add.reset_mock()

        # Expensive model: 1.1x margin
        mock_admin_config.get_pricing.return_value = _SONNET_PRICING
        await service.record_and_debit(
            _USER_ID, _PROVIDER, _SONNET_MODEL, "chat_response", 1000, 1000
        )
        sonnet_record = mock_db.add.call_args_list[0][0][0]

        assert haiku_record.margin_multiplier == Decimal("3.00")
        assert sonnet_record.margin_multiplier == Decimal("1.10")

    @pytest.mark.asyncio
    async def test_unregistered_model_in_record_and_debit_logs_error(
        self,
        service: MeteringService,
        mock_admin_config: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unregistered model error in record_and_debit is logged, not raised."""
        mock_admin_config.is_model_registered.return_value = False
        with caplog.at_level(logging.ERROR):
            await service.record_and_debit(
                _USER_ID, _PROVIDER, "nonexistent-model", _TASK_TYPE, 1000, 500
            )
        assert "failed to record usage" in caplog.text.lower()
