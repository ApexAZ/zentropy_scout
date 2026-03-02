"""Integration tests for admin pricing pipeline.

REQ-022 §15.2–§15.3: End-to-end tests verifying the full admin pricing
pipeline — model registry → pricing config → task routing → metering →
cost calculation → balance debit. Uses real PostgreSQL database.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NoPricingConfigError, UnregisteredModelError
from app.models.admin_config import (
    ModelRegistry,
    PricingConfig,
    TaskRoutingConfig,
)
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.user import User
from app.providers.llm.base import LLMResponse, TaskType
from app.providers.metered_provider import MeteredLLMProvider
from app.services.admin_config_service import AdminConfigService
from app.services.metering_service import MeteringService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_LAST_WEEK = _TODAY - timedelta(days=7)
_TOMORROW = _TODAY + timedelta(days=1)

_PROVIDER = "claude"
_MODEL_HAIKU = "claude-3-5-haiku-20241022"
_MODEL_SONNET = "claude-3-5-sonnet-20241022"
_TEST_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000099")

# Standard pricing values for tests
_HAIKU_INPUT = Decimal("0.000800")
_HAIKU_OUTPUT = Decimal("0.004000")
_SONNET_INPUT = Decimal("0.003000")
_SONNET_OUTPUT = Decimal("0.015000")

# Repeated literals extracted as constants
_TASK_EXTRACTION = "extraction"
_TASK_COVER_LETTER = "cover_letter"
_MARGIN_DEFAULT = Decimal("1.30")
_MARGIN_HIGH = Decimal("2.00")
_INITIAL_BALANCE = Decimal("100.000000")
_BALANCE_QUERY = "SELECT balance_usd FROM users WHERE id = :uid"
_MODEL_OVERRIDE_KEY = "model_override"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_model(
    db: AsyncSession,
    provider: str = _PROVIDER,
    model: str = _MODEL_HAIKU,
    display_name: str = "Claude 3.5 Haiku",
    is_active: bool = True,
) -> ModelRegistry:
    """Insert a model registry entry."""
    row = ModelRegistry(
        provider=provider,
        model=model,
        display_name=display_name,
        is_active=is_active,
    )
    db.add(row)
    await db.flush()
    return row


async def _seed_pricing(
    db: AsyncSession,
    provider: str = _PROVIDER,
    model: str = _MODEL_HAIKU,
    input_cost: Decimal = _HAIKU_INPUT,
    output_cost: Decimal = _HAIKU_OUTPUT,
    margin: Decimal = _MARGIN_DEFAULT,
    effective: date = _TODAY,
) -> PricingConfig:
    """Insert a pricing config entry."""
    row = PricingConfig(
        provider=provider,
        model=model,
        input_cost_per_1k=input_cost,
        output_cost_per_1k=output_cost,
        margin_multiplier=margin,
        effective_date=effective,
    )
    db.add(row)
    await db.flush()
    return row


async def _seed_routing(
    db: AsyncSession,
    provider: str = _PROVIDER,
    task_type: str = _TASK_EXTRACTION,
    model: str = _MODEL_HAIKU,
) -> TaskRoutingConfig:
    """Insert a task routing config entry."""
    row = TaskRoutingConfig(
        provider=provider,
        task_type=task_type,
        model=model,
    )
    db.add(row)
    await db.flush()
    return row


async def _seed_user(
    db: AsyncSession,
    user_id: uuid.UUID = _TEST_USER_ID,
    email: str = "pipeline-test@example.com",
    balance: Decimal = _INITIAL_BALANCE,
    is_admin: bool = False,
) -> User:
    """Insert a test user with a specified balance."""
    user = User(
        id=user_id,
        email=email,
        balance_usd=balance,
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    return user


def _mock_llm_response(
    model: str = _MODEL_HAIKU,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> LLMResponse:
    """Create a mock LLMResponse for metered provider tests."""
    return LLMResponse(
        content="Test response",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish_reason="stop",
        latency_ms=100.0,
    )


def _make_services(
    db: AsyncSession,
) -> tuple[MeteringService, AdminConfigService]:
    """Create MeteringService and AdminConfigService for a given session."""
    admin_config = AdminConfigService(db)
    return MeteringService(db, admin_config), admin_config


def _mock_inner_adapter(
    model: str = _MODEL_HAIKU,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> AsyncMock:
    """Create a mocked inner LLM adapter with provider_name and complete()."""
    inner = AsyncMock()
    inner.provider_name = _PROVIDER
    inner.complete.return_value = _mock_llm_response(model, input_tokens, output_tokens)
    return inner


# ===========================================================================
# Pricing Pipeline — MeteringService with real DB
# ===========================================================================


@pytest.mark.asyncio
class TestPricingPipeline:
    """MeteringService cost calculation with real DB pricing."""

    async def test_registered_model_with_pricing_calculates_cost(
        self, db_session: AsyncSession
    ) -> None:
        """Full pipeline: model in registry + pricing → cost calculation works."""
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=_MARGIN_DEFAULT)

        svc, _ = _make_services(db_session)
        raw, billed = await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)

        # raw = (1000 * 0.000800 + 500 * 0.004000) / 1000 = (0.8 + 2.0) / 1000 = 0.0028
        assert raw == Decimal("0.0028")
        # billed = 0.0028 * 1.30 = 0.00364
        assert billed == Decimal("0.00364")

    async def test_unregistered_model_raises_error(
        self, db_session: AsyncSession
    ) -> None:
        """Model not in registry raises UnregisteredModelError."""
        svc, _ = _make_services(db_session)

        with pytest.raises(UnregisteredModelError):
            await svc.calculate_cost(_PROVIDER, "nonexistent-model", 1000, 500)

    async def test_inactive_model_raises_error(self, db_session: AsyncSession) -> None:
        """Inactive model treated as unregistered."""
        await _seed_model(db_session, is_active=False)
        await _seed_pricing(db_session)

        svc, _ = _make_services(db_session)

        with pytest.raises(UnregisteredModelError):
            await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)

    async def test_registered_model_without_pricing_raises_error(
        self, db_session: AsyncSession
    ) -> None:
        """Model in registry but no effective pricing raises NoPricingConfigError."""
        await _seed_model(db_session)
        # No pricing entry created

        svc, _ = _make_services(db_session)

        with pytest.raises(NoPricingConfigError):
            await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)

    async def test_future_pricing_only_raises_error(
        self, db_session: AsyncSession
    ) -> None:
        """Model with only future-dated pricing has no effective pricing."""
        await _seed_model(db_session)
        await _seed_pricing(db_session, effective=_TOMORROW)

        svc, _ = _make_services(db_session)

        with pytest.raises(NoPricingConfigError):
            await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)


# ===========================================================================
# Per-model margins
# ===========================================================================


@pytest.mark.asyncio
class TestPerModelMargins:
    """Different models bill at different margins."""

    async def test_cheap_model_high_margin(self, db_session: AsyncSession) -> None:
        """Haiku with 3.0x margin bills higher relative to raw cost."""
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=Decimal("3.00"))

        svc, _ = _make_services(db_session)
        raw, billed = await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)

        assert billed == raw * Decimal("3.00")

    async def test_expensive_model_low_margin(self, db_session: AsyncSession) -> None:
        """Sonnet with 1.1x margin bills lower relative to raw cost."""
        await _seed_model(db_session, model=_MODEL_SONNET, display_name="Sonnet")
        await _seed_pricing(
            db_session,
            model=_MODEL_SONNET,
            input_cost=_SONNET_INPUT,
            output_cost=_SONNET_OUTPUT,
            margin=Decimal("1.10"),
        )

        svc, _ = _make_services(db_session)
        raw, billed = await svc.calculate_cost(_PROVIDER, _MODEL_SONNET, 1000, 500)

        assert billed == raw * Decimal("1.10")

    async def test_margins_produce_different_billed_costs(
        self, db_session: AsyncSession
    ) -> None:
        """Same raw cost formula but different margins → different billed costs."""
        # Register both models with the SAME pricing but different margins
        await _seed_model(db_session, model=_MODEL_HAIKU)
        await _seed_model(db_session, model=_MODEL_SONNET, display_name="Sonnet")
        await _seed_pricing(db_session, model=_MODEL_HAIKU, margin=Decimal("3.00"))
        await _seed_pricing(db_session, model=_MODEL_SONNET, margin=Decimal("1.10"))

        svc, _ = _make_services(db_session)
        _, billed_haiku = await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)
        _, billed_sonnet = await svc.calculate_cost(_PROVIDER, _MODEL_SONNET, 1000, 500)

        assert billed_haiku > billed_sonnet


# ===========================================================================
# Effective date transitions
# ===========================================================================


@pytest.mark.asyncio
class TestEffectiveDateTransitions:
    """Pricing effective date logic in the full pipeline."""

    async def test_picks_most_recent_past_pricing(
        self, db_session: AsyncSession
    ) -> None:
        """Multiple past effective dates: the most recent one is used."""
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=_MARGIN_HIGH, effective=_LAST_WEEK)
        await _seed_pricing(db_session, margin=Decimal("1.50"), effective=_YESTERDAY)

        svc, _ = _make_services(db_session)
        raw, billed = await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)

        # Should use yesterday's pricing (margin 1.50)
        assert billed == raw * Decimal("1.50")

    async def test_effective_date_transition_via_mock(
        self, db_session: AsyncSession
    ) -> None:
        """Create future pricing, mock date forward, verify new pricing takes effect."""
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=_MARGIN_DEFAULT, effective=_TODAY)
        await _seed_pricing(db_session, margin=_MARGIN_HIGH, effective=_TOMORROW)

        svc, _ = _make_services(db_session)

        # Today: should use margin 1.30
        raw_today, billed_today = await svc.calculate_cost(
            _PROVIDER, _MODEL_HAIKU, 1000, 500
        )
        assert billed_today == raw_today * _MARGIN_DEFAULT

        # Mock date to tomorrow: should use margin 2.00
        future = _TOMORROW
        with patch("app.services.admin_config_service.date") as mock_date:
            mock_date.today.return_value = future
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            raw_future, billed_future = await svc.calculate_cost(
                _PROVIDER, _MODEL_HAIKU, 1000, 500
            )

        assert billed_future == raw_future * _MARGIN_HIGH


# ===========================================================================
# Record and debit — full pipeline
# ===========================================================================


@pytest.mark.asyncio
class TestRecordAndDebit:
    """MeteringService.record_and_debit creates records and debits balance."""

    async def test_creates_usage_record_and_transaction(
        self, db_session: AsyncSession
    ) -> None:
        """record_and_debit inserts LLMUsageRecord + CreditTransaction."""
        user = await _seed_user(db_session)
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=_MARGIN_DEFAULT)

        svc, _ = _make_services(db_session)
        await svc.record_and_debit(
            user_id=user.id,
            provider=_PROVIDER,
            model=_MODEL_HAIKU,
            task_type=_TASK_EXTRACTION,
            input_tokens=1000,
            output_tokens=500,
        )
        await db_session.flush()

        # Verify usage record exists
        usage_result = await db_session.execute(
            select(LLMUsageRecord).where(LLMUsageRecord.user_id == user.id)
        )
        usage = usage_result.scalar_one()
        assert usage.provider == _PROVIDER
        assert usage.model == _MODEL_HAIKU
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.margin_multiplier == _MARGIN_DEFAULT

        # Verify transaction exists
        txn_result = await db_session.execute(
            select(CreditTransaction).where(CreditTransaction.user_id == user.id)
        )
        txn = txn_result.scalar_one()
        assert txn.transaction_type == "usage_debit"
        assert txn.amount_usd < 0  # Debit is negative

    async def test_debits_user_balance(self, db_session: AsyncSession) -> None:
        """record_and_debit reduces the user's balance."""
        user = await _seed_user(db_session, balance=_INITIAL_BALANCE)
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=_MARGIN_DEFAULT)

        svc, _ = _make_services(db_session)
        await svc.record_and_debit(
            user_id=user.id,
            provider=_PROVIDER,
            model=_MODEL_HAIKU,
            task_type=_TASK_EXTRACTION,
            input_tokens=1000,
            output_tokens=500,
        )
        await db_session.flush()

        # Re-read user balance
        result = await db_session.execute(text(_BALANCE_QUERY), {"uid": user.id})
        new_balance = result.scalar_one()
        assert new_balance < _INITIAL_BALANCE

    async def test_per_model_margin_in_usage_record(
        self, db_session: AsyncSession
    ) -> None:
        """Usage record stores the per-model margin from DB pricing."""
        user = await _seed_user(db_session)
        await _seed_model(db_session)
        await _seed_pricing(db_session, margin=Decimal("2.50"))

        svc, _ = _make_services(db_session)
        await svc.record_and_debit(
            user_id=user.id,
            provider=_PROVIDER,
            model=_MODEL_HAIKU,
            task_type=_TASK_EXTRACTION,
            input_tokens=100,
            output_tokens=50,
        )
        await db_session.flush()

        result = await db_session.execute(
            select(LLMUsageRecord).where(LLMUsageRecord.user_id == user.id)
        )
        usage = result.scalar_one()
        assert usage.margin_multiplier == Decimal("2.50")


