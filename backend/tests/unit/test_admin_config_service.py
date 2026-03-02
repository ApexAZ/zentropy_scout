"""Tests for AdminConfigService — read-side config lookups.

REQ-022 §6.1–§6.3: Pricing lookup with effective dates, routing
lookup with fallback, model registration check, system config.

Integration tests using real DB (db_session fixture).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import (
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)
from app.services.admin_config_service import AdminConfigService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_LAST_WEEK = _TODAY - timedelta(days=7)
_TOMORROW = _TODAY + timedelta(days=1)

_PROVIDER_CLAUDE = "claude"
_MODEL_HAIKU = "claude-3-5-haiku-20241022"
_MODEL_SONNET = "claude-3-5-sonnet-20241022"
_TASK_EXTRACTION = "extraction"
_CONFIG_KEY_SIGNUP = "signup_grant_credits"
_MISSING_KEY = "nonexistent_key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pricing(
    provider: str = _PROVIDER_CLAUDE,
    model: str = _MODEL_HAIKU,
    input_cost: str = "0.000800",
    output_cost: str = "0.004000",
    margin: str = "1.30",
    effective: date = _TODAY,
) -> PricingConfig:
    """Create a PricingConfig row for testing."""
    return PricingConfig(
        provider=provider,
        model=model,
        input_cost_per_1k=Decimal(input_cost),
        output_cost_per_1k=Decimal(output_cost),
        margin_multiplier=Decimal(margin),
        effective_date=effective,
    )


def _make_routing(
    provider: str = _PROVIDER_CLAUDE,
    task_type: str = _TASK_EXTRACTION,
    model: str = _MODEL_HAIKU,
) -> TaskRoutingConfig:
    """Create a TaskRoutingConfig row for testing."""
    return TaskRoutingConfig(
        provider=provider,
        task_type=task_type,
        model=model,
    )


def _make_model(
    provider: str = _PROVIDER_CLAUDE,
    model: str = _MODEL_HAIKU,
    display_name: str = "Claude 3.5 Haiku",
    model_type: str = "llm",
    is_active: bool = True,
) -> ModelRegistry:
    """Create a ModelRegistry row for testing."""
    return ModelRegistry(
        provider=provider,
        model=model,
        display_name=display_name,
        model_type=model_type,
        is_active=is_active,
    )


# ===========================================================================
# Pricing — effective date logic
# ===========================================================================


@pytest.mark.asyncio
class TestGetPricing:
    """AdminConfigService.get_pricing effective date scenarios."""

    async def test_exact_match_today(self, db_session: AsyncSession) -> None:
        """Pricing with effective_date == today is returned."""
        db_session.add(_make_pricing(effective=_TODAY))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is not None
        assert result.input_cost_per_1k == Decimal("0.000800")
        assert result.output_cost_per_1k == Decimal("0.004000")
        assert result.margin_multiplier == Decimal("1.30")
        assert result.effective_date == _TODAY

    async def test_past_effective_date_returned(self, db_session: AsyncSession) -> None:
        """Pricing from a past date is returned when no newer entry exists."""
        db_session.add(_make_pricing(effective=_LAST_WEEK))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is not None
        assert result.effective_date == _LAST_WEEK

    async def test_future_effective_date_not_used(
        self, db_session: AsyncSession
    ) -> None:
        """Pricing with effective_date in the future is NOT returned."""
        db_session.add(_make_pricing(effective=_TOMORROW))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is None

    async def test_picks_most_recent_effective_date(
        self, db_session: AsyncSession
    ) -> None:
        """When multiple effective dates exist, the most recent <= today wins."""
        db_session.add(_make_pricing(effective=_LAST_WEEK, margin="2.00"))
        db_session.add(_make_pricing(effective=_YESTERDAY, margin="1.50"))
        db_session.add(_make_pricing(effective=_TOMORROW, margin="3.00"))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is not None
        assert result.effective_date == _YESTERDAY
        assert result.margin_multiplier == Decimal("1.50")

    async def test_no_pricing_returns_none(self, db_session: AsyncSession) -> None:
        """Returns None when no pricing exists for the model."""
        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, "nonexistent-model")

        assert result is None

    async def test_different_provider_not_matched(
        self, db_session: AsyncSession
    ) -> None:
        """Pricing for a different provider is not returned."""
        db_session.add(
            _make_pricing(provider="openai", model="gpt-4o", effective=_TODAY)
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, "gpt-4o")

        assert result is None

    async def test_result_is_frozen_dataclass(self, db_session: AsyncSession) -> None:
        """PricingResult is immutable (frozen dataclass)."""
        db_session.add(_make_pricing(effective=_TODAY))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_pricing(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is not None
        # Verify immutability through the public API
        from dataclasses import replace

        updated = replace(result, margin_multiplier=Decimal("9.99"))
        assert result.margin_multiplier == Decimal("1.30")  # Original unchanged
        assert updated.margin_multiplier == Decimal("9.99")  # Copy has new value


# ===========================================================================
# Routing — exact match + fallback
# ===========================================================================


@pytest.mark.asyncio
class TestGetModelForTask:
    """AdminConfigService.get_model_for_task routing scenarios."""

    async def test_exact_match_returns_model(self, db_session: AsyncSession) -> None:
        """Exact (provider, task_type) match returns the routed model."""
        db_session.add(
            _make_routing(
                provider=_PROVIDER_CLAUDE,
                task_type=_TASK_EXTRACTION,
                model=_MODEL_HAIKU,
            )
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_model_for_task(_PROVIDER_CLAUDE, _TASK_EXTRACTION)

        assert result == _MODEL_HAIKU

    async def test_fallback_to_default(self, db_session: AsyncSession) -> None:
        """Falls back to (provider, '_default') when no exact match."""
        db_session.add(
            _make_routing(
                provider=_PROVIDER_CLAUDE, task_type="_default", model=_MODEL_SONNET
            )
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_model_for_task(_PROVIDER_CLAUDE, "cover_letter")

        assert result == _MODEL_SONNET

    async def test_exact_match_preferred_over_default(
        self, db_session: AsyncSession
    ) -> None:
        """Exact match is used even when _default also exists."""
        db_session.add(
            _make_routing(
                provider=_PROVIDER_CLAUDE,
                task_type=_TASK_EXTRACTION,
                model=_MODEL_HAIKU,
            )
        )
        db_session.add(
            _make_routing(
                provider=_PROVIDER_CLAUDE, task_type="_default", model=_MODEL_SONNET
            )
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_model_for_task(_PROVIDER_CLAUDE, _TASK_EXTRACTION)

        assert result == _MODEL_HAIKU

    async def test_no_routing_returns_none(self, db_session: AsyncSession) -> None:
        """Returns None when no routing exists for provider + task_type."""
        svc = AdminConfigService(db_session)
        result = await svc.get_model_for_task(_PROVIDER_CLAUDE, _TASK_EXTRACTION)

        assert result is None

    async def test_different_provider_not_matched(
        self, db_session: AsyncSession
    ) -> None:
        """Routing for a different provider is not returned."""
        db_session.add(
            _make_routing(
                provider="openai", task_type=_TASK_EXTRACTION, model="gpt-4o-mini"
            )
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_model_for_task(_PROVIDER_CLAUDE, _TASK_EXTRACTION)

        assert result is None


# ===========================================================================
# Model registration check
# ===========================================================================


@pytest.mark.asyncio
class TestIsModelRegistered:
    """AdminConfigService.is_model_registered scenarios."""

    async def test_active_model_returns_true(self, db_session: AsyncSession) -> None:
        """Active registered model returns True."""
        db_session.add(_make_model(is_active=True))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.is_model_registered(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is True

    async def test_inactive_model_returns_false(self, db_session: AsyncSession) -> None:
        """Inactive model returns False (treated as unregistered)."""
        db_session.add(_make_model(is_active=False))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.is_model_registered(_PROVIDER_CLAUDE, _MODEL_HAIKU)

        assert result is False

    async def test_unregistered_model_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        """Model not in registry returns False."""
        svc = AdminConfigService(db_session)
        result = await svc.is_model_registered(_PROVIDER_CLAUDE, "nonexistent-model")

        assert result is False

    async def test_different_provider_not_matched(
        self, db_session: AsyncSession
    ) -> None:
        """Model registered under a different provider returns False."""
        db_session.add(_make_model(provider="openai", model="gpt-4o"))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.is_model_registered(_PROVIDER_CLAUDE, "gpt-4o")

        assert result is False


# ===========================================================================
# System config
# ===========================================================================


@pytest.mark.asyncio
class TestGetSystemConfig:
    """AdminConfigService.get_system_config scenarios."""

    async def test_existing_key_returns_value(self, db_session: AsyncSession) -> None:
        """Existing config key returns its value."""
        db_session.add(
            SystemConfig(
                key=_CONFIG_KEY_SIGNUP, value="1000", description="Initial grant"
            )
        )
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_system_config(_CONFIG_KEY_SIGNUP)

        assert result == "1000"

    async def test_missing_key_returns_default(self, db_session: AsyncSession) -> None:
        """Missing key returns the default value."""
        svc = AdminConfigService(db_session)
        result = await svc.get_system_config(_MISSING_KEY, default="fallback")

        assert result == "fallback"

    async def test_missing_key_returns_none_when_no_default(
        self, db_session: AsyncSession
    ) -> None:
        """Missing key with no default returns None."""
        svc = AdminConfigService(db_session)
        result = await svc.get_system_config(_MISSING_KEY)

        assert result is None


@pytest.mark.asyncio
class TestGetSystemConfigInt:
    """AdminConfigService.get_system_config_int scenarios."""

    async def test_parses_int_correctly(self, db_session: AsyncSession) -> None:
        """Integer string value is parsed to int."""
        db_session.add(SystemConfig(key=_CONFIG_KEY_SIGNUP, value="5000"))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_system_config_int(_CONFIG_KEY_SIGNUP)

        assert result == 5000

    async def test_missing_key_returns_int_default(
        self, db_session: AsyncSession
    ) -> None:
        """Missing key returns the integer default."""
        svc = AdminConfigService(db_session)
        result = await svc.get_system_config_int(_MISSING_KEY, default=42)

        assert result == 42

    async def test_default_int_is_zero(self, db_session: AsyncSession) -> None:
        """Default int value is 0 when not specified."""
        svc = AdminConfigService(db_session)
        result = await svc.get_system_config_int(_MISSING_KEY)

        assert result == 0

    async def test_non_numeric_value_returns_default(
        self, db_session: AsyncSession
    ) -> None:
        """Non-numeric string value returns the default."""
        db_session.add(SystemConfig(key="bad_value", value="not_a_number"))
        await db_session.flush()

        svc = AdminConfigService(db_session)
        result = await svc.get_system_config_int("bad_value", default=99)

        assert result == 99
