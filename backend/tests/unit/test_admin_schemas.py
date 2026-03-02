"""Tests for admin Pydantic schemas.

REQ-022 §10.1–§10.7: Validates request/response schemas for all admin
API resources — model registry, pricing config, task routing, credit packs,
system config, admin users, and cache refresh.
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.admin import (
    AdminUserResponse,
    AdminUserUpdate,
    CacheRefreshResponse,
    CreditPackCreate,
    CreditPackResponse,
    CreditPackUpdate,
    ModelRegistryCreate,
    ModelRegistryResponse,
    ModelRegistryUpdate,
    PricingConfigCreate,
    PricingConfigResponse,
    PricingConfigUpdate,
    SystemConfigResponse,
    SystemConfigUpsert,
    TaskRoutingCreate,
    TaskRoutingResponse,
    TaskRoutingUpdate,
)

# =============================================================================
# Model Registry schemas
# =============================================================================


class TestModelRegistryCreate:
    """ModelRegistryCreate accepts valid data and rejects invalid input."""

    def test_valid_model_creation(self) -> None:
        schema = ModelRegistryCreate(
            provider="claude",
            model="claude-3-5-haiku-20241022",
            display_name="Claude 3.5 Haiku",
            model_type="llm",
        )
        assert schema.provider == "claude"
        assert schema.model == "claude-3-5-haiku-20241022"
        assert schema.display_name == "Claude 3.5 Haiku"
        assert schema.model_type == "llm"

    def test_embedding_model_type(self) -> None:
        schema = ModelRegistryCreate(
            provider="openai",
            model="text-embedding-3-small",
            display_name="Embedding Small",
            model_type="embedding",
        )
        assert schema.model_type == "embedding"

    def test_rejects_invalid_provider(self) -> None:
        with pytest.raises(ValidationError, match="provider"):
            ModelRegistryCreate(
                provider="invalid",
                model="some-model",
                display_name="Some Model",
                model_type="llm",
            )

    def test_rejects_invalid_model_type(self) -> None:
        with pytest.raises(ValidationError, match="model_type"):
            ModelRegistryCreate(
                provider="claude",
                model="some-model",
                display_name="Some Model",
                model_type="invalid",
            )

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ModelRegistryCreate(
                provider="claude",
                model="some-model",
                display_name="Some Model",
                model_type="llm",
                secret="not_allowed",  # type: ignore[call-arg]
            )

    def test_rejects_model_name_over_100_chars(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            ModelRegistryCreate(
                provider="claude",
                model="x" * 101,
                display_name="Some Model",
                model_type="llm",
            )

    def test_accepts_all_valid_providers(self) -> None:
        for provider in ("claude", "openai", "gemini"):
            schema = ModelRegistryCreate(
                provider=provider,
                model="test-model",
                display_name="Test",
                model_type="llm",
            )
            assert schema.provider == provider


class TestModelRegistryUpdate:
    """ModelRegistryUpdate accepts partial updates."""

    def test_partial_update_display_name(self) -> None:
        schema = ModelRegistryUpdate(display_name="New Name")
        assert schema.display_name == "New Name"
        assert schema.is_active is None
        assert schema.model_type is None

    def test_partial_update_is_active(self) -> None:
        schema = ModelRegistryUpdate(is_active=False)
        assert schema.is_active is False

    def test_rejects_invalid_model_type_on_update(self) -> None:
        with pytest.raises(ValidationError, match="model_type"):
            ModelRegistryUpdate(model_type="invalid")

    def test_rejects_display_name_over_100_chars(self) -> None:
        with pytest.raises(ValidationError, match="display_name"):
            ModelRegistryUpdate(display_name="x" * 101)

    def test_accepts_display_name_at_100_chars(self) -> None:
        schema = ModelRegistryUpdate(display_name="x" * 100)
        assert len(schema.display_name) == 100


class TestModelRegistryResponse:
    """ModelRegistryResponse serializes correctly."""

    def test_full_response(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = ModelRegistryResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            provider="claude",
            model="claude-3-5-haiku-20241022",
            display_name="Claude 3.5 Haiku",
            model_type="llm",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert schema.id == "550e8400-e29b-41d4-a716-446655440000"
        assert schema.is_active is True


# =============================================================================
# Pricing Config schemas
# =============================================================================


class TestPricingConfigCreate:
    """PricingConfigCreate validates monetary values as strings."""

    def test_valid_pricing_creation(self) -> None:
        schema = PricingConfigCreate(
            provider="claude",
            model="claude-3-5-haiku-20241022",
            input_cost_per_1k="0.000800",
            output_cost_per_1k="0.004000",
            margin_multiplier="1.30",
            effective_date=date(2026, 3, 1),
        )
        assert schema.input_cost_per_1k == "0.000800"
        assert schema.output_cost_per_1k == "0.004000"
        assert schema.margin_multiplier == "1.30"
        assert schema.effective_date == date(2026, 3, 1)

    def test_rejects_negative_input_cost(self) -> None:
        with pytest.raises(ValidationError, match="input_cost_per_1k"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="-0.001",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_negative_output_cost(self) -> None:
        with pytest.raises(ValidationError, match="output_cost_per_1k"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="0.001",
                output_cost_per_1k="-0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_non_positive_margin(self) -> None:
        with pytest.raises(ValidationError, match="margin_multiplier"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="0.001",
                output_cost_per_1k="0.004",
                margin_multiplier="0",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_non_numeric_cost_string(self) -> None:
        with pytest.raises(ValidationError, match="input_cost_per_1k"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="not_a_number",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_accepts_zero_input_cost(self) -> None:
        schema = PricingConfigCreate(
            provider="openai",
            model="test-model",
            input_cost_per_1k="0",
            output_cost_per_1k="0.004",
            margin_multiplier="1.30",
            effective_date=date(2026, 3, 1),
        )
        assert schema.input_cost_per_1k == "0"

    def test_rejects_invalid_provider(self) -> None:
        with pytest.raises(ValidationError, match="provider"):
            PricingConfigCreate(
                provider="llama",
                model="test-model",
                input_cost_per_1k="0.001",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_model_over_100_chars(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            PricingConfigCreate(
                provider="claude",
                model="x" * 101,
                input_cost_per_1k="0.001",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_infinity_cost(self) -> None:
        with pytest.raises(ValidationError, match="finite"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="Infinity",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_nan_cost(self) -> None:
        with pytest.raises(ValidationError, match="finite"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k="NaN",
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )

    def test_rejects_overly_long_decimal_string(self) -> None:
        long_decimal = "0." + "0" * 30
        with pytest.raises(ValidationError, match="too long"):
            PricingConfigCreate(
                provider="claude",
                model="test-model",
                input_cost_per_1k=long_decimal,
                output_cost_per_1k="0.004",
                margin_multiplier="1.30",
                effective_date=date(2026, 3, 1),
            )


class TestPricingConfigUpdate:
    """PricingConfigUpdate accepts partial updates with validation."""

    def test_partial_update_margin(self) -> None:
        schema = PricingConfigUpdate(margin_multiplier="2.00")
        assert schema.margin_multiplier == "2.00"
        assert schema.input_cost_per_1k is None

    def test_rejects_negative_margin_on_update(self) -> None:
        with pytest.raises(ValidationError, match="margin_multiplier"):
            PricingConfigUpdate(margin_multiplier="-1.0")


class TestPricingConfigResponse:
    """PricingConfigResponse includes is_current computed field."""

    def test_response_with_is_current(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = PricingConfigResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            provider="claude",
            model="claude-3-5-haiku-20241022",
            input_cost_per_1k="0.000800",
            output_cost_per_1k="0.004000",
            margin_multiplier="1.30",
            effective_date=date(2026, 3, 1),
            is_current=True,
            created_at=now,
            updated_at=now,
        )
        assert schema.is_current is True
        assert schema.effective_date == date(2026, 3, 1)


# =============================================================================
# Task Routing schemas
# =============================================================================


class TestTaskRoutingCreate:
    """TaskRoutingCreate validates provider and task_type."""

    def test_valid_routing_creation(self) -> None:
        schema = TaskRoutingCreate(
            provider="claude",
            task_type="extraction",
            model="claude-3-5-haiku-20241022",
        )
        assert schema.provider == "claude"
        assert schema.task_type == "extraction"
        assert schema.model == "claude-3-5-haiku-20241022"

    def test_accepts_default_task_type(self) -> None:
        schema = TaskRoutingCreate(
            provider="openai",
            task_type="_default",
            model="gpt-4o",
        )
        assert schema.task_type == "_default"

    def test_rejects_invalid_provider(self) -> None:
        with pytest.raises(ValidationError, match="provider"):
            TaskRoutingCreate(
                provider="invalid",
                task_type="extraction",
                model="some-model",
            )

    def test_rejects_invalid_task_type(self) -> None:
        with pytest.raises(ValidationError, match="task_type"):
            TaskRoutingCreate(
                provider="claude",
                task_type="not_a_real_task",
                model="some-model",
            )

    def test_rejects_model_over_100_chars(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            TaskRoutingCreate(
                provider="claude",
                task_type="extraction",
                model="x" * 101,
            )

    def test_accepts_all_task_types(self) -> None:
        """All TaskType enum values and '_default' are accepted."""
        from app.providers.llm.base import TaskType

        for task_value in [t.value for t in TaskType]:
            schema = TaskRoutingCreate(
                provider="claude",
                task_type=task_value,
                model="test-model",
            )
            assert schema.task_type == task_value


class TestTaskRoutingUpdate:
    """TaskRoutingUpdate allows model change."""

    def test_update_model(self) -> None:
        schema = TaskRoutingUpdate(model="new-model")
        assert schema.model == "new-model"

    def test_rejects_model_over_100_chars(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            TaskRoutingUpdate(model="x" * 101)


class TestTaskRoutingResponse:
    """TaskRoutingResponse includes optional model_display_name."""

    def test_response_with_display_name(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = TaskRoutingResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            provider="claude",
            task_type="extraction",
            model="claude-3-5-haiku-20241022",
            model_display_name="Claude 3.5 Haiku",
            created_at=now,
            updated_at=now,
        )
        assert schema.model_display_name == "Claude 3.5 Haiku"

    def test_response_without_display_name(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = TaskRoutingResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            provider="claude",
            task_type="_default",
            model="claude-3-5-haiku-20241022",
            model_display_name=None,
            created_at=now,
            updated_at=now,
        )
        assert schema.model_display_name is None


# =============================================================================
# Credit Pack schemas
# =============================================================================


class TestCreditPackCreate:
    """CreditPackCreate validates price and credit amounts."""

    def test_valid_pack_creation(self) -> None:
        schema = CreditPackCreate(
            name="Starter",
            price_cents=500,
            credit_amount=1000,
            display_order=1,
            description="Basic starter pack",
            highlight_label="Popular",
        )
        assert schema.name == "Starter"
        assert schema.price_cents == 500
        assert schema.credit_amount == 1000

    def test_rejects_zero_price_cents(self) -> None:
        with pytest.raises(ValidationError, match="price_cents"):
            CreditPackCreate(
                name="Free",
                price_cents=0,
                credit_amount=100,
            )

    def test_rejects_negative_price_cents(self) -> None:
        with pytest.raises(ValidationError, match="price_cents"):
            CreditPackCreate(
                name="Bad",
                price_cents=-100,
                credit_amount=100,
            )

    def test_rejects_zero_credit_amount(self) -> None:
        with pytest.raises(ValidationError, match="credit_amount"):
            CreditPackCreate(
                name="Empty",
                price_cents=500,
                credit_amount=0,
            )

    def test_rejects_name_over_50_chars(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            CreditPackCreate(
                name="x" * 51,
                price_cents=500,
                credit_amount=1000,
            )

    def test_default_display_order(self) -> None:
        schema = CreditPackCreate(
            name="Basic",
            price_cents=500,
            credit_amount=1000,
        )
        assert schema.display_order == 0

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            CreditPackCreate(
                name="Test",
                price_cents=500,
                credit_amount=1000,
                sneaky_field="nope",  # type: ignore[call-arg]
            )


class TestCreditPackUpdate:
    """CreditPackUpdate accepts partial updates."""

    def test_partial_update_name(self) -> None:
        schema = CreditPackUpdate(name="New Name")
        assert schema.name == "New Name"
        assert schema.price_cents is None

    def test_rejects_zero_price_on_update(self) -> None:
        with pytest.raises(ValidationError, match="price_cents"):
            CreditPackUpdate(price_cents=0)

    def test_rejects_description_over_255_chars(self) -> None:
        with pytest.raises(ValidationError, match="description"):
            CreditPackUpdate(description="x" * 256)

    def test_rejects_highlight_label_over_50_chars(self) -> None:
        with pytest.raises(ValidationError, match="highlight_label"):
            CreditPackUpdate(highlight_label="x" * 51)


class TestCreditPackResponse:
    """CreditPackResponse includes price_display computed value."""

    def test_price_display_formatting(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = CreditPackResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Starter",
            price_cents=500,
            price_display="$5.00",
            credit_amount=1000,
            stripe_price_id=None,
            display_order=1,
            is_active=True,
            description="Basic pack",
            highlight_label=None,
            created_at=now,
            updated_at=now,
        )
        assert schema.price_display == "$5.00"
        assert schema.stripe_price_id is None


# =============================================================================
# System Config schemas
# =============================================================================


class TestSystemConfigUpsert:
    """SystemConfigUpsert validates value and description."""

    def test_valid_upsert(self) -> None:
        schema = SystemConfigUpsert(
            value="100",
            description="Signup grant in credits",
        )
        assert schema.value == "100"
        assert schema.description == "Signup grant in credits"

    def test_upsert_without_description(self) -> None:
        schema = SystemConfigUpsert(value="true")
        assert schema.description is None

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            SystemConfigUpsert(
                value="100",
                key="not_allowed",  # type: ignore[call-arg]
            )

    def test_rejects_value_over_10000_chars(self) -> None:
        with pytest.raises(ValidationError, match="value"):
            SystemConfigUpsert(value="x" * 10_001)

    def test_accepts_value_at_10000_chars(self) -> None:
        schema = SystemConfigUpsert(value="x" * 10_000)
        assert len(schema.value) == 10_000

    def test_rejects_description_over_255_chars(self) -> None:
        with pytest.raises(ValidationError, match="description"):
            SystemConfigUpsert(value="ok", description="x" * 256)


class TestSystemConfigResponse:
    """SystemConfigResponse returns key-value pairs."""

    def test_full_response(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = SystemConfigResponse(
            key="signup_grant_credits",
            value="0",
            description="Credits on signup",
            updated_at=now,
        )
        assert schema.key == "signup_grant_credits"
        assert schema.value == "0"


# =============================================================================
# Admin User schemas
# =============================================================================


class TestAdminUserUpdate:
    """AdminUserUpdate validates is_admin field."""

    def test_set_admin_true(self) -> None:
        schema = AdminUserUpdate(is_admin=True)
        assert schema.is_admin is True

    def test_set_admin_false(self) -> None:
        schema = AdminUserUpdate(is_admin=False)
        assert schema.is_admin is False

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            AdminUserUpdate(
                is_admin=True,
                email="hack@evil.com",  # type: ignore[call-arg]
            )


class TestAdminUserResponse:
    """AdminUserResponse includes computed is_env_protected."""

    def test_full_response(self) -> None:
        now = datetime(2026, 3, 1, 12, 0, 0)
        schema = AdminUserResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="admin@example.com",
            name="Admin User",
            is_admin=True,
            is_env_protected=True,
            balance_usd="10.500000",
            created_at=now,
        )
        assert schema.is_admin is True
        assert schema.is_env_protected is True
        assert schema.balance_usd == "10.500000"


# =============================================================================
# Cache Refresh schema
# =============================================================================


class TestCacheRefreshResponse:
    """CacheRefreshResponse returns message and caching status."""

    def test_cache_not_enabled(self) -> None:
        schema = CacheRefreshResponse(
            message="Cache refresh triggered",
            caching_enabled=False,
        )
        assert schema.message == "Cache refresh triggered"
        assert schema.caching_enabled is False
