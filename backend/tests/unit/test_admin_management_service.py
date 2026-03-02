"""Tests for AdminManagementService — CRUD operations.

REQ-022 §10.1–§10.7: Business logic for all admin CRUD operations including
validation rules and error codes per §14.

Integration tests using real DB (db_session fixture).
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.admin_config import (
    CreditPack,
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)
from app.models.user import User
from app.services.admin_management_service import AdminManagementService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)

_PROVIDER = "claude"
_PROVIDER_OPENAI = "openai"
_MODEL_HAIKU = "claude-3-5-haiku-20241022"
_MODEL_SONNET = "claude-3-5-sonnet-20241022"
_MODEL_GPT4O = "gpt-4o"
_TASK_EXTRACTION = "extraction"
_ADMIN_EMAIL = "admin@test.com"
_TARGET_EMAIL = "target@test.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(
    provider: str = _PROVIDER,
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


def _make_pricing(
    provider: str = _PROVIDER,
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
    provider: str = _PROVIDER,
    task_type: str = _TASK_EXTRACTION,
    model: str = _MODEL_HAIKU,
) -> TaskRoutingConfig:
    """Create a TaskRoutingConfig row for testing."""
    return TaskRoutingConfig(provider=provider, task_type=task_type, model=model)


def _make_pack(
    name: str = "Starter",
    price_cents: int = 500,
    credit_amount: int = 50000,
    display_order: int = 0,
    is_active: bool = True,
) -> CreditPack:
    """Create a CreditPack row for testing."""
    return CreditPack(
        name=name,
        price_cents=price_cents,
        credit_amount=credit_amount,
        display_order=display_order,
        is_active=is_active,
    )


def _make_user(
    email: str = "admin@example.com",
    is_admin: bool = True,
    user_id: uuid.UUID | None = None,
) -> User:
    """Create a User row for testing."""
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        is_admin=is_admin,
    )


# ===========================================================================
# Model Registry CRUD
# ===========================================================================


@pytest.mark.asyncio
class TestListModels:
    """AdminManagementService.list_models filtering."""

    async def test_returns_all_models(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model(model=_MODEL_HAIKU))
        db_session.add(_make_model(model=_MODEL_SONNET, display_name="Sonnet"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_models()

        assert len(results) == 2

    async def test_filters_by_provider(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model(provider="claude"))
        db_session.add(
            _make_model(
                provider=_PROVIDER_OPENAI, model=_MODEL_GPT4O, display_name="GPT-4o"
            )
        )
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_models(provider="claude")

        assert len(results) == 1
        assert results[0].provider == "claude"

    async def test_filters_by_model_type(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model(model_type="llm"))
        db_session.add(
            _make_model(
                model="text-embedding-3-small",
                display_name="Embedding",
                model_type="embedding",
            )
        )
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_models(model_type="embedding")

        assert len(results) == 1
        assert results[0].model_type == "embedding"

    async def test_filters_by_is_active(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model(is_active=True))
        db_session.add(
            _make_model(model=_MODEL_SONNET, display_name="Sonnet", is_active=False)
        )
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_models(is_active=False)

        assert len(results) == 1
        assert results[0].is_active is False


@pytest.mark.asyncio
class TestCreateModel:
    """AdminManagementService.create_model validation."""

    async def test_creates_model_successfully(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        result = await svc.create_model(
            provider="claude",
            model="claude-4-opus",
            display_name="Claude 4 Opus",
            model_type="llm",
        )

        assert result.provider == "claude"
        assert result.model == "claude-4-opus"
        assert result.display_name == "Claude 4 Opus"
        assert result.model_type == "llm"
        assert result.is_active is True
        assert result.id is not None

    async def test_duplicate_model_raises_conflict(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(ConflictError) as exc_info:
            await svc.create_model(
                provider=_PROVIDER,
                model=_MODEL_HAIKU,
                display_name="Duplicate",
                model_type="llm",
            )
        assert exc_info.value.code == "DUPLICATE_MODEL"


@pytest.mark.asyncio
class TestUpdateModel:
    """AdminManagementService.update_model."""

    async def test_updates_display_name(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        models = await svc.list_models()
        result = await svc.update_model(models[0].id, display_name="Updated Name")

        assert result.display_name == "Updated Name"

    async def test_updates_is_active(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        models = await svc.list_models()
        result = await svc.update_model(models[0].id, is_active=False)

        assert result.is_active is False

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.update_model(uuid.uuid4(), display_name="Nope")


@pytest.mark.asyncio
class TestDeleteModel:
    """AdminManagementService.delete_model with cascade protection."""

    async def test_deletes_unreferenced_model(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        models = await svc.list_models()
        await svc.delete_model(models[0].id)

        remaining = await svc.list_models()
        assert len(remaining) == 0

    async def test_model_in_use_raises_conflict(self, db_session: AsyncSession) -> None:
        """Cannot delete model referenced by task_routing_config."""
        db_session.add(_make_model())
        db_session.add(_make_routing(model=_MODEL_HAIKU))
        await db_session.flush()
        svc = AdminManagementService(db_session)

        models = await svc.list_models()
        with pytest.raises(ConflictError) as exc_info:
            await svc.delete_model(models[0].id)
        assert exc_info.value.code == "MODEL_IN_USE"

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.delete_model(uuid.uuid4())


# ===========================================================================
# Pricing Config CRUD
# ===========================================================================


@pytest.mark.asyncio
class TestListPricing:
    """AdminManagementService.list_pricing with is_current computation."""

    async def test_returns_all_pricing(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pricing(effective=_TODAY))
        db_session.add(_make_pricing(effective=_YESTERDAY, margin="2.00"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_pricing()

        assert len(results) == 2

    async def test_is_current_set_on_latest_effective(
        self, db_session: AsyncSession
    ) -> None:
        """The pricing with latest effective_date <= today gets is_current=True."""
        db_session.add(_make_pricing(effective=_YESTERDAY, margin="2.00"))
        db_session.add(_make_pricing(effective=_TODAY, margin="1.30"))
        db_session.add(_make_pricing(effective=_TOMORROW, margin="3.00"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_pricing()

        # Find the one for today — it should be current
        current = [r for r in results if r["is_current"] is True]
        assert len(current) == 1
        assert current[0]["effective_date"] == _TODAY

    async def test_filters_by_provider(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pricing(provider="claude"))
        db_session.add(_make_pricing(provider=_PROVIDER_OPENAI, model=_MODEL_GPT4O))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_pricing(provider="claude")

        assert len(results) == 1


@pytest.mark.asyncio
class TestCreatePricing:
    """AdminManagementService.create_pricing validation."""

    async def test_creates_pricing_for_registered_model(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        await db_session.flush()

        svc = AdminManagementService(db_session)
        result = await svc.create_pricing(
            provider=_PROVIDER,
            model=_MODEL_HAIKU,
            input_cost_per_1k=Decimal("0.000800"),
            output_cost_per_1k=Decimal("0.004000"),
            margin_multiplier=Decimal("1.30"),
            effective_date=_TODAY,
        )

        assert result.provider == _PROVIDER
        assert result.model == _MODEL_HAIKU

    async def test_model_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError, match="Model"):
            await svc.create_pricing(
                provider=_PROVIDER,
                model="nonexistent-model",
                input_cost_per_1k=Decimal("0.001"),
                output_cost_per_1k=Decimal("0.001"),
                margin_multiplier=Decimal("1.30"),
                effective_date=_TODAY,
            )

    async def test_duplicate_pricing_raises_conflict(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        db_session.add(_make_pricing(effective=_TODAY))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(ConflictError) as exc_info:
            await svc.create_pricing(
                provider=_PROVIDER,
                model=_MODEL_HAIKU,
                input_cost_per_1k=Decimal("0.001"),
                output_cost_per_1k=Decimal("0.001"),
                margin_multiplier=Decimal("1.50"),
                effective_date=_TODAY,
            )
        assert exc_info.value.code == "DUPLICATE_PRICING"


@pytest.mark.asyncio
class TestUpdatePricing:
    """AdminManagementService.update_pricing."""

    async def test_updates_margin(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pricing())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        pricing = await svc.list_pricing()
        result = await svc.update_pricing(
            uuid.UUID(pricing[0]["id"]),
            margin_multiplier=Decimal("2.50"),
        )

        assert result.margin_multiplier == Decimal("2.50")

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.update_pricing(uuid.uuid4(), margin_multiplier=Decimal("1.00"))


@pytest.mark.asyncio
class TestDeletePricing:
    """AdminManagementService.delete_pricing with last-pricing guard."""

    async def test_deletes_non_last_pricing(self, db_session: AsyncSession) -> None:
        """Can delete a pricing entry if another current one exists."""
        db_session.add(_make_model())
        db_session.add(_make_pricing(effective=_YESTERDAY, margin="2.00"))
        db_session.add(_make_pricing(effective=_TODAY, margin="1.30"))
        await db_session.flush()
        svc = AdminManagementService(db_session)

        pricing = await svc.list_pricing()
        yesterday_entry = [p for p in pricing if p["effective_date"] == _YESTERDAY][0]
        await svc.delete_pricing(uuid.UUID(yesterday_entry["id"]))

        remaining = await svc.list_pricing()
        assert len(remaining) == 1

    async def test_last_pricing_for_active_model_raises_conflict(
        self, db_session: AsyncSession
    ) -> None:
        """Cannot delete the only current pricing for an active model."""
        db_session.add(_make_model(is_active=True))
        db_session.add(_make_pricing(effective=_TODAY))
        await db_session.flush()
        svc = AdminManagementService(db_session)

        pricing = await svc.list_pricing()
        with pytest.raises(ConflictError) as exc_info:
            await svc.delete_pricing(uuid.UUID(pricing[0]["id"]))
        assert exc_info.value.code == "LAST_PRICING"

    async def test_can_delete_pricing_for_inactive_model(
        self, db_session: AsyncSession
    ) -> None:
        """Can delete last pricing if the model is inactive."""
        db_session.add(_make_model(is_active=False))
        db_session.add(_make_pricing(effective=_TODAY))
        await db_session.flush()
        svc = AdminManagementService(db_session)

        pricing = await svc.list_pricing()
        await svc.delete_pricing(uuid.UUID(pricing[0]["id"]))

        remaining = await svc.list_pricing()
        assert len(remaining) == 0

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.delete_pricing(uuid.uuid4())


# ===========================================================================
# Task Routing CRUD
# ===========================================================================


@pytest.mark.asyncio
class TestListRouting:
    """AdminManagementService.list_routing with display_name join."""

    async def test_returns_routing_with_display_name(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        db_session.add(_make_routing())
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_routing()

        assert len(results) == 1
        assert results[0]["model_display_name"] == "Claude 3.5 Haiku"

    async def test_filters_by_provider(self, db_session: AsyncSession) -> None:
        db_session.add(_make_routing(provider="claude"))
        db_session.add(
            _make_routing(
                provider=_PROVIDER_OPENAI,
                model=_MODEL_GPT4O,
                task_type=_TASK_EXTRACTION,
            )
        )
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_routing(provider="claude")

        assert len(results) == 1


@pytest.mark.asyncio
class TestCreateRouting:
    """AdminManagementService.create_routing validation."""

    async def test_creates_routing_for_active_model(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        await db_session.flush()

        svc = AdminManagementService(db_session)
        result = await svc.create_routing(
            provider=_PROVIDER,
            task_type=_TASK_EXTRACTION,
            model=_MODEL_HAIKU,
        )

        assert result.task_type == _TASK_EXTRACTION
        assert result.model == _MODEL_HAIKU

    async def test_inactive_model_raises_not_found(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model(is_active=False))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError, match="Model"):
            await svc.create_routing(
                provider=_PROVIDER,
                task_type=_TASK_EXTRACTION,
                model=_MODEL_HAIKU,
            )

    async def test_unregistered_model_raises_not_found(
        self, db_session: AsyncSession
    ) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError, match="Model"):
            await svc.create_routing(
                provider=_PROVIDER,
                task_type=_TASK_EXTRACTION,
                model="nonexistent",
            )

    async def test_duplicate_routing_raises_conflict(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(_make_model())
        db_session.add(_make_routing())
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(ConflictError) as exc_info:
            await svc.create_routing(
                provider=_PROVIDER,
                task_type=_TASK_EXTRACTION,
                model=_MODEL_HAIKU,
            )
        assert exc_info.value.code == "DUPLICATE_ROUTING"


@pytest.mark.asyncio
class TestUpdateRouting:
    """AdminManagementService.update_routing."""

    async def test_updates_model(self, db_session: AsyncSession) -> None:
        db_session.add(_make_model(model=_MODEL_SONNET, display_name="Sonnet"))
        db_session.add(_make_routing())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        routing = await svc.list_routing()
        result = await svc.update_routing(
            uuid.UUID(routing[0]["id"]),
            model=_MODEL_SONNET,
        )

        assert result.model == _MODEL_SONNET

    async def test_update_rejects_unregistered_model(
        self, db_session: AsyncSession
    ) -> None:
        """Cannot update routing to point at an unregistered model."""
        db_session.add(_make_routing())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        routing = await svc.list_routing()
        with pytest.raises(NotFoundError, match="Model"):
            await svc.update_routing(
                uuid.UUID(routing[0]["id"]),
                model="nonexistent-model",
            )

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.update_routing(uuid.uuid4(), model="test")


@pytest.mark.asyncio
class TestDeleteRouting:
    """AdminManagementService.delete_routing."""

    async def test_deletes_routing(self, db_session: AsyncSession) -> None:
        db_session.add(_make_routing())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        routing = await svc.list_routing()
        await svc.delete_routing(uuid.UUID(routing[0]["id"]))

        remaining = await svc.list_routing()
        assert len(remaining) == 0

    async def test_not_found_raises_404(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.delete_routing(uuid.uuid4())


# ===========================================================================
# Credit Packs CRUD
# ===========================================================================


@pytest.mark.asyncio
class TestCreditPacks:
    """AdminManagementService credit pack operations."""

    async def test_list_packs_returns_all(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pack(name="Starter"))
        db_session.add(_make_pack(name="Pro", price_cents=2000, credit_amount=250000))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_packs()

        assert len(results) == 2

    async def test_create_pack(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        result = await svc.create_pack(
            name="Standard",
            price_cents=1000,
            credit_amount=125000,
            display_order=1,
        )

        assert result.name == "Standard"
        assert result.price_cents == 1000
        assert result.credit_amount == 125000
        assert result.is_active is True

    async def test_update_pack(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pack())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        packs = await svc.list_packs()
        result = await svc.update_pack(packs[0].id, is_active=False)

        assert result.is_active is False

    async def test_update_pack_clears_description_when_none(
        self, db_session: AsyncSession
    ) -> None:
        """Passing description=None explicitly clears the field."""
        pack = _make_pack()
        pack.description = "Original description"
        db_session.add(pack)
        await db_session.flush()
        svc = AdminManagementService(db_session)

        packs = await svc.list_packs()
        result = await svc.update_pack(packs[0].id, description=None)

        assert result.description is None

    async def test_update_pack_preserves_description_when_omitted(
        self, db_session: AsyncSession
    ) -> None:
        """Not passing description at all preserves existing value."""
        pack = _make_pack()
        pack.description = "Original description"
        db_session.add(pack)
        await db_session.flush()
        svc = AdminManagementService(db_session)

        packs = await svc.list_packs()
        result = await svc.update_pack(packs[0].id, name="Renamed")

        assert result.description == "Original description"

    async def test_update_pack_not_found(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.update_pack(uuid.uuid4(), name="Nope")

    async def test_delete_pack(self, db_session: AsyncSession) -> None:
        db_session.add(_make_pack())
        await db_session.flush()
        svc = AdminManagementService(db_session)

        packs = await svc.list_packs()
        await svc.delete_pack(packs[0].id)

        remaining = await svc.list_packs()
        assert len(remaining) == 0

    async def test_delete_pack_not_found(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.delete_pack(uuid.uuid4())


# ===========================================================================
# System Config CRUD
# ===========================================================================


@pytest.mark.asyncio
class TestSystemConfig:
    """AdminManagementService system config operations."""

    async def test_list_config(self, db_session: AsyncSession) -> None:
        db_session.add(SystemConfig(key="signup_grant_credits", value="0"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        results = await svc.list_config()

        assert len(results) == 1
        assert results[0].key == "signup_grant_credits"

    async def test_upsert_creates_new_key(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        result = await svc.upsert_config(
            key="new_key",
            value="new_value",
            description="A new config",
        )

        assert result.key == "new_key"
        assert result.value == "new_value"
        assert result.description == "A new config"

    async def test_upsert_updates_existing_key(self, db_session: AsyncSession) -> None:
        db_session.add(
            SystemConfig(key="existing", value="old", description="Old desc")
        )
        await db_session.flush()

        svc = AdminManagementService(db_session)
        result = await svc.upsert_config(
            key="existing",
            value="new",
            description="New desc",
        )

        assert result.value == "new"
        assert result.description == "New desc"

    async def test_delete_config(self, db_session: AsyncSession) -> None:
        db_session.add(SystemConfig(key="to_delete", value="val"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        await svc.delete_config("to_delete")

        results = await svc.list_config()
        assert len(results) == 0

    async def test_delete_config_not_found(self, db_session: AsyncSession) -> None:
        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.delete_config("nonexistent")


# ===========================================================================
# Admin Users
# ===========================================================================


@pytest.mark.asyncio
class TestListUsers:
    """AdminManagementService.list_users with pagination."""

    async def test_returns_users_with_pagination(
        self, db_session: AsyncSession
    ) -> None:
        for i in range(3):
            db_session.add(_make_user(email=f"user{i}@test.com"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        users, total = await svc.list_users(page=1, per_page=2)

        assert len(users) == 2
        assert total == 3

    async def test_page_2_returns_remainder(self, db_session: AsyncSession) -> None:
        for i in range(3):
            db_session.add(_make_user(email=f"user{i}@test.com"))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        users, total = await svc.list_users(page=2, per_page=2)

        assert len(users) == 1
        assert total == 3

    async def test_filters_by_is_admin(self, db_session: AsyncSession) -> None:
        db_session.add(_make_user(email=_ADMIN_EMAIL, is_admin=True))
        db_session.add(_make_user(email="regular@test.com", is_admin=False))
        await db_session.flush()

        svc = AdminManagementService(db_session)
        users, total = await svc.list_users(is_admin=True)

        assert total == 1
        assert users[0].is_admin is True


@pytest.mark.asyncio
class TestToggleAdmin:
    """AdminManagementService.toggle_admin validation."""

    async def test_promotes_user_to_admin(self, db_session: AsyncSession) -> None:
        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        target = _make_user(email=_TARGET_EMAIL, is_admin=False)
        db_session.add_all([admin, target])
        await db_session.flush()

        svc = AdminManagementService(db_session)
        result = await svc.toggle_admin(
            admin_user_id=admin.id,
            target_user_id=target.id,
            is_admin=True,
        )

        assert result.is_admin is True

    async def test_sets_token_invalidated_before(
        self, db_session: AsyncSession
    ) -> None:
        """Admin toggle sets token_invalidated_before to force JWT refresh."""
        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        target = _make_user(email=_TARGET_EMAIL, is_admin=False)
        db_session.add_all([admin, target])
        await db_session.flush()

        assert target.token_invalidated_before is None

        svc = AdminManagementService(db_session)
        await svc.toggle_admin(
            admin_user_id=admin.id,
            target_user_id=target.id,
            is_admin=True,
        )

        # Refresh to get updated value
        await db_session.refresh(target)
        assert target.token_invalidated_before is not None

    async def test_cannot_demote_self(self, db_session: AsyncSession) -> None:
        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        db_session.add(admin)
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(ConflictError) as exc_info:
            await svc.toggle_admin(
                admin_user_id=admin.id,
                target_user_id=admin.id,
                is_admin=False,
            )
        assert exc_info.value.code == "CANNOT_DEMOTE_SELF"

    async def test_self_promote_is_allowed(self, db_session: AsyncSession) -> None:
        """Setting is_admin=True on yourself is not a demotion — it's fine."""
        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        db_session.add(admin)
        await db_session.flush()

        svc = AdminManagementService(db_session)
        result = await svc.toggle_admin(
            admin_user_id=admin.id,
            target_user_id=admin.id,
            is_admin=True,
        )

        assert result.is_admin is True

    async def test_cannot_demote_env_protected_admin(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cannot demote admin whose email is in ADMIN_EMAILS."""
        from app.core import config as config_module

        monkeypatch.setattr(
            config_module.settings, "admin_emails", "protected@test.com"
        )

        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        target = _make_user(email="protected@test.com", is_admin=True)
        db_session.add_all([admin, target])
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(ConflictError) as exc_info:
            await svc.toggle_admin(
                admin_user_id=admin.id,
                target_user_id=target.id,
                is_admin=False,
            )
        assert exc_info.value.code == "ADMIN_EMAILS_PROTECTED"

    async def test_target_not_found_raises_404(self, db_session: AsyncSession) -> None:
        admin = _make_user(email=_ADMIN_EMAIL, is_admin=True)
        db_session.add(admin)
        await db_session.flush()

        svc = AdminManagementService(db_session)
        with pytest.raises(NotFoundError):
            await svc.toggle_admin(
                admin_user_id=admin.id,
                target_user_id=uuid.uuid4(),
                is_admin=True,
            )
