"""Admin management service — CRUD operations.

REQ-022 §10.1–§10.7: Business logic for all admin write operations including
validation rules and error codes per §14.

This is the WRITE-SIDE service used only by admin endpoints. The READ-SIDE
service (AdminConfigService) is separate and used by the metering pipeline.
"""

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.models.admin_config import (
    CreditPack,
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)
from app.models.user import User

logger = logging.getLogger(__name__)


class AdminManagementService:
    """CRUD operations for admin-managed configuration.

    REQ-022 §10: Provides create/read/update/delete for model registry,
    pricing config, task routing, credit packs, system config, and admin users.

    Args:
        db: Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -----------------------------------------------------------------------
    # Model Registry
    # -----------------------------------------------------------------------

    async def list_models(
        self,
        *,
        provider: str | None = None,
        model_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[ModelRegistry]:
        """List registered models with optional filters.

        Args:
            provider: Filter by provider identifier.
            model_type: Filter by model type ('llm' or 'embedding').
            is_active: Filter by active status.

        Returns:
            List of ModelRegistry rows.
        """
        stmt = select(ModelRegistry)
        if provider is not None:
            stmt = stmt.where(ModelRegistry.provider == provider)
        if model_type is not None:
            stmt = stmt.where(ModelRegistry.model_type == model_type)
        if is_active is not None:
            stmt = stmt.where(ModelRegistry.is_active == is_active)
        stmt = stmt.order_by(ModelRegistry.provider, ModelRegistry.model)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def create_model(
        self,
        *,
        provider: str,
        model: str,
        display_name: str,
        model_type: str,
    ) -> ModelRegistry:
        """Register a new model.

        Args:
            provider: Provider identifier.
            model: Model identifier.
            display_name: Human-friendly display name.
            model_type: 'llm' or 'embedding'.

        Returns:
            Created ModelRegistry row.

        Raises:
            ConflictError: DUPLICATE_MODEL if (provider, model) exists.
        """
        existing = await self._db.execute(
            select(ModelRegistry.id).where(
                ModelRegistry.provider == provider,
                ModelRegistry.model == model,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                code="DUPLICATE_MODEL",
                message=f"Model '{model}' already registered for provider '{provider}'",
            )

        row = ModelRegistry(
            provider=provider,
            model=model,
            display_name=display_name,
            model_type=model_type,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_model(
        self,
        model_id: uuid.UUID,
        *,
        display_name: str | None = None,
        is_active: bool | None = None,
        model_type: str | None = None,
    ) -> ModelRegistry:
        """Update model properties.

        Args:
            model_id: UUID of the model to update.
            display_name: New display name.
            is_active: New active status.
            model_type: New model type.

        Returns:
            Updated ModelRegistry row.

        Raises:
            NotFoundError: If model not found.
        """
        row = await self._db.get(ModelRegistry, model_id)
        if row is None:
            raise NotFoundError("Model", str(model_id))

        if display_name is not None:
            row.display_name = display_name
        if is_active is not None:
            row.is_active = is_active
        if model_type is not None:
            row.model_type = model_type

        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def delete_model(self, model_id: uuid.UUID) -> None:
        """Delete a model from the registry.

        Args:
            model_id: UUID of the model to delete.

        Raises:
            NotFoundError: If model not found.
            ConflictError: MODEL_IN_USE if referenced by task_routing_config.
        """
        row = await self._db.get(ModelRegistry, model_id)
        if row is None:
            raise NotFoundError("Model", str(model_id))

        # Check for routing references
        routing_ref = await self._db.execute(
            select(TaskRoutingConfig.id)
            .where(
                TaskRoutingConfig.provider == row.provider,
                TaskRoutingConfig.model == row.model,
            )
            .limit(1)
        )
        if routing_ref.scalar_one_or_none() is not None:
            raise ConflictError(
                code="MODEL_IN_USE",
                message=f"Model '{row.model}' is referenced by task routing config",
            )

        await self._db.delete(row)
        await self._db.flush()

    # -----------------------------------------------------------------------
    # Pricing Config
    # -----------------------------------------------------------------------

    async def list_pricing(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """List pricing entries with computed is_current flag.

        Args:
            provider: Filter by provider.
            model: Filter by model.

        Returns:
            List of dicts with pricing fields + is_current boolean.
        """
        stmt = select(PricingConfig)
        if provider is not None:
            stmt = stmt.where(PricingConfig.provider == provider)
        if model is not None:
            stmt = stmt.where(PricingConfig.model == model)
        stmt = stmt.order_by(
            PricingConfig.provider,
            PricingConfig.model,
            PricingConfig.effective_date.desc(),
        )

        result = await self._db.execute(stmt)
        rows = list(result.scalars().all())

        # Compute is_current: for each (provider, model), the entry with
        # the latest effective_date <= today is "current"
        today = date.today()
        current_ids: set[uuid.UUID] = set()
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (row.provider, row.model)
            if key not in seen and row.effective_date <= today:
                current_ids.add(row.id)
                seen.add(key)

        return [
            {
                "id": str(row.id),
                "provider": row.provider,
                "model": row.model,
                "input_cost_per_1k": row.input_cost_per_1k,
                "output_cost_per_1k": row.output_cost_per_1k,
                "margin_multiplier": row.margin_multiplier,
                "effective_date": row.effective_date,
                "is_current": row.id in current_ids,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    async def create_pricing(
        self,
        *,
        provider: str,
        model: str,
        input_cost_per_1k: Decimal,
        output_cost_per_1k: Decimal,
        margin_multiplier: Decimal,
        effective_date: date,
    ) -> PricingConfig:
        """Add a pricing entry.

        Args:
            provider: Provider identifier.
            model: Model identifier (must exist in registry).
            input_cost_per_1k: Cost per 1K input tokens.
            output_cost_per_1k: Cost per 1K output tokens.
            margin_multiplier: Per-model margin.
            effective_date: Date pricing becomes active.

        Returns:
            Created PricingConfig row.

        Raises:
            NotFoundError: MODEL_NOT_FOUND if model not in registry.
            ConflictError: DUPLICATE_PRICING if same triple exists.
        """
        # Validate model exists in registry
        model_exists = await self._db.execute(
            select(ModelRegistry.id).where(
                ModelRegistry.provider == provider,
                ModelRegistry.model == model,
            )
        )
        if model_exists.scalar_one_or_none() is None:
            raise NotFoundError("Model", f"{provider}/{model}")

        # Check for duplicate
        dup = await self._db.execute(
            select(PricingConfig.id).where(
                PricingConfig.provider == provider,
                PricingConfig.model == model,
                PricingConfig.effective_date == effective_date,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(
                code="DUPLICATE_PRICING",
                message=(
                    f"Pricing for '{model}' on {effective_date} "
                    f"already exists for provider '{provider}'"
                ),
            )

        row = PricingConfig(
            provider=provider,
            model=model,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
            margin_multiplier=margin_multiplier,
            effective_date=effective_date,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_pricing(
        self,
        pricing_id: uuid.UUID,
        *,
        input_cost_per_1k: Decimal | None = None,
        output_cost_per_1k: Decimal | None = None,
        margin_multiplier: Decimal | None = None,
    ) -> PricingConfig:
        """Update a pricing entry.

        Args:
            pricing_id: UUID of pricing entry.
            input_cost_per_1k: New input cost.
            output_cost_per_1k: New output cost.
            margin_multiplier: New margin.

        Returns:
            Updated PricingConfig row.

        Raises:
            NotFoundError: If pricing not found.
        """
        row = await self._db.get(PricingConfig, pricing_id)
        if row is None:
            raise NotFoundError("Pricing", str(pricing_id))

        if input_cost_per_1k is not None:
            row.input_cost_per_1k = input_cost_per_1k
        if output_cost_per_1k is not None:
            row.output_cost_per_1k = output_cost_per_1k
        if margin_multiplier is not None:
            row.margin_multiplier = margin_multiplier

        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def delete_pricing(self, pricing_id: uuid.UUID) -> None:
        """Delete a pricing entry.

        Args:
            pricing_id: UUID of pricing entry.

        Raises:
            NotFoundError: If pricing not found.
            ConflictError: LAST_PRICING if this is the only current pricing
                for an active model.
        """
        row = await self._db.get(PricingConfig, pricing_id)
        if row is None:
            raise NotFoundError("Pricing", str(pricing_id))

        # Check if this is the last current pricing for an active model
        today = date.today()
        if row.effective_date <= today:
            # Is the model active?
            model_result = await self._db.execute(
                select(ModelRegistry.is_active).where(
                    ModelRegistry.provider == row.provider,
                    ModelRegistry.model == row.model,
                )
            )
            model_active = model_result.scalar_one_or_none()

            if model_active is True:
                # Count other current pricing entries for this model
                other_current = await self._db.execute(
                    select(func.count())
                    .select_from(PricingConfig)
                    .where(
                        PricingConfig.provider == row.provider,
                        PricingConfig.model == row.model,
                        PricingConfig.effective_date <= today,
                        PricingConfig.id != pricing_id,
                    )
                )
                if other_current.scalar() == 0:
                    raise ConflictError(
                        code="LAST_PRICING",
                        message=(
                            f"Cannot delete the only current pricing for "
                            f"active model '{row.model}'"
                        ),
                    )

        await self._db.delete(row)
        await self._db.flush()

    # -----------------------------------------------------------------------
    # Task Routing
    # -----------------------------------------------------------------------

    async def list_routing(
        self,
        *,
        provider: str | None = None,
    ) -> list[dict]:
        """List routing entries with model display_name.

        Args:
            provider: Filter by provider.

        Returns:
            List of dicts with routing fields + model_display_name.
        """
        stmt = select(
            TaskRoutingConfig,
            ModelRegistry.display_name.label("model_display_name"),
        ).outerjoin(
            ModelRegistry,
            (TaskRoutingConfig.provider == ModelRegistry.provider)
            & (TaskRoutingConfig.model == ModelRegistry.model),
        )
        if provider is not None:
            stmt = stmt.where(TaskRoutingConfig.provider == provider)
        stmt = stmt.order_by(TaskRoutingConfig.provider, TaskRoutingConfig.task_type)

        result = await self._db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(routing.id),
                "provider": routing.provider,
                "task_type": routing.task_type,
                "model": routing.model,
                "model_display_name": display_name,
                "created_at": routing.created_at,
                "updated_at": routing.updated_at,
            }
            for routing, display_name in rows
        ]

    async def create_routing(
        self,
        *,
        provider: str,
        task_type: str,
        model: str,
    ) -> TaskRoutingConfig:
        """Add a routing entry.

        Args:
            provider: Provider identifier.
            task_type: TaskType enum value or '_default'.
            model: Target model (must be registered and active).

        Returns:
            Created TaskRoutingConfig row.

        Raises:
            NotFoundError: MODEL_NOT_FOUND if model not in registry or inactive.
            ConflictError: DUPLICATE_ROUTING if (provider, task_type) exists.
        """
        # Validate model is registered and active
        model_check = await self._db.execute(
            select(ModelRegistry.id).where(
                ModelRegistry.provider == provider,
                ModelRegistry.model == model,
                ModelRegistry.is_active.is_(True),
            )
        )
        if model_check.scalar_one_or_none() is None:
            raise NotFoundError("Model", f"{provider}/{model}")

        # Check for duplicate
        dup = await self._db.execute(
            select(TaskRoutingConfig.id).where(
                TaskRoutingConfig.provider == provider,
                TaskRoutingConfig.task_type == task_type,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(
                code="DUPLICATE_ROUTING",
                message=(
                    f"Routing for task '{task_type}' already exists "
                    f"for provider '{provider}'"
                ),
            )

        row = TaskRoutingConfig(
            provider=provider,
            task_type=task_type,
            model=model,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_routing(
        self,
        routing_id: uuid.UUID,
        *,
        model: str | None = None,
    ) -> TaskRoutingConfig:
        """Update routing (change target model).

        Args:
            routing_id: UUID of routing entry.
            model: New target model.

        Returns:
            Updated TaskRoutingConfig row.

        Raises:
            NotFoundError: If routing not found or model not registered/active.
        """
        row = await self._db.get(TaskRoutingConfig, routing_id)
        if row is None:
            raise NotFoundError("Routing", str(routing_id))

        if model is not None:
            # Validate model is registered and active (same as create_routing)
            model_check = await self._db.execute(
                select(ModelRegistry.id).where(
                    ModelRegistry.provider == row.provider,
                    ModelRegistry.model == model,
                    ModelRegistry.is_active.is_(True),
                )
            )
            if model_check.scalar_one_or_none() is None:
                raise NotFoundError("Model", f"{row.provider}/{model}")
            row.model = model

        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def delete_routing(self, routing_id: uuid.UUID) -> None:
        """Delete a routing entry.

        Args:
            routing_id: UUID of routing entry.

        Raises:
            NotFoundError: If routing not found.
        """
        row = await self._db.get(TaskRoutingConfig, routing_id)
        if row is None:
            raise NotFoundError("Routing", str(routing_id))

        await self._db.delete(row)
        await self._db.flush()

    # -----------------------------------------------------------------------
    # Credit Packs
    # -----------------------------------------------------------------------

    async def list_packs(self) -> list[CreditPack]:
        """List all credit packs ordered by display_order.

        Returns:
            List of CreditPack rows.
        """
        stmt = select(CreditPack).order_by(CreditPack.display_order, CreditPack.name)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def create_pack(
        self,
        *,
        name: str,
        price_cents: int,
        credit_amount: int,
        display_order: int = 0,
        description: str | None = None,
        highlight_label: str | None = None,
    ) -> CreditPack:
        """Create a credit pack.

        stripe_price_id is intentionally excluded — it is set via
        update_pack after the Stripe price object is created externally.

        Args:
            name: Pack display name.
            price_cents: Price in cents.
            credit_amount: Credits granted.
            display_order: Sort order.
            description: Short description.
            highlight_label: Optional badge text.

        Returns:
            Created CreditPack row.
        """
        row = CreditPack(
            name=name,
            price_cents=price_cents,
            credit_amount=credit_amount,
            display_order=display_order,
            description=description,
            highlight_label=highlight_label,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_pack(
        self,
        pack_id: uuid.UUID,
        *,
        name: str | None = None,
        price_cents: int | None = None,
        credit_amount: int | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
        description: str | None = ...,  # type: ignore[assignment]
        highlight_label: str | None = ...,  # type: ignore[assignment]
        stripe_price_id: str | None = ...,  # type: ignore[assignment]
    ) -> CreditPack:
        """Update a credit pack.

        Args:
            pack_id: UUID of pack.
            name: New name.
            price_cents: New price.
            credit_amount: New credit amount.
            display_order: New sort order.
            is_active: New active status.
            description: New description (None clears).
            highlight_label: New badge (None clears).
            stripe_price_id: New Stripe ID (None clears).

        Returns:
            Updated CreditPack row.

        Raises:
            NotFoundError: If pack not found.
        """
        row = await self._db.get(CreditPack, pack_id)
        if row is None:
            raise NotFoundError("Credit pack", str(pack_id))

        if name is not None:
            row.name = name
        if price_cents is not None:
            row.price_cents = price_cents
        if credit_amount is not None:
            row.credit_amount = credit_amount
        if display_order is not None:
            row.display_order = display_order
        if is_active is not None:
            row.is_active = is_active
        # Sentinel ... means "not provided"; None means "clear the field"
        if description is not ...:
            row.description = description
        if highlight_label is not ...:
            row.highlight_label = highlight_label
        if stripe_price_id is not ...:
            row.stripe_price_id = stripe_price_id

        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def delete_pack(self, pack_id: uuid.UUID) -> None:
        """Delete a credit pack.

        Args:
            pack_id: UUID of pack.

        Raises:
            NotFoundError: If pack not found.
        """
        row = await self._db.get(CreditPack, pack_id)
        if row is None:
            raise NotFoundError("Credit pack", str(pack_id))

        await self._db.delete(row)
        await self._db.flush()

    # -----------------------------------------------------------------------
    # System Config
    # -----------------------------------------------------------------------

    async def list_config(self) -> list[SystemConfig]:
        """List all system config entries.

        Returns:
            List of SystemConfig rows.
        """
        stmt = select(SystemConfig).order_by(SystemConfig.key)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_config(
        self,
        *,
        key: str,
        value: str,
        description: str | None = None,
    ) -> SystemConfig:
        """Create or update a system config entry.

        Args:
            key: Config key.
            value: Config value.
            description: Human-readable description.

        Returns:
            Created or updated SystemConfig row.
        """
        row = await self._db.get(SystemConfig, key)
        if row is None:
            row = SystemConfig(key=key, value=value, description=description)
            self._db.add(row)
        else:
            row.value = value
            if description is not None:
                row.description = description

        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def delete_config(self, key: str) -> None:
        """Delete a system config entry.

        Args:
            key: Config key.

        Raises:
            NotFoundError: If key not found.
        """
        row = await self._db.get(SystemConfig, key)
        if row is None:
            raise NotFoundError("System config", key)

        await self._db.delete(row)
        await self._db.flush()

    # -----------------------------------------------------------------------
    # Admin Users
    # -----------------------------------------------------------------------

    async def list_users(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        is_admin: bool | None = None,
    ) -> tuple[list[User], int]:
        """List users with pagination.

        Args:
            page: Page number (1-based).
            per_page: Items per page (max 100).
            is_admin: Filter by admin status.

        Returns:
            Tuple of (user list, total count).
        """
        per_page = min(per_page, 100)
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        if is_admin is not None:
            stmt = stmt.where(User.is_admin == is_admin)
            count_stmt = count_stmt.where(User.is_admin == is_admin)

        # Total count
        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginated results
        offset = (page - 1) * per_page
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(per_page)
        result = await self._db.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def toggle_admin(
        self,
        *,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        is_admin: bool,
    ) -> User:
        """Toggle admin status for a user.

        Args:
            admin_user_id: UUID of the admin performing the action.
            target_user_id: UUID of the user to modify.
            is_admin: New admin status.

        Returns:
            Updated User.

        Raises:
            ConflictError: CANNOT_DEMOTE_SELF if demoting yourself.
            ConflictError: ADMIN_EMAILS_PROTECTED if demoting env-protected admin.
            NotFoundError: If target user not found.
        """
        # Self-demotion check
        if admin_user_id == target_user_id and not is_admin:
            raise ConflictError(
                code="CANNOT_DEMOTE_SELF",
                message="Cannot remove your own admin status",
            )

        target = await self._db.get(User, target_user_id)
        if target is None:
            raise NotFoundError("User", str(target_user_id))

        # Env-protected check (only on demotion)
        if not is_admin:
            protected_emails = {
                e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()
            }
            if target.email.lower() in protected_emails:
                raise ConflictError(
                    code="ADMIN_EMAILS_PROTECTED",
                    message="Cannot demote this user — protected by ADMIN_EMAILS",
                )

        target.is_admin = is_admin
        target.token_invalidated_before = datetime.now(UTC)

        await self._db.flush()
        await self._db.refresh(target)
        return target