# ===========================================================================
# Task routing — MeteredLLMProvider with real DB
# ===========================================================================


@pytest.mark.asyncio
class TestRoutingPipeline:
    """MeteredLLMProvider resolves routing from DB and passes model_override."""

    async def test_routing_exact_match_passes_model_override(
        self, db_session: AsyncSession
    ) -> None:
        """MeteredLLMProvider resolves exact routing and passes to inner adapter."""
        user = await _seed_user(db_session)
        await _seed_model(db_session, model=_MODEL_HAIKU)
        await _seed_pricing(db_session, model=_MODEL_HAIKU)
        await _seed_routing(db_session, task_type=_TASK_EXTRACTION, model=_MODEL_HAIKU)

        inner = _mock_inner_adapter(model=_MODEL_HAIKU)

        metering, admin_config = _make_services(db_session)
        provider = MeteredLLMProvider(inner, metering, admin_config, user.id)

        await provider.complete([], TaskType.EXTRACTION)

        # Verify inner.complete was called with model_override from DB routing
        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] == _MODEL_HAIKU

    async def test_routing_fallback_to_default(self, db_session: AsyncSession) -> None:
        """No exact routing falls back to _default entry."""
        user = await _seed_user(db_session)
        await _seed_model(db_session, model=_MODEL_SONNET, display_name="Sonnet")
        await _seed_pricing(db_session, model=_MODEL_SONNET)
        await _seed_routing(db_session, task_type="_default", model=_MODEL_SONNET)

        inner = _mock_inner_adapter(model=_MODEL_SONNET)

        metering, admin_config = _make_services(db_session)
        provider = MeteredLLMProvider(inner, metering, admin_config, user.id)

        # cover_letter has no exact routing → falls back to _default
        await provider.complete([], TaskType.COVER_LETTER)

        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] == _MODEL_SONNET

    async def test_routing_none_passes_none_override(
        self, db_session: AsyncSession
    ) -> None:
        """No routing at all passes model_override=None (adapter uses hardcoded)."""
        user = await _seed_user(db_session)
        await _seed_model(db_session, model=_MODEL_HAIKU)
        await _seed_pricing(db_session, model=_MODEL_HAIKU)
        # No routing entries

        inner = _mock_inner_adapter(model=_MODEL_HAIKU)

        metering, admin_config = _make_services(db_session)
        provider = MeteredLLMProvider(inner, metering, admin_config, user.id)

        await provider.complete([], TaskType.EXTRACTION)

        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] is None

    async def test_routing_override_changes_model_used(
        self, db_session: AsyncSession
    ) -> None:
        """Changing routing config changes which model the adapter receives."""
        user = await _seed_user(db_session)
        # Register both models
        await _seed_model(db_session, model=_MODEL_HAIKU)
        await _seed_model(db_session, model=_MODEL_SONNET, display_name="Sonnet")
        await _seed_pricing(db_session, model=_MODEL_HAIKU)
        await _seed_pricing(db_session, model=_MODEL_SONNET)

        # Route extraction to Haiku initially
        routing = await _seed_routing(
            db_session, task_type=_TASK_EXTRACTION, model=_MODEL_HAIKU
        )

        inner = _mock_inner_adapter(model=_MODEL_HAIKU)

        metering, admin_config = _make_services(db_session)
        provider = MeteredLLMProvider(inner, metering, admin_config, user.id)

        await provider.complete([], TaskType.EXTRACTION)
        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] == _MODEL_HAIKU

        # Change routing to Sonnet
        routing.model = _MODEL_SONNET
        await db_session.flush()

        inner.complete.return_value = _mock_llm_response(model=_MODEL_SONNET)
        await provider.complete([], TaskType.EXTRACTION)
        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] == _MODEL_SONNET


