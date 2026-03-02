"""Admin API router.

REQ-022 §10.1–§10.7: CRUD endpoints for model registry, pricing config,
task routing, credit packs, system config, admin users, and cache refresh.

All endpoints require the AdminUser dependency (§5.3).
Response envelopes follow REQ-006 §7.2.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models.admin_config import CreditPack, ModelRegistry, PricingConfig
from app.models.user import User
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
from app.services.admin_management_service import AdminManagementService

router = APIRouter()

# =============================================================================
# Shared types and helpers
# =============================================================================

_DECIMAL_FMT = "{:.6f}"

ProviderFilter = Annotated[
    str | None,
    Query(max_length=20, description="Filter by provider"),
]
ModelFilter = Annotated[
    str | None,
    Query(max_length=100, description="Filter by model"),
]
ModelTypeFilter = Annotated[
    str | None,
    Query(max_length=20, description="Filter by model type (llm or embedding)"),
]
IsActiveFilter = Annotated[
    bool | None,
    Query(description="Filter by active status"),
]
IsAdminFilter = Annotated[
    bool | None,
    Query(description="Filter by admin status"),
]
PageParam = Annotated[int, Query(ge=1, description="Page number (1-based)")]
PerPageParam = Annotated[
    int, Query(ge=1, le=100, description="Items per page (max 100)")
]
ConfigKey = Annotated[
    str,
    Path(max_length=100, description="Config key identifier"),
]


def _model_response(row: ModelRegistry) -> ModelRegistryResponse:
    """Build ModelRegistryResponse from ORM row."""
    return ModelRegistryResponse(
        id=str(row.id),
        provider=row.provider,
        model=row.model,
        display_name=row.display_name,
        model_type=row.model_type,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _pricing_response(row: PricingConfig, *, is_current: bool) -> PricingConfigResponse:
    """Build PricingConfigResponse from ORM row with computed is_current."""
    return PricingConfigResponse(
        id=str(row.id),
        provider=row.provider,
        model=row.model,
        input_cost_per_1k=_DECIMAL_FMT.format(row.input_cost_per_1k),
        output_cost_per_1k=_DECIMAL_FMT.format(row.output_cost_per_1k),
        margin_multiplier=_DECIMAL_FMT.format(row.margin_multiplier),
        effective_date=row.effective_date,
        is_current=is_current,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _pack_response(row: CreditPack) -> CreditPackResponse:
    """Build CreditPackResponse from ORM row with computed price_display."""
    return CreditPackResponse(
        id=str(row.id),
        name=row.name,
        price_cents=row.price_cents,
        price_display=f"${row.price_cents / 100:.2f}",
        credit_amount=row.credit_amount,
        stripe_price_id=row.stripe_price_id,
        display_order=row.display_order,
        is_active=row.is_active,
        description=row.description,
        highlight_label=row.highlight_label,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _user_response(user: User, *, protected_emails: set[str]) -> AdminUserResponse:
    """Build AdminUserResponse from ORM row with computed is_env_protected."""
    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_admin=user.is_admin,
        is_env_protected=user.email.lower() in protected_emails,
        balance_usd=_DECIMAL_FMT.format(user.balance_usd),
        created_at=user.created_at,
    )


def _get_protected_emails() -> set[str]:
    """Parse ADMIN_EMAILS env var into a lowercase set for env-protected checks."""
    return {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}


# =============================================================================
# Model Registry (§10.1)
# =============================================================================


@router.get("/models")
async def list_models(
    _admin: AdminUser,
    db: DbSession,
    provider: ProviderFilter = None,
    model_type: ModelTypeFilter = None,
    is_active: IsActiveFilter = None,
) -> DataResponse[list[ModelRegistryResponse]]:
    """List registered models with optional filters.

    REQ-022 §10.1: GET /admin/models.
    """
    svc = AdminManagementService(db)
    rows = await svc.list_models(
        provider=provider, model_type=model_type, is_active=is_active
    )
    return DataResponse(data=[_model_response(row) for row in rows])


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model(
    _admin: AdminUser,
    db: DbSession,
    body: ModelRegistryCreate,
) -> DataResponse[ModelRegistryResponse]:
    """Register a new model.

    REQ-022 §10.1: POST /admin/models.
    """
    svc = AdminManagementService(db)
    row = await svc.create_model(
        provider=body.provider,
        model=body.model,
        display_name=body.display_name,
        model_type=body.model_type,
    )
    await db.commit()
    return DataResponse(data=_model_response(row))


@router.patch("/models/{model_id}")
async def update_model(
    _admin: AdminUser,
    db: DbSession,
    model_id: uuid.UUID,
    body: ModelRegistryUpdate,
) -> DataResponse[ModelRegistryResponse]:
    """Update model properties.

    REQ-022 §10.1: PATCH /admin/models/:id.
    """
    svc = AdminManagementService(db)
    row = await svc.update_model(
        model_id,
        display_name=body.display_name,
        is_active=body.is_active,
        model_type=body.model_type,
    )
    await db.commit()
    return DataResponse(data=_model_response(row))


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    _admin: AdminUser,
    db: DbSession,
    model_id: uuid.UUID,
) -> Response:
    """Delete a model from the registry.

    REQ-022 §10.1: DELETE /admin/models/:id.
    """
    svc = AdminManagementService(db)
    await svc.delete_model(model_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Pricing Config (§10.2)
# =============================================================================


@router.get("/pricing")
async def list_pricing(
    _admin: AdminUser,
    db: DbSession,
    provider: ProviderFilter = None,
    model: ModelFilter = None,
) -> DataResponse[list[PricingConfigResponse]]:
    """List pricing entries with computed is_current flag.

    REQ-022 §10.2: GET /admin/pricing.
    """
    svc = AdminManagementService(db)
    entries = await svc.list_pricing(provider=provider, model=model)
    return DataResponse(
        data=[
            PricingConfigResponse(
                id=e["id"],
                provider=e["provider"],
                model=e["model"],
                input_cost_per_1k=_DECIMAL_FMT.format(e["input_cost_per_1k"]),
                output_cost_per_1k=_DECIMAL_FMT.format(e["output_cost_per_1k"]),
                margin_multiplier=_DECIMAL_FMT.format(e["margin_multiplier"]),
                effective_date=e["effective_date"],
                is_current=e["is_current"],
                created_at=e["created_at"],
                updated_at=e["updated_at"],
            )
            for e in entries
        ]
    )


@router.post("/pricing", status_code=status.HTTP_201_CREATED)
async def create_pricing(
    _admin: AdminUser,
    db: DbSession,
    body: PricingConfigCreate,
) -> DataResponse[PricingConfigResponse]:
    """Add a pricing entry.

    REQ-022 §10.2: POST /admin/pricing.
    """
    svc = AdminManagementService(db)
    row = await svc.create_pricing(
        provider=body.provider,
        model=body.model,
        input_cost_per_1k=Decimal(body.input_cost_per_1k),
        output_cost_per_1k=Decimal(body.output_cost_per_1k),
        margin_multiplier=Decimal(body.margin_multiplier),
        effective_date=body.effective_date,
    )
    await db.commit()
    return DataResponse(
        data=_pricing_response(row, is_current=row.effective_date <= date.today())
    )


@router.patch("/pricing/{pricing_id}")
async def update_pricing(
    _admin: AdminUser,
    db: DbSession,
    pricing_id: uuid.UUID,
    body: PricingConfigUpdate,
) -> DataResponse[PricingConfigResponse]:
    """Update a pricing entry.

    REQ-022 §10.2: PATCH /admin/pricing/:id.
    """
    svc = AdminManagementService(db)
    row = await svc.update_pricing(
        pricing_id,
        input_cost_per_1k=(
            Decimal(body.input_cost_per_1k)
            if body.input_cost_per_1k is not None
            else None
        ),
        output_cost_per_1k=(
            Decimal(body.output_cost_per_1k)
            if body.output_cost_per_1k is not None
            else None
        ),
        margin_multiplier=(
            Decimal(body.margin_multiplier)
            if body.margin_multiplier is not None
            else None
        ),
    )
    await db.commit()
    return DataResponse(
        data=_pricing_response(row, is_current=row.effective_date <= date.today())
    )


@router.delete("/pricing/{pricing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing(
    _admin: AdminUser,
    db: DbSession,
    pricing_id: uuid.UUID,
) -> Response:
    """Delete a pricing entry.

    REQ-022 §10.2: DELETE /admin/pricing/:id.
    """
    svc = AdminManagementService(db)
    await svc.delete_pricing(pricing_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Task Routing (§10.3)
# =============================================================================


@router.get("/routing")
async def list_routing(
    _admin: AdminUser,
    db: DbSession,
    provider: ProviderFilter = None,
) -> DataResponse[list[TaskRoutingResponse]]:
    """List routing entries with model display_name.

    REQ-022 §10.3: GET /admin/routing.
    """
    svc = AdminManagementService(db)
    entries = await svc.list_routing(provider=provider)
    return DataResponse(
        data=[
            TaskRoutingResponse(
                id=e["id"],
                provider=e["provider"],
                task_type=e["task_type"],
                model=e["model"],
                model_display_name=e["model_display_name"],
                created_at=e["created_at"],
                updated_at=e["updated_at"],
            )
            for e in entries
        ]
    )


@router.post("/routing", status_code=status.HTTP_201_CREATED)
async def create_routing(
    _admin: AdminUser,
    db: DbSession,
    body: TaskRoutingCreate,
) -> DataResponse[TaskRoutingResponse]:
    """Add a routing entry.

    REQ-022 §10.3: POST /admin/routing.
    """
    svc = AdminManagementService(db)
    row = await svc.create_routing(
        provider=body.provider,
        task_type=body.task_type,
        model=body.model,
    )
    await db.commit()
    return DataResponse(
        data=TaskRoutingResponse(
            id=str(row.id),
            provider=row.provider,
            task_type=row.task_type,
            model=row.model,
            model_display_name=None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    )


@router.patch("/routing/{routing_id}")
async def update_routing(
    _admin: AdminUser,
    db: DbSession,
    routing_id: uuid.UUID,
    body: TaskRoutingUpdate,
) -> DataResponse[TaskRoutingResponse]:
    """Update routing (change target model).

    REQ-022 §10.3: PATCH /admin/routing/:id.
    """
    svc = AdminManagementService(db)
    row = await svc.update_routing(routing_id, model=body.model)
    await db.commit()
    return DataResponse(
        data=TaskRoutingResponse(
            id=str(row.id),
            provider=row.provider,
            task_type=row.task_type,
            model=row.model,
            model_display_name=None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    )


@router.delete("/routing/{routing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing(
    _admin: AdminUser,
    db: DbSession,
    routing_id: uuid.UUID,
) -> Response:
    """Delete a routing entry.

    REQ-022 §10.3: DELETE /admin/routing/:id.
    """
    svc = AdminManagementService(db)
    await svc.delete_routing(routing_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Credit Packs (§10.4)
# =============================================================================


@router.get("/credit-packs")
async def list_packs(
    _admin: AdminUser,
    db: DbSession,
) -> DataResponse[list[CreditPackResponse]]:
    """List all credit packs.

    REQ-022 §10.4: GET /admin/credit-packs.
    """
    svc = AdminManagementService(db)
    rows = await svc.list_packs()
    return DataResponse(data=[_pack_response(row) for row in rows])


@router.post("/credit-packs", status_code=status.HTTP_201_CREATED)
async def create_pack(
    _admin: AdminUser,
    db: DbSession,
    body: CreditPackCreate,
) -> DataResponse[CreditPackResponse]:
    """Create a credit pack.

    REQ-022 §10.4: POST /admin/credit-packs.
    """
    svc = AdminManagementService(db)
    row = await svc.create_pack(
        name=body.name,
        price_cents=body.price_cents,
        credit_amount=body.credit_amount,
        display_order=body.display_order,
        description=body.description,
        highlight_label=body.highlight_label,
    )
    await db.commit()
    return DataResponse(data=_pack_response(row))


@router.patch("/credit-packs/{pack_id}")
async def update_pack(
    _admin: AdminUser,
    db: DbSession,
    pack_id: uuid.UUID,
    body: CreditPackUpdate,
) -> DataResponse[CreditPackResponse]:
    """Update a credit pack.

    REQ-022 §10.4: PATCH /admin/credit-packs/:id.
    """
    svc = AdminManagementService(db)
    kwargs = {field: getattr(body, field) for field in body.model_fields_set}
    row = await svc.update_pack(pack_id, **kwargs)
    await db.commit()
    return DataResponse(data=_pack_response(row))


@router.delete("/credit-packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pack(
    _admin: AdminUser,
    db: DbSession,
    pack_id: uuid.UUID,
) -> Response:
    """Delete a credit pack.

    REQ-022 §10.4: DELETE /admin/credit-packs/:id.
    """
    svc = AdminManagementService(db)
    await svc.delete_pack(pack_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# System Config (§10.5)
# =============================================================================


@router.get("/config")
async def list_config(
    _admin: AdminUser,
    db: DbSession,
) -> DataResponse[list[SystemConfigResponse]]:
    """List all system config entries.

    REQ-022 §10.5: GET /admin/config.
    """
    svc = AdminManagementService(db)
    rows = await svc.list_config()
    return DataResponse(
        data=[
            SystemConfigResponse(
                key=row.key,
                value=row.value,
                description=row.description,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


@router.put("/config/{key}")
async def upsert_config(
    _admin: AdminUser,
    db: DbSession,
    key: ConfigKey,
    body: SystemConfigUpsert,
) -> DataResponse[SystemConfigResponse]:
    """Create or update a system config entry.

    REQ-022 §10.5: PUT /admin/config/:key.
    """
    svc = AdminManagementService(db)
    row = await svc.upsert_config(
        key=key, value=body.value, description=body.description
    )
    await db.commit()
    return DataResponse(
        data=SystemConfigResponse(
            key=row.key,
            value=row.value,
            description=row.description,
            updated_at=row.updated_at,
        )
    )


@router.delete("/config/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    _admin: AdminUser,
    db: DbSession,
    key: ConfigKey,
) -> Response:
    """Delete a system config entry.

    REQ-022 §10.5: DELETE /admin/config/:key.
    """
    svc = AdminManagementService(db)
    await svc.delete_config(key)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Admin Users (§10.6)
# =============================================================================


@router.get("/users")
async def list_users(
    _admin: AdminUser,
    db: DbSession,
    page: PageParam = 1,
    per_page: PerPageParam = 50,
    is_admin: IsAdminFilter = None,
) -> ListResponse[AdminUserResponse]:
    """List all users with pagination.

    REQ-022 §10.6: GET /admin/users.
    """
    protected = _get_protected_emails()
    svc = AdminManagementService(db)
    users, total = await svc.list_users(page=page, per_page=per_page, is_admin=is_admin)
    return ListResponse(
        data=[_user_response(u, protected_emails=protected) for u in users],
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.patch("/users/{user_id}")
async def toggle_admin(
    admin_user_id: AdminUser,
    db: DbSession,
    user_id: uuid.UUID,
    body: AdminUserUpdate,
) -> DataResponse[AdminUserResponse]:
    """Toggle admin status for a user.

    REQ-022 §10.6: PATCH /admin/users/:id.
    """
    svc = AdminManagementService(db)
    user = await svc.toggle_admin(
        admin_user_id=admin_user_id,
        target_user_id=user_id,
        is_admin=body.is_admin,
    )
    await db.commit()
    return DataResponse(
        data=_user_response(user, protected_emails=_get_protected_emails())
    )


# =============================================================================
# Cache Refresh (§10.7)
# =============================================================================


@router.post("/cache/refresh")
async def refresh_cache(
    _admin: AdminUser,
) -> DataResponse[CacheRefreshResponse]:
    """Trigger cache refresh (no-op for MVP).

    REQ-022 §10.7, §2.7: Placeholder endpoint — no caching layer exists.
    """
    return DataResponse(
        data=CacheRefreshResponse(
            message="Cache refresh triggered",
            caching_enabled=False,
        )
    )
