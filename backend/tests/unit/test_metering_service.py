"""Tests for MeteringService — DB-backed pricing and cost calculation.

REQ-022 §7: Verifies pricing lookup via AdminConfigService, per-model margins,
and unregistered model blocking.
REQ-030 §5.2: Verifies reserve() — routing, pricing lookup, cost estimation,
UsageReservation creation, and held_balance_usd increment.
REQ-030 §5.3: Verifies settle() — savepoint-wrapped recording, balance debit,
held release, and fail-closed error handling.
REQ-030 §5.5: Verifies release() — held balance decrement and status update.
REQ-030 §5.8: Verifies persist_response_metadata() — best-effort outbox
pattern that writes response metadata to the reservation row.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import NoPricingConfigError, UnregisteredModelError
from app.models.usage_reservation import UsageReservation
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
_POSITIVE_BALANCE = Decimal("5.000000")
_DB_ERROR_MSG = "DB error"
_PROGRAMMING_ERROR_MSG = "bad operand type"

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

# AF-05: Zero-cost pricing — both input and output at zero.
# PricingConfig allows >= 0 for both, but UsageReservation requires > 0.
_ZERO_PRICING = PricingResult(
    input_cost_per_1k=Decimal("0"),
    output_cost_per_1k=Decimal("0"),
    margin_multiplier=Decimal("1.00"),
    effective_date=date(2026, 1, 1),
)


# =============================================================================
# Helpers
# =============================================================================


def _added_objects(mock_db: AsyncMock) -> list:
    """Extract objects added to the mocked DB session."""
    return [c[0][0] for c in mock_db.add.call_args_list]


def _make_held_reservation() -> UsageReservation:
    """Create a held UsageReservation for settle/release tests.

    Estimated cost reflects the AF-03 input+output formula:
    (4096 * 0.0008 + 4096 * 0.004) / 1000 * 3.00 = 0.0589824
    """
    return UsageReservation(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        estimated_cost_usd=Decimal("0.0589824"),
        status="held",
        task_type=_TASK_TYPE,
        provider=_PROVIDER,
        model=_HAIKU_MODEL,
        max_tokens=4096,
    )


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
    mock_result.scalar_one.return_value = _POSITIVE_BALANCE  # Default: positive balance
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
# TestReserve
# =============================================================================


class TestReserve:
    """Tests for MeteringService.reserve() — pre-debit reservation.

    REQ-030 §5.2, AF-03: Resolves routing, looks up pricing, calculates
    estimated cost from (input_ceiling × input_price + output_ceiling ×
    output_price) × margin, creates UsageReservation, and atomically
    increments held_balance_usd.
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
    async def test_estimated_cost_includes_input_and_output(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Estimated cost includes both input and output token components.

        AF-03: estimated = (input_ceiling * input_per_1k + max_tokens * output_per_1k) / 1000 * margin.
        With haiku pricing: input_per_1k=0.0008, output_per_1k=0.004, margin=3.00,
        max_input_tokens=4096, max_tokens=4096:
        (4096 * 0.0008 + 4096 * 0.004) / 1000 * 3.00 = 0.0589824
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        expected = (
            (
                Decimal("4096") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("4096") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
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
            (
                Decimal("4096") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("4096") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_explicit_max_input_tokens_overrides_default(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Caller-specified max_input_tokens overrides the default ceiling."""
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096, max_input_tokens=8192
        )
        expected = (
            (
                Decimal("8192") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("4096") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_zero_input_price_uses_output_only(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Zero input_cost_per_1k produces output-only estimate (no input component)."""
        zero_input_pricing = PricingResult(
            input_cost_per_1k=Decimal("0"),
            output_cost_per_1k=Decimal("0.004"),
            margin_multiplier=Decimal("3.00"),
            effective_date=date(2026, 1, 1),
        )
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        mock_admin_config.get_pricing.return_value = zero_input_pricing
        service = MeteringService(mock_db, mock_admin_config)

        reservation = await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)
        # With zero input price, estimate should equal output-only formula
        expected = (
            (Decimal("4096") * zero_input_pricing.output_cost_per_1k)
            / Decimal("1000")
            * zero_input_pricing.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_negative_max_input_tokens_uses_default(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """Negative max_input_tokens falls back to default ceiling."""
        default_reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        negative_reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096, max_input_tokens=-100
        )
        assert (
            negative_reservation.estimated_cost_usd
            == default_reservation.estimated_cost_usd
        )

    @pytest.mark.asyncio
    async def test_zero_max_tokens_respected_for_embeddings(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """AF-13: max_tokens=0 must not be replaced with default.

        Embeddings produce zero output tokens. Treating 0 as falsy inflates
        the estimated cost by adding a 4096-token output component.
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=0, max_input_tokens=500
        )
        # With max_tokens=0, output component is zero — cost is input-only
        expected = (
            (
                Decimal("500") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("0") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_zero_max_input_tokens_respected(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """AF-13: max_input_tokens=0 must not be replaced with default.

        Symmetric to the max_tokens=0 test — ensures the guard fix applies
        to both parameters.
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096, max_input_tokens=0
        )
        expected = (
            (
                Decimal("0") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("4096") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected

    @pytest.mark.asyncio
    async def test_both_ceilings_zero_uses_minimum_floor(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """AF-13 + AF-05: Both ceilings zero produces the minimum floor cost.

        Realistic for embed([]) where estimated_tokens=0. The
        _MINIMUM_ESTIMATED_COST floor (0.000001) prevents a zero-cost
        reservation that would violate ck_reservation_estimated_positive.
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=0, max_input_tokens=0
        )
        assert reservation.estimated_cost_usd == Decimal("0.000001")

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
    async def test_zero_cost_pricing_produces_minimum_estimate(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
    ) -> None:
        """AF-05: Zero input+output pricing produces floor estimate, not zero.

        PricingConfig allows input_cost_per_1k=0 and output_cost_per_1k=0,
        but UsageReservation requires estimated_cost_usd > 0. The floor
        (0.000001) prevents an IntegrityError on the CHECK constraint.
        """
        mock_admin_config.get_routing_for_task.return_value = (_PROVIDER, _HAIKU_MODEL)
        mock_admin_config.get_pricing.return_value = _ZERO_PRICING
        service = MeteringService(mock_db, mock_admin_config)

        reservation = await service.reserve(_USER_ID, _TASK_TYPE, max_tokens=4096)
        assert reservation.estimated_cost_usd == Decimal("0.000001")

    @pytest.mark.asyncio
    async def test_normal_pricing_unaffected_by_floor(
        self,
        reserve_service: MeteringService,
    ) -> None:
        """AF-05: Normal pricing is not changed by the minimum floor.

        The floor only activates when estimated cost would be zero or
        below the representable minimum. Normal pricing produces values
        well above the floor and should be returned unchanged.
        """
        reservation = await reserve_service.reserve(
            _USER_ID, _TASK_TYPE, max_tokens=4096
        )
        # Haiku pricing produces 0.0589824, well above the floor
        expected = (
            (
                Decimal("4096") * _HAIKU_PRICING.input_cost_per_1k
                + Decimal("4096") * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal("1000")
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.estimated_cost_usd == expected
        assert reservation.estimated_cost_usd > Decimal("0.000001")

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


# =============================================================================
# TestSettle
# =============================================================================


class TestSettle:
    """Tests for MeteringService.settle() — post-LLM-call settlement.

    REQ-030 §5.3: Wraps all recording in a savepoint. Calculates actual cost,
    inserts LLMUsageRecord + CreditTransaction, debits balance, releases hold,
    and marks reservation as settled. Fail-closed on error.
    """

    @pytest.fixture
    def mock_db_with_savepoint(self, mock_db: AsyncMock) -> AsyncMock:
        """mock_db with begin_nested() returning async context manager."""
        mock_db.begin_nested = MagicMock(return_value=AsyncMock())
        return mock_db

    @pytest.fixture
    def settle_service(
        self, mock_db_with_savepoint: AsyncMock, mock_admin_config: AsyncMock
    ) -> MeteringService:
        """MeteringService wired for settle tests."""
        return MeteringService(mock_db_with_savepoint, mock_admin_config)

    @pytest.fixture
    def reservation(self) -> UsageReservation:
        """Pre-built held reservation from a prior reserve() call."""
        return _make_held_reservation()

    @pytest.mark.asyncio
    async def test_creates_usage_record(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() creates LLMUsageRecord with correct fields."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        added = _added_objects(mock_db_with_savepoint)
        usage_record = added[0]
        assert usage_record.provider == _PROVIDER
        assert usage_record.model == _HAIKU_MODEL
        assert usage_record.task_type == _TASK_TYPE
        assert usage_record.input_tokens == 1000
        assert usage_record.output_tokens == 500
        assert usage_record.user_id == _USER_ID

    @pytest.mark.asyncio
    async def test_creates_debit_transaction(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() creates CreditTransaction with negative billed cost."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        added = _added_objects(mock_db_with_savepoint)
        credit_txn = added[1]
        assert credit_txn.transaction_type == "usage_debit"
        assert credit_txn.amount_usd < Decimal("0")
        assert credit_txn.user_id == _USER_ID

    @pytest.mark.asyncio
    async def test_debit_references_usage_record(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """CreditTransaction reference_id links to LLMUsageRecord id."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        added = _added_objects(mock_db_with_savepoint)
        usage_record = added[0]
        credit_txn = added[1]
        assert credit_txn.reference_id == str(usage_record.id)

    @pytest.mark.asyncio
    async def test_debits_balance_and_releases_hold(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() atomically debits balance and releases held amount."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        execute_calls = mock_db_with_savepoint.execute.call_args_list
        # Two execute calls: balance debit + conditional reservation update
        assert len(execute_calls) == 2
        sql_arg = str(execute_calls[0][0][0])
        assert "balance_usd" in sql_arg
        assert "held_balance_usd" in sql_arg
        params = execute_calls[0][0][1]
        assert params["user_id"] == _USER_ID
        assert params["estimated"] == reservation.estimated_cost_usd
        expected_billed = (
            (
                Decimal(1000) * _HAIKU_PRICING.input_cost_per_1k
                + Decimal(500) * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal(1000)
            * _HAIKU_PRICING.margin_multiplier
        )
        assert params["actual"] == expected_billed

    @pytest.mark.asyncio
    async def test_usage_record_costs_match_pricing(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Usage record raw and billed costs match pricing formula."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        usage_record = _added_objects(mock_db_with_savepoint)[0]
        expected_raw = (
            Decimal(1000) * _HAIKU_PRICING.input_cost_per_1k
            + Decimal(500) * _HAIKU_PRICING.output_cost_per_1k
        ) / Decimal(1000)
        assert usage_record.raw_cost_usd == expected_raw
        assert (
            usage_record.billed_cost_usd
            == expected_raw * _HAIKU_PRICING.margin_multiplier
        )

    @pytest.mark.asyncio
    async def test_reservation_marked_settled(
        self,
        settle_service: MeteringService,
        reservation: UsageReservation,
    ) -> None:
        """settle() updates reservation status to 'settled'."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert reservation.status == "settled"

    @pytest.mark.asyncio
    async def test_reservation_stores_actual_cost(
        self,
        settle_service: MeteringService,
        reservation: UsageReservation,
    ) -> None:
        """settle() sets actual_cost_usd to the calculated billed cost."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        expected_billed = (
            (
                Decimal(1000) * _HAIKU_PRICING.input_cost_per_1k
                + Decimal(500) * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal(1000)
            * _HAIKU_PRICING.margin_multiplier
        )
        assert reservation.actual_cost_usd == expected_billed

    @pytest.mark.asyncio
    async def test_reservation_stores_settled_at(
        self,
        settle_service: MeteringService,
        reservation: UsageReservation,
    ) -> None:
        """settle() sets settled_at timestamp."""
        assert reservation.settled_at is None
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert reservation.settled_at is not None

    @pytest.mark.asyncio
    async def test_uses_savepoint(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() wraps operations in a savepoint (begin_nested)."""
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        mock_db_with_savepoint.begin_nested.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Settlement failure (DB error) is caught — reservation stays held.

        AF-07: SQLAlchemyError is an expected failure mode (connection loss,
        constraint violation) and is handled gracefully.
        """
        mock_db_with_savepoint.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        # Should not raise
        await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        # Fail-closed: reservation stays held for background sweep
        assert reservation.status == "held"

    @pytest.mark.asyncio
    async def test_pricing_failure_stays_held(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Pricing failure inside savepoint is caught — reservation stays held."""
        mock_admin_config.is_model_registered.return_value = False
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert reservation.status == "held"

    @pytest.mark.asyncio
    async def test_already_settled_is_noop(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() on non-held reservation is a no-op."""
        reservation.status = "settled"
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        mock_db_with_savepoint.add.assert_not_called()
        mock_db_with_savepoint.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_logs_error(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Settlement DB failure logs error with reservation and user IDs."""
        mock_db_with_savepoint.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with caplog.at_level(logging.ERROR):
            await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert any(
            "Settlement failed" in r.message and str(reservation.id) in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_uses_conditional_reservation_update(
        self,
        settle_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() uses WHERE status = 'held' guard on reservation UPDATE.

        AF-01: Prevents settle/sweep race where both processes act on the
        same reservation, causing double-decrement of held_balance_usd.
        """
        await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        execute_calls = mock_db_with_savepoint.execute.call_args_list
        # Second execute call is the conditional reservation UPDATE
        reservation_sql = str(execute_calls[1][0][0])
        assert "status = 'settled'" in reservation_sql
        assert "AND status = 'held'" in reservation_sql

    @pytest.mark.asyncio
    async def test_swept_reservation_aborts_cleanly(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """settle() aborts when sweep already handled the reservation.

        AF-01: If the conditional reservation UPDATE returns rowcount=0,
        the _ReservationSweptError triggers savepoint rollback — in
        production, all inserts and balance updates are undone.
        """
        # First call (balance debit) succeeds with positive balance,
        # second (reservation) returns 0 — sweep already handled it
        balance_mock = MagicMock(rowcount=1)
        balance_mock.scalar_one.return_value = _POSITIVE_BALANCE
        mock_db_with_savepoint.execute.side_effect = [
            balance_mock,
            MagicMock(rowcount=0),
        ]
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)

        # Reservation stays 'held' in memory — sweep handles cleanup
        assert reservation.status == "held"
        # Savepoint was used — rollback undoes inserts + balance debit
        mock_db_with_savepoint.begin_nested.assert_called_once()

    @pytest.mark.asyncio
    async def test_swept_reservation_logs_warning(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """settle() logs warning (not error) when sweep wins the race."""
        balance_mock = MagicMock(rowcount=1)
        balance_mock.scalar_one.return_value = _POSITIVE_BALANCE
        mock_db_with_savepoint.execute.side_effect = [
            balance_mock,
            MagicMock(rowcount=0),
        ]
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with caplog.at_level(logging.WARNING):
            await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert any(
            "sweep" in r.message.lower() and str(reservation.id) in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    @pytest.mark.asyncio
    async def test_logs_error_on_balance_overdraft(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """settle() logs ERROR when balance goes negative after debit (AF-02).

        The settlement still completes (fail-forward) since the LLM service
        was already consumed, but the overdraft is logged for operator alert.
        """
        balance_result = MagicMock()
        balance_result.scalar_one.return_value = Decimal("-0.500000")
        reservation_result = MagicMock(rowcount=1)
        mock_db_with_savepoint.execute.side_effect = [
            balance_result,
            reservation_result,
        ]
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with caplog.at_level(logging.ERROR):
            await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        overdraft_records = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "overdraft" in r.message.lower()
        ]
        assert len(overdraft_records) == 1
        msg = overdraft_records[0].message
        assert str(reservation.user_id) in msg
        assert str(reservation.id) in msg
        # Verify billed cost is included for operator investigation
        expected_billed = (
            (
                Decimal(1000) * _HAIKU_PRICING.input_cost_per_1k
                + Decimal(500) * _HAIKU_PRICING.output_cost_per_1k
            )
            / Decimal(1000)
            * _HAIKU_PRICING.margin_multiplier
        )
        assert str(expected_billed) in msg

    @pytest.mark.asyncio
    async def test_overdraft_still_settles_reservation(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Overdraft does not prevent settlement — service was already consumed.

        AF-02: Fail-forward. The usage record and debit transaction are
        still created. Only an ERROR log is emitted for operator investigation.
        """
        balance_result = MagicMock()
        balance_result.scalar_one.return_value = Decimal("-0.500000")
        reservation_result = MagicMock(rowcount=1)
        mock_db_with_savepoint.execute.side_effect = [
            balance_result,
            reservation_result,
        ]
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert reservation.status == "settled"

    @pytest.mark.asyncio
    async def test_no_overdraft_log_on_positive_balance(
        self,
        settle_service: MeteringService,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No overdraft error when balance remains positive after settlement."""
        with caplog.at_level(logging.ERROR):
            await settle_service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)
        assert not any(
            "overdraft" in r.message.lower()
            for r in caplog.records
            if r.levelno == logging.ERROR
        )

    @pytest.mark.asyncio
    async def test_programming_error_propagates(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """AF-07: Programming errors (TypeError, AttributeError) must NOT be
        silently swallowed — they propagate so callers can react.

        Expected DB/pricing errors are still caught, but a TypeError inside
        the savepoint indicates a bug that must be surfaced, not hidden.
        """
        mock_db_with_savepoint.execute.side_effect = TypeError(_PROGRAMMING_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with pytest.raises(TypeError, match=_PROGRAMMING_ERROR_MSG):
            await service.settle(reservation, _PROVIDER, _HAIKU_MODEL, 1000, 500)


# =============================================================================
# TestRelease
# =============================================================================


class TestRelease:
    """Tests for MeteringService.release() — held reservation release.

    REQ-030 §5.5: Decrements held_balance_usd and marks reservation as
    'released' when the LLM call fails. Uses savepoint + conditional SQL
    UPDATE to prevent release/sweep race. Errors are logged, not raised.
    """

    @pytest.fixture
    def mock_db_with_savepoint(self, mock_db: AsyncMock) -> AsyncMock:
        """mock_db with begin_nested() returning async context manager."""
        mock_db.begin_nested = MagicMock(return_value=AsyncMock())
        return mock_db

    @pytest.fixture
    def release_service(
        self, mock_db_with_savepoint: AsyncMock, mock_admin_config: AsyncMock
    ) -> MeteringService:
        """MeteringService wired for release tests."""
        return MeteringService(mock_db_with_savepoint, mock_admin_config)

    @pytest.fixture
    def reservation(self) -> UsageReservation:
        """Pre-built held reservation from a prior reserve() call."""
        return _make_held_reservation()

    @pytest.mark.asyncio
    async def test_decrements_held_balance(
        self,
        release_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() decrements held_balance_usd by estimated cost."""
        await release_service.release(reservation)
        execute_calls = mock_db_with_savepoint.execute.call_args_list
        # Two execute calls: conditional reservation UPDATE + balance decrement
        assert len(execute_calls) == 2
        # Second call is the balance decrement
        sql_arg = str(execute_calls[1][0][0])
        assert "held_balance_usd" in sql_arg
        params = execute_calls[1][0][1]
        assert params["amount"] == reservation.estimated_cost_usd
        assert params["user_id"] == _USER_ID

    @pytest.mark.asyncio
    async def test_reservation_marked_released(
        self,
        release_service: MeteringService,
        reservation: UsageReservation,
    ) -> None:
        """release() updates reservation status to 'released'."""
        await release_service.release(reservation)
        assert reservation.status == "released"

    @pytest.mark.asyncio
    async def test_reservation_stores_settled_at(
        self,
        release_service: MeteringService,
        reservation: UsageReservation,
    ) -> None:
        """release() sets settled_at timestamp."""
        assert reservation.settled_at is None
        await release_service.release(reservation)
        assert reservation.settled_at is not None

    @pytest.mark.asyncio
    async def test_flushes_session(
        self,
        release_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() flushes the session after releasing."""
        await release_service.release(reservation)
        mock_db_with_savepoint.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_savepoint(
        self,
        release_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() wraps operations in a savepoint (begin_nested)."""
        await release_service.release(reservation)
        mock_db_with_savepoint.begin_nested.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_conditional_reservation_update(
        self,
        release_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() uses WHERE status = 'held' guard on reservation UPDATE.

        AF-01: Prevents release/sweep race — same pattern as settle().
        """
        await release_service.release(reservation)
        execute_calls = mock_db_with_savepoint.execute.call_args_list
        # First execute call is the conditional reservation UPDATE
        reservation_sql = str(execute_calls[0][0][0])
        assert "status = 'released'" in reservation_sql
        assert "AND status = 'held'" in reservation_sql

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Release DB failure is caught — reservation stays held.

        AF-07: SQLAlchemyError is an expected failure mode and is handled
        gracefully. The hold remains for background sweep.
        """
        mock_db_with_savepoint.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        # Should not raise
        await service.release(reservation)
        # Fail-closed: hold remains for background sweep
        assert reservation.status == "held"

    @pytest.mark.asyncio
    async def test_already_released_is_noop(
        self,
        release_service: MeteringService,
        mock_db_with_savepoint: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() on non-held reservation is a no-op."""
        reservation.status = "released"
        await release_service.release(reservation)
        mock_db_with_savepoint.execute.assert_not_called()
        mock_db_with_savepoint.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_error_logs_error(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Release DB failure logs error with reservation and user IDs."""
        mock_db_with_savepoint.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with caplog.at_level(logging.ERROR):
            await service.release(reservation)
        assert any(
            "Release failed" in r.message and str(reservation.id) in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_swept_reservation_skips_release(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """release() aborts when sweep already handled the reservation.

        AF-01: If the conditional reservation UPDATE returns rowcount=0,
        no balance decrement occurs — prevents double-decrement.
        """
        mock_db_with_savepoint.execute.return_value = MagicMock(rowcount=0)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        await service.release(reservation)

        # Only one execute call (the conditional UPDATE), no balance decrement
        assert mock_db_with_savepoint.execute.call_count == 1
        # Reservation stays 'held' in memory — sweep handles it
        assert reservation.status == "held"

    @pytest.mark.asyncio
    async def test_swept_reservation_logs_warning(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """release() logs warning (not error) when sweep wins the race."""
        mock_db_with_savepoint.execute.return_value = MagicMock(rowcount=0)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with caplog.at_level(logging.WARNING):
            await service.release(reservation)
        assert any(
            "sweep" in r.message.lower() and str(reservation.id) in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    @pytest.mark.asyncio
    async def test_programming_error_propagates(
        self,
        mock_db_with_savepoint: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """AF-07: Programming errors (TypeError, AttributeError) must NOT be
        silently swallowed — they propagate so callers can react.

        Expected DB errors (SQLAlchemyError) are still caught, but a TypeError
        inside the savepoint indicates a bug that must be surfaced.
        """
        mock_db_with_savepoint.execute.side_effect = TypeError(_PROGRAMMING_ERROR_MSG)
        service = MeteringService(mock_db_with_savepoint, mock_admin_config)
        with pytest.raises(TypeError, match=_PROGRAMMING_ERROR_MSG):
            await service.release(reservation)


# =============================================================================
# TestPersistResponseMetadata
# =============================================================================


class TestPersistResponseMetadata:
    """Tests for MeteringService.persist_response_metadata().

    REQ-030 §5.8: Writes LLM response metadata to the reservation row using
    raw SQL UPDATE ... WHERE status = 'held'. Best-effort: catches
    SQLAlchemyError, logs, does not block settlement.
    """

    @pytest.fixture
    def reservation(self) -> UsageReservation:
        """Pre-built held reservation."""
        return _make_held_reservation()

    @pytest.mark.asyncio
    async def test_writes_metadata_to_held_reservation(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """persist_response_metadata() UPDATEs the 4 outbox columns."""
        await service.persist_response_metadata(
            reservation=reservation,
            model=_HAIKU_MODEL,
            input_tokens=1500,
            output_tokens=800,
        )
        mock_db.execute.assert_called()
        # Get the persist call (first execute after the fixture's default)
        call_args = mock_db.execute.call_args_list[-1]
        sql = str(call_args[0][0])
        params = call_args[0][1]

        assert "response_model" in sql
        assert "response_input_tokens" in sql
        assert "response_output_tokens" in sql
        assert "call_completed_at" in sql
        assert "AND status = 'held'" in sql
        assert params["response_model"] == _HAIKU_MODEL
        assert params["input_tokens"] == 1500
        assert params["output_tokens"] == 800
        assert params["id"] == reservation.id

    @pytest.mark.asyncio
    async def test_only_updates_held_reservations(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """SQL includes WHERE status = 'held' guard — prevents writing to
        reservations already handled by the sweep."""
        await service.persist_response_metadata(
            reservation=reservation,
            model=_HAIKU_MODEL,
            input_tokens=100,
            output_tokens=50,
        )
        call_args = mock_db.execute.call_args_list[-1]
        sql = str(call_args[0][0])
        assert "WHERE id = :id AND status = 'held'" in sql

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """SQLAlchemyError is caught — persist failure must not block settle()."""
        mock_db.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db, mock_admin_config)
        # Should not raise
        await service.persist_response_metadata(
            reservation=reservation,
            model=_HAIKU_MODEL,
            input_tokens=100,
            output_tokens=50,
        )

    @pytest.mark.asyncio
    async def test_db_error_logs_error(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Persist DB failure logs error with reservation ID."""
        mock_db.execute.side_effect = SQLAlchemyError(_DB_ERROR_MSG)
        service = MeteringService(mock_db, mock_admin_config)
        with caplog.at_level(logging.ERROR):
            await service.persist_response_metadata(
                reservation=reservation,
                model=_HAIKU_MODEL,
                input_tokens=100,
                output_tokens=50,
            )
        assert any(
            "persist" in r.message.lower() and str(reservation.id) in r.message
            for r in caplog.records
            if r.levelno == logging.ERROR
        )

    @pytest.mark.asyncio
    async def test_does_not_use_savepoint(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """persist_response_metadata() does NOT use begin_nested().

        REQ-030 §5.8: Simple idempotent UPDATE, no savepoint needed —
        must not interfere with the subsequent settle() savepoint.
        """
        await service.persist_response_metadata(
            reservation=reservation,
            model=_HAIKU_MODEL,
            input_tokens=100,
            output_tokens=50,
        )
        mock_db.begin_nested.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_call_completed_at_timestamp(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """call_completed_at is set to a current timestamp."""
        await service.persist_response_metadata(
            reservation=reservation,
            model=_HAIKU_MODEL,
            input_tokens=100,
            output_tokens=50,
        )
        call_args = mock_db.execute.call_args_list[-1]
        params = call_args[0][1]
        assert "completed_at" in params
        assert params["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_zero_output_tokens_accepted(
        self,
        service: MeteringService,
        mock_db: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """Zero output tokens is valid (embeddings produce no output)."""
        await service.persist_response_metadata(
            reservation=reservation,
            model="text-embedding-3-small",
            input_tokens=500,
            output_tokens=0,
        )
        call_args = mock_db.execute.call_args_list[-1]
        params = call_args[0][1]
        assert params["output_tokens"] == 0

    @pytest.mark.asyncio
    async def test_programming_error_propagates(
        self,
        mock_db: AsyncMock,
        mock_admin_config: AsyncMock,
        reservation: UsageReservation,
    ) -> None:
        """AF-07: Programming errors (TypeError, AttributeError) must NOT be
        silently swallowed — they propagate so callers can react.

        Expected DB errors (SQLAlchemyError) are still caught, but a TypeError
        inside the execute indicates a bug that must be surfaced.
        """
        mock_db.execute.side_effect = TypeError(_PROGRAMMING_ERROR_MSG)
        service = MeteringService(mock_db, mock_admin_config)
        with pytest.raises(TypeError, match=_PROGRAMMING_ERROR_MSG):
            await service.persist_response_metadata(
                reservation=reservation,
                model=_HAIKU_MODEL,
                input_tokens=100,
                output_tokens=50,
            )