# ===========================================================================
# Model deactivation blocks pipeline
# ===========================================================================


@pytest.mark.asyncio
class TestModelDeactivation:
    """Deactivating a model blocks metering but routing still resolves."""

    async def test_deactivated_model_blocks_metering(
        self, db_session: AsyncSession
    ) -> None:
        """Deactivating a model causes UnregisteredModelError in metering."""
        model = await _seed_model(db_session, is_active=True)
        await _seed_pricing(db_session)

        svc, _ = _make_services(db_session)

        # Works while active
        raw, billed = await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)
        assert billed > 0

        # Deactivate
        model.is_active = False
        await db_session.flush()

        # Now blocked
        with pytest.raises(UnregisteredModelError):
            await svc.calculate_cost(_PROVIDER, _MODEL_HAIKU, 1000, 500)


# ===========================================================================
# Full admin CRUD → metering pipeline
# ===========================================================================


@pytest.mark.asyncio
class TestFullAdminPipeline:
    """Admin creates model → pricing → routing → metering uses new config."""

    async def test_admin_creates_config_then_metering_uses_it(
        self, db_session: AsyncSession
    ) -> None:
        """Full flow: seed new model + pricing + routing, verify metering works."""
        user = await _seed_user(db_session)

        # Simulate admin creating a new model config
        new_model = "claude-4-opus-20260201"
        await _seed_model(db_session, model=new_model, display_name="Claude 4 Opus")
        await _seed_pricing(
            db_session,
            model=new_model,
            input_cost=Decimal("0.010000"),
            output_cost=Decimal("0.030000"),
            margin=Decimal("1.20"),
        )
        await _seed_routing(db_session, task_type=_TASK_COVER_LETTER, model=new_model)

        # Verify metering calculates correctly with new config
        svc, admin_config = _make_services(db_session)
        raw, billed = await svc.calculate_cost(_PROVIDER, new_model, 2000, 1000)

        # raw = (2000 * 0.010000 + 1000 * 0.030000) / 1000 = (20 + 30) / 1000 = 0.05
        assert raw == Decimal("0.05")
        assert billed == raw * Decimal("1.20")

        # Verify routing resolves to the new model
        routed = await admin_config.get_model_for_task(_PROVIDER, _TASK_COVER_LETTER)
        assert routed == new_model

        # Verify record_and_debit works end-to-end
        await svc.record_and_debit(
            user_id=user.id,
            provider=_PROVIDER,
            model=new_model,
            task_type=_TASK_COVER_LETTER,
            input_tokens=2000,
            output_tokens=1000,
        )
        await db_session.flush()

        # User balance decreased
        result = await db_session.execute(text(_BALANCE_QUERY), {"uid": user.id})
        balance = result.scalar_one()
        assert balance < _INITIAL_BALANCE

    async def test_metered_provider_full_pipeline(
        self, db_session: AsyncSession
    ) -> None:
        """MeteredLLMProvider: routing → adapter call → metering → debit."""
        user = await _seed_user(db_session, balance=Decimal("50.000000"))
        await _seed_model(db_session, model=_MODEL_HAIKU)
        await _seed_pricing(db_session, model=_MODEL_HAIKU, margin=_MARGIN_HIGH)
        await _seed_routing(db_session, task_type=_TASK_EXTRACTION, model=_MODEL_HAIKU)

        inner = _mock_inner_adapter(
            model=_MODEL_HAIKU, input_tokens=500, output_tokens=200
        )

        metering, admin_config = _make_services(db_session)
        provider = MeteredLLMProvider(inner, metering, admin_config, user.id)

        response = await provider.complete([], TaskType.EXTRACTION)
        await db_session.flush()

        # Response returned
        assert response.content == "Test response"
        assert response.model == _MODEL_HAIKU

        # Routing resolved correctly
        assert inner.complete.call_args.kwargs[_MODEL_OVERRIDE_KEY] == _MODEL_HAIKU

        # Usage recorded with correct margin
        result = await db_session.execute(
            select(LLMUsageRecord).where(LLMUsageRecord.user_id == user.id)
        )
        usage = result.scalar_one()
        assert usage.margin_multiplier == _MARGIN_HIGH

        # Balance decreased
        balance_result = await db_session.execute(
            text(_BALANCE_QUERY), {"uid": user.id}
        )
        balance = balance_result.scalar_one()
        assert balance < Decimal("50.000000")
