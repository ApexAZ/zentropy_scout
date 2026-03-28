"""Tests for MeteringService — DB-backed pricing and cost calculation.

REQ-022 §7: Verifies pricing lookup via AdminConfigService, per-model margins,
unregistered model blocking, and the record_and_debit pipeline.
REQ-030 §5.2: Verifies reserve() — routing, pricing lookup, cost estimation,
UsageReservation creation, and held_balance_usd increment.
"""

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
    async def test_db_error_does_not_raise(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
    ) -> None:
        """Database errors do not propagate — user already got their response."""
        mock_db.flush.side_effect = Exception("DB connection lost")

        await service.record_and_debit(
            _USER_ID, _PROVIDER, _HAIKU_MODEL, _TASK_TYPE, 1000, 500
        )

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
    async def test_unregistered_model_does_not_raise(
        self,
        service: MeteringService,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Unregistered model in record_and_debit does not propagate."""
        mock_admin_config.is_model_registered.return_value = False

        await service.record_and_debit(
            _USER_ID, _PROVIDER, "nonexistent-model", _TASK_TYPE, 1000, 500
        )


# =============================================================================
# TestReserve
# =============================================================================


class TestReserve:
    """Tests for MeteringService.reserve() — pre-debit reservation.

    REQ-030 §5.2: Resolves routing, looks up pricing, calculates estimated
    cost from max_tokens × output_price × margin, creates UsageReservation,
    and atomically increments held_balance_usd.
    """

    @pytest.fixture
    def mock_admin_config_with_routing(self, mock_admin_config: AsyncMock) -> AsyncMock:
        """AdminConfigService with routing configured for extraction task."""
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        return mock_admin_config

    @pytest.fixture
    def reserve_service(
        self, mock_db: AsyncMock, mock_admin_config_with_routing: AsyncMock
    ) -> MeteringService:
        """MeteringService with routing + pricing configured."""
        return MeteringService(mock_db, mock_admin_config_with_routing)

    @pytest.mark.asyncio
    async def test_creates_reservation_with_held_status(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """reserve() creates a UsageReservation with status='held'."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        assert reservation.status == "held"
        assert reservation.user_id == _USER_ID
        assert reservation.task_type == _TASK_TYPE

    @pytest.mark.asyncio
    async def test_stores_provider_and_model_from_routing(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Reservation stores the routed provider and model."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        assert reservation.provider == _PROVIDER
        assert reservation.model == _HAIKU_MODEL

    @pytest.mark.asyncio
    async def test_stores_max_tokens(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Reservation stores the max_tokens used for estimation."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=2048
        )
        assert reservation.max_tokens == 2048

    @pytest.mark.asyncio
    async def test_estimated_cost_matches_formula(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Estimated cost = (max_tokens / 1000) * output_per_1k * margin.

        With haiku pricing: output_per_1k=0.004, margin=3.00, max_tokens=4096:
        (4096 / 1000) * 0.004 * 3.00 = 0.049152
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        expected = (
            (Decimal("4096") / Decimal("1000"))
            * _HAIKU_PRICING.output_cost_per_1k
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_default_max_tokens_when_none(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """max_tokens=None defaults to 4096 for cost estimation."""
        reservation = await reserve_service.reserve(_USER_ID, _TASK_TYPE)
        assert reservation.max_tokens == 4096
        expected = (
            (Decimal("4096") / Decimal("1000"))
            * _HAIKU_PRICING.output_cost_per_1k
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_increments_held_balance(
        self,
        reserve_service: MeteringService,
        mock_db: AsyncMock,
    ) -> None:
        """reserve() atomically increments held_balance_usd on users table."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        # Verify execute was called with UPDATE for held_balance
        execute_calls = mock_db.execute.call_args_list
        assert len(execute_calls) == 1
        sql_arg = str(execute_calls[0][0][0])
        assert "held_balance_usd" in sql_arg
        params = execute_calls[0][0][1]
        assert params["user_id"] == _USER_ID
        assert params["amount"] == reservation.estimated_cost_usd

    @pytest.mark.asyncio
    async def test_flushes_session(
        self,
        reserve_service: MeteringService,
        mock_db: AsyncMock,
    ) -> None:
        """reserve() flushes the session after creating the reservation."""
        await reserve_service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_adds_reservation_to_session(
        self,
        reserve_service: MeteringService,
        mock_db: AsyncMock,
    ) -> None:
        """reserve() adds the returned reservation to the DB session."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        added = _added_objects(mock_db)
        assert len(added) == 1
        assert added[0] is reservation

    @pytest.mark.asyncio
    async def test_no_routing_raises_no_pricing_error(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """No routing configured raises NoPricingConfigError."""
        mock_admin_config.get_routing_for_task.return_value = None
        service = MeteringService(mock_db, mock_admin_config)

        with pytest.raises(NoPricingConfigError):
            await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)

    @pytest.mark.asyncio
    async def test_unregistered_model_raises_error(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Unregistered model in routing raises UnregisteredModelError."""
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, "bad-model")
        mock_admin_config.is_model_registered.return_value = False
        service = MeteringService(mock_db, mock_admin_config)

        with pytest.raises(UnregisteredModelError):
            await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)

    @pytest.mark.asyncio
    async def test_no_pricing_config_raises_error(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Missing pricing config raises NoPricingConfigError."""
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        mock_admin_config.is_model_registered.return_value = True
        mock_admin_config.get_pricing.return_value = None
        service = MeteringService(mock_db, mock_admin_config)

        with pytest.raises(NoPricingConfigError):
            await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)

    @pytest.mark.asyncio
    async def test_missing_user_raises_error(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Missing user (rowcount=0) raises ValueError."""
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        service = MeteringService(mock_db, mock_admin_config)

        with pytest.raises(ValueError, match="not found"):
            await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)

    @pytest.mark.asyncio
    async def test_no_reservation_on_pricing_failure(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """No reservation or held_balance change when pricing lookup fails."""
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        mock_admin_config.is_model_registered.return_value = False
        service = MeteringService(mock_db, mock_admin_config)

        with pytest.raises(UnregisteredModelError):
            await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)

        # No objects added, no execute (held_balance), no flush
        assert mock_db.add.call_count == 0
        assert mock_db.execute.call_count == 0
        mock_db.flush.assert_not_awaited()
