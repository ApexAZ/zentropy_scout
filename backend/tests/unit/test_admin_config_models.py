"""Tests for admin config ORM models.

REQ-022 §4.1–§4.6: Verifies ModelRegistry, PricingConfig, TaskRoutingConfig,
CreditPack, and SystemConfig models have correct attributes, defaults,
constraints, and table names. Also verifies User.is_admin extension.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.admin_config import (
    CreditPack,
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)
from app.models.user import User

# ---------------------------------------------------------------------------
# Test constants — match seed data from REQ-022 §12
# ---------------------------------------------------------------------------

_PROVIDER = "claude"
_MODEL = "claude-3-5-haiku-20241022"
_DISPLAY_NAME = "Claude 3.5 Haiku"
_INPUT_COST = Decimal("0.000800")
_OUTPUT_COST = Decimal("0.004000")
_MARGIN = Decimal("1.30")


# ---------------------------------------------------------------------------
# Factory helpers — centralize default values for DB integration tests
# ---------------------------------------------------------------------------


def _make_model_registry(**overrides: object) -> ModelRegistry:
    defaults: dict[str, object] = {
        "provider": _PROVIDER,
        "model": _MODEL,
        "display_name": _DISPLAY_NAME,
    }
    defaults.update(overrides)
    return ModelRegistry(**defaults)


def _make_pricing_config(**overrides: object) -> PricingConfig:
    defaults: dict[str, object] = {
        "provider": _PROVIDER,
        "model": _MODEL,
        "input_cost_per_1k": _INPUT_COST,
        "output_cost_per_1k": _OUTPUT_COST,
        "margin_multiplier": _MARGIN,
        "effective_date": date.today(),
    }
    defaults.update(overrides)
    return PricingConfig(**defaults)


def _make_credit_pack(**overrides: object) -> CreditPack:
    defaults: dict[str, object] = {
        "name": "Starter",
        "price_cents": 500,
        "credit_amount": 50000,
    }
    defaults.update(overrides)
    return CreditPack(**defaults)


# ---------------------------------------------------------------------------
# ModelRegistry (§4.2)
# ---------------------------------------------------------------------------


class TestModelRegistry:
    """ModelRegistry stores the canonical list of available LLM/embedding models."""

    def test_attributes_set_when_constructed_with_valid_data(self) -> None:
        model = ModelRegistry(
            id=uuid.uuid4(),
            provider=_PROVIDER,
            model=_MODEL,
            display_name=_DISPLAY_NAME,
            model_type="llm",
            is_active=True,
        )
        assert model.provider == _PROVIDER
        assert model.model == _MODEL
        assert model.display_name == _DISPLAY_NAME
        assert model.model_type == "llm"
        assert model.is_active is True

    def test_embedding_model_type_accepted(self) -> None:
        model = ModelRegistry(
            id=uuid.uuid4(),
            provider="openai",
            model="text-embedding-3-small",
            display_name="Embedding 3 Small",
            model_type="embedding",
        )
        assert model.model_type == "embedding"


# ---------------------------------------------------------------------------
# PricingConfig (§4.3)
# ---------------------------------------------------------------------------


class TestPricingConfig:
    """PricingConfig stores per-model pricing with effective dates."""

    def test_attributes_set_when_constructed_with_valid_data(self) -> None:
        pricing = PricingConfig(
            id=uuid.uuid4(),
            provider=_PROVIDER,
            model=_MODEL,
            input_cost_per_1k=_INPUT_COST,
            output_cost_per_1k=_OUTPUT_COST,
            margin_multiplier=_MARGIN,
            effective_date=date(2026, 3, 1),
        )
        assert pricing.input_cost_per_1k == _INPUT_COST
        assert pricing.output_cost_per_1k == _OUTPUT_COST
        assert pricing.margin_multiplier == _MARGIN
        assert pricing.effective_date == date(2026, 3, 1)

    def test_decimal_precision_preserved(self) -> None:
        pricing = PricingConfig(
            id=uuid.uuid4(),
            provider="openai",
            model="gpt-4o-mini",
            input_cost_per_1k=Decimal("0.000150"),
            output_cost_per_1k=Decimal("0.000600"),
            margin_multiplier=Decimal("3.00"),
            effective_date=date.today(),
        )
        assert pricing.input_cost_per_1k == Decimal("0.000150")
        assert pricing.margin_multiplier == Decimal("3.00")


# ---------------------------------------------------------------------------
# TaskRoutingConfig (§4.4)
# ---------------------------------------------------------------------------


class TestTaskRoutingConfig:
    """TaskRoutingConfig maps task types to models per provider."""

    def test_attributes_set_when_constructed_with_valid_data(self) -> None:
        routing = TaskRoutingConfig(
            id=uuid.uuid4(),
            provider=_PROVIDER,
            task_type="extraction",
            model=_MODEL,
        )
        assert routing.provider == _PROVIDER
        assert routing.task_type == "extraction"
        assert routing.model == _MODEL

    def test_default_fallback_task_type_accepted(self) -> None:
        routing = TaskRoutingConfig(
            id=uuid.uuid4(),
            provider=_PROVIDER,
            task_type="_default",
            model="claude-3-5-sonnet-20241022",
        )
        assert routing.task_type == "_default"


# ---------------------------------------------------------------------------
# CreditPack (§4.5)
# ---------------------------------------------------------------------------


class TestCreditPack:
    """CreditPack stores admin-configurable credit pack definitions."""

    def test_attributes_set_when_constructed_with_valid_data(self) -> None:
        pack = CreditPack(
            id=uuid.uuid4(),
            name="Starter",
            price_cents=500,
            credit_amount=50000,
            display_order=1,
            is_active=True,
            description="Get started with Zentropy Scout",
        )
        assert pack.name == "Starter"
        assert pack.price_cents == 500
        assert pack.credit_amount == 50000

    def test_stripe_price_id_nullable(self) -> None:
        pack = _make_credit_pack()
        assert pack.stripe_price_id is None

    def test_highlight_label_set_when_provided(self) -> None:
        pack = _make_credit_pack(highlight_label="Most Popular")
        assert pack.highlight_label == "Most Popular"

    def test_description_nullable(self) -> None:
        pack = _make_credit_pack()
        assert pack.description is None


# ---------------------------------------------------------------------------
# SystemConfig (§4.6)
# ---------------------------------------------------------------------------


class TestSystemConfig:
    """SystemConfig is a key-value store for global settings."""

    def test_attributes_set_when_constructed_with_valid_data(self) -> None:
        cfg = SystemConfig(
            key="signup_grant_credits",
            value="0",
            description="Credits granted to new users on signup",
        )
        assert cfg.key == "signup_grant_credits"
        assert cfg.value == "0"
        assert cfg.description == "Credits granted to new users on signup"

    def test_description_nullable(self) -> None:
        cfg = SystemConfig(key="test_key", value="test_val")
        assert cfg.description is None


# ---------------------------------------------------------------------------
# User.is_admin (§4.1)
# ---------------------------------------------------------------------------


class TestUserIsAdmin:
    """User model extended with is_admin boolean column."""

    def test_is_admin_can_be_set_true(self) -> None:
        user = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            is_admin=True,
        )
        assert user.is_admin is True

    def test_is_admin_can_be_set_false(self) -> None:
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            is_admin=False,
        )
        assert user.is_admin is False


# ---------------------------------------------------------------------------
# Database integration — verify defaults, constraints, uniqueness (§4.1–§4.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdminConfigModelsDB:
    """Integration tests verifying server defaults and constraints with real DB."""

    async def test_model_registry_persists_and_reads_back(self, db_session) -> None:
        model = _make_model_registry()
        db_session.add(model)
        await db_session.flush()
        assert model.id is not None
        assert model.created_at is not None
        assert model.updated_at is not None

    async def test_model_registry_server_defaults(self, db_session) -> None:
        """model_type defaults to 'llm', is_active defaults to True via server."""
        model = _make_model_registry()
        db_session.add(model)
        await db_session.flush()
        await db_session.refresh(model)
        assert model.model_type == "llm"
        assert model.is_active is True

    async def test_model_registry_rejects_duplicate_provider_model(
        self, db_session
    ) -> None:
        db_session.add(_make_model_registry())
        await db_session.flush()
        db_session.add(_make_model_registry(display_name="Duplicate"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_model_registry_rejects_invalid_model_type(self, db_session) -> None:
        """model_type must be 'llm' or 'embedding'."""
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO model_registry "
                    "(id, provider, model, display_name, model_type) "
                    "VALUES (gen_random_uuid(), 'test', 'test-model', "
                    "'Test', 'invalid')"
                )
            )

    async def test_pricing_config_persists_with_correct_types(self, db_session) -> None:
        pricing = _make_pricing_config()
        db_session.add(pricing)
        await db_session.flush()
        assert pricing.id is not None
        assert pricing.created_at is not None

    async def test_pricing_config_rejects_negative_margin(self, db_session) -> None:
        """margin_multiplier must be positive."""
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO pricing_config "
                    "(id, provider, model, input_cost_per_1k, output_cost_per_1k, "
                    "margin_multiplier, effective_date) "
                    "VALUES (gen_random_uuid(), 'test', 'test', 0.001, 0.001, "
                    "-1.0, CURRENT_DATE)"
                )
            )

    async def test_pricing_config_rejects_negative_input_cost(self, db_session) -> None:
        """input_cost_per_1k must be non-negative."""
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO pricing_config "
                    "(id, provider, model, input_cost_per_1k, output_cost_per_1k, "
                    "margin_multiplier, effective_date) "
                    "VALUES (gen_random_uuid(), 'test', 'test', -0.001, 0.001, "
                    "1.30, CURRENT_DATE)"
                )
            )

    async def test_pricing_config_rejects_duplicate_provider_model_date(
        self, db_session
    ) -> None:
        db_session.add(_make_pricing_config())
        await db_session.flush()
        db_session.add(
            _make_pricing_config(
                input_cost_per_1k=Decimal("0.001000"),
                margin_multiplier=Decimal("1.50"),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_credit_pack_server_defaults(self, db_session) -> None:
        """display_order defaults to 0, is_active defaults to True via server."""
        pack = _make_credit_pack()
        db_session.add(pack)
        await db_session.flush()
        await db_session.refresh(pack)
        assert pack.display_order == 0
        assert pack.is_active is True

    async def test_credit_pack_rejects_zero_price(self, db_session) -> None:
        """price_cents must be > 0."""
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO credit_packs "
                    "(id, name, price_cents, credit_amount) "
                    "VALUES (gen_random_uuid(), 'Free', 0, 1000)"
                )
            )

    async def test_credit_pack_rejects_zero_credit_amount(self, db_session) -> None:
        """credit_amount must be > 0."""
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO credit_packs "
                    "(id, name, price_cents, credit_amount) "
                    "VALUES (gen_random_uuid(), 'Empty', 500, 0)"
                )
            )

    async def test_system_config_persists_with_key_pk(self, db_session) -> None:
        """SystemConfig uses key as PK — persists and reads back by key."""
        cfg = SystemConfig(key="test_setting", value="42")
        db_session.add(cfg)
        await db_session.flush()
        assert cfg.created_at is not None
        assert cfg.key == "test_setting"

    async def test_user_is_admin_server_default_false(self, db_session) -> None:
        """User.is_admin defaults to False when persisted without explicit value."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        assert user.is_admin is False

    async def test_task_routing_rejects_duplicate_provider_task(
        self, db_session
    ) -> None:
        r1 = TaskRoutingConfig(
            provider=_PROVIDER,
            task_type="extraction",
            model=_MODEL,
        )
        r2 = TaskRoutingConfig(
            provider=_PROVIDER,
            task_type="extraction",
            model="claude-3-5-sonnet-20241022",
        )
        db_session.add(r1)
        await db_session.flush()
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
