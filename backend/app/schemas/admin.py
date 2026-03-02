"""Admin API request/response schemas.

REQ-022 §10.1–§10.7: Pydantic models for all admin endpoint resources —
model registry, pricing config, task routing, credit packs, system config,
admin users, and cache refresh.

All monetary values are serialized as strings to preserve decimal precision.
All schemas use ConfigDict(extra="forbid") to reject unexpected fields.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, field_validator

from app.providers.llm.base import TaskType

_VALID_PROVIDERS = frozenset({"claude", "openai", "gemini"})
_VALID_MODEL_TYPES = frozenset({"llm", "embedding"})
_VALID_TASK_TYPES = frozenset({t.value for t in TaskType} | {"_default"})

# Max string length for decimal input fields. Prevents pathological-precision
# Decimal parsing (e.g. "0." + "0" * 100_000) from consuming CPU/memory.
_MAX_DECIMAL_STR_LEN = 20

# Shared validation messages (SonarCloud S1192 — extract duplicated literals).
_MSG_MODEL_MAX_100 = "model must be at most 100 characters"
_MSG_DESC_MAX_255 = "description must be at most 255 characters"


def _validate_provider(value: str) -> str:
    """Validate provider is one of the allowed values."""
    if value not in _VALID_PROVIDERS:
        msg = f"provider must be one of: {', '.join(sorted(_VALID_PROVIDERS))}"
        raise ValueError(msg)
    return value


def _validate_model_type(value: str) -> str:
    """Validate model_type is 'llm' or 'embedding'."""
    if value not in _VALID_MODEL_TYPES:
        msg = f"model_type must be one of: {', '.join(sorted(_VALID_MODEL_TYPES))}"
        raise ValueError(msg)
    return value


def _validate_non_negative_decimal(value: str, field_name: str) -> str:
    """Validate a string parses as a finite, non-negative Decimal."""
    if len(value) > _MAX_DECIMAL_STR_LEN:
        msg = f"{field_name} string representation too long"
        raise ValueError(msg)
    try:
        d = Decimal(value)
    except InvalidOperation:
        msg = f"{field_name} must be a valid decimal number"
        raise ValueError(msg) from None
    if not d.is_finite():
        msg = f"{field_name} must be a finite number"
        raise ValueError(msg)
    if d < 0:
        msg = f"{field_name} must be >= 0"
        raise ValueError(msg)
    return value


def _validate_positive_decimal(value: str, field_name: str) -> str:
    """Validate a string parses as a finite, positive Decimal (> 0)."""
    if len(value) > _MAX_DECIMAL_STR_LEN:
        msg = f"{field_name} string representation too long"
        raise ValueError(msg)
    try:
        d = Decimal(value)
    except InvalidOperation:
        msg = f"{field_name} must be a valid decimal number"
        raise ValueError(msg) from None
    if not d.is_finite():
        msg = f"{field_name} must be a finite number"
        raise ValueError(msg)
    if d <= 0:
        msg = f"{field_name} must be > 0"
        raise ValueError(msg)
    return value


# =============================================================================
# Model Registry
# =============================================================================


class ModelRegistryCreate(BaseModel):
    """Request schema for POST /admin/models.

    Attributes:
        provider: Provider identifier (claude, openai, gemini).
        model: Exact model identifier, max 100 chars.
        display_name: Human-friendly name, max 100 chars.
        model_type: 'llm' or 'embedding'.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    display_name: str
    model_type: str

    @field_validator("provider")
    @classmethod
    def check_provider(cls, v: str) -> str:
        return _validate_provider(v)

    @field_validator("model")
    @classmethod
    def check_model_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError(_MSG_MODEL_MAX_100)
        return v

    @field_validator("display_name")
    @classmethod
    def check_display_name_length(cls, v: str) -> str:
        if len(v) > 100:
            msg = "display_name must be at most 100 characters"
            raise ValueError(msg)
        return v

    @field_validator("model_type")
    @classmethod
    def check_model_type(cls, v: str) -> str:
        return _validate_model_type(v)


class ModelRegistryUpdate(BaseModel):
    """Request schema for PATCH /admin/models/:id.

    All fields optional — only provided fields are updated.

    Attributes:
        display_name: New display name.
        is_active: Toggle active status.
        model_type: Change model type.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    is_active: bool | None = None
    model_type: str | None = None

    @field_validator("display_name")
    @classmethod
    def check_display_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 100:
            msg = "display_name must be at most 100 characters"
            raise ValueError(msg)
        return v

    @field_validator("model_type")
    @classmethod
    def check_model_type(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_model_type(v)
        return v


class ModelRegistryResponse(BaseModel):
    """Response schema for model registry items.

    Attributes:
        id: UUID as string.
        provider: Provider identifier.
        model: Model identifier.
        display_name: Human-friendly name.
        model_type: 'llm' or 'embedding'.
        is_active: Whether the model is active.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    model: str
    display_name: str
    model_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Pricing Config
# =============================================================================


class PricingConfigCreate(BaseModel):
    """Request schema for POST /admin/pricing.

    Monetary values are strings to preserve decimal precision.

    Attributes:
        provider: Provider identifier.
        model: Model identifier.
        input_cost_per_1k: Raw cost per 1K input tokens (>= 0).
        output_cost_per_1k: Raw cost per 1K output tokens (>= 0).
        margin_multiplier: Per-model margin (> 0).
        effective_date: Date this pricing becomes active.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    input_cost_per_1k: str
    output_cost_per_1k: str
    margin_multiplier: str
    effective_date: date

    @field_validator("provider")
    @classmethod
    def check_provider(cls, v: str) -> str:
        return _validate_provider(v)

    @field_validator("model")
    @classmethod
    def check_model_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError(_MSG_MODEL_MAX_100)
        return v

    @field_validator("input_cost_per_1k")
    @classmethod
    def check_input_cost(cls, v: str) -> str:
        return _validate_non_negative_decimal(v, "input_cost_per_1k")

    @field_validator("output_cost_per_1k")
    @classmethod
    def check_output_cost(cls, v: str) -> str:
        return _validate_non_negative_decimal(v, "output_cost_per_1k")

    @field_validator("margin_multiplier")
    @classmethod
    def check_margin(cls, v: str) -> str:
        return _validate_positive_decimal(v, "margin_multiplier")


class PricingConfigUpdate(BaseModel):
    """Request schema for PATCH /admin/pricing/:id.

    All fields optional — only provided fields are updated.

    Attributes:
        input_cost_per_1k: New input cost.
        output_cost_per_1k: New output cost.
        margin_multiplier: New margin.
    """

    model_config = ConfigDict(extra="forbid")

    input_cost_per_1k: str | None = None
    output_cost_per_1k: str | None = None
    margin_multiplier: str | None = None

    @field_validator("input_cost_per_1k")
    @classmethod
    def check_input_cost(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_non_negative_decimal(v, "input_cost_per_1k")
        return v

    @field_validator("output_cost_per_1k")
    @classmethod
    def check_output_cost(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_non_negative_decimal(v, "output_cost_per_1k")
        return v

    @field_validator("margin_multiplier")
    @classmethod
    def check_margin(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_positive_decimal(v, "margin_multiplier")
        return v


class PricingConfigResponse(BaseModel):
    """Response schema for pricing config items.

    Attributes:
        id: UUID as string.
        provider: Provider identifier.
        model: Model identifier.
        input_cost_per_1k: Raw cost per 1K input tokens.
        output_cost_per_1k: Raw cost per 1K output tokens.
        margin_multiplier: Per-model margin.
        effective_date: Date this pricing is active from.
        is_current: Whether this is the currently effective pricing.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    model: str
    input_cost_per_1k: str
    output_cost_per_1k: str
    margin_multiplier: str
    effective_date: date
    is_current: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Task Routing
# =============================================================================


class TaskRoutingCreate(BaseModel):
    """Request schema for POST /admin/routing.

    Attributes:
        provider: Provider identifier.
        task_type: TaskType enum value or '_default'.
        model: Target model identifier.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    task_type: str
    model: str

    @field_validator("provider")
    @classmethod
    def check_provider(cls, v: str) -> str:
        return _validate_provider(v)

    @field_validator("task_type")
    @classmethod
    def check_task_type(cls, v: str) -> str:
        if v not in _VALID_TASK_TYPES:
            msg = f"task_type must be one of: {', '.join(sorted(_VALID_TASK_TYPES))}"
            raise ValueError(msg)
        return v

    @field_validator("model")
    @classmethod
    def check_model_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError(_MSG_MODEL_MAX_100)
        return v


class TaskRoutingUpdate(BaseModel):
    """Request schema for PATCH /admin/routing/:id.

    Attributes:
        model: New target model.
    """

    model_config = ConfigDict(extra="forbid")

    model: str | None = None

    @field_validator("model")
    @classmethod
    def check_model_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 100:
            raise ValueError(_MSG_MODEL_MAX_100)
        return v


class TaskRoutingResponse(BaseModel):
    """Response schema for task routing items.

    Attributes:
        id: UUID as string.
        provider: Provider identifier.
        task_type: Task type or '_default'.
        model: Target model identifier.
        model_display_name: Human-friendly name from model registry.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    task_type: str
    model: str
    model_display_name: str | None = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Credit Packs
# =============================================================================


class CreditPackCreate(BaseModel):
    """Request schema for POST /admin/credit-packs.

    Attributes:
        name: Pack name, max 50 chars.
        price_cents: Price in USD cents (> 0).
        credit_amount: Credits granted (> 0).
        display_order: Sort order in UI. Defaults to 0.
        description: Short description, max 255 chars.
        highlight_label: Optional badge text, max 50 chars.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    price_cents: int
    credit_amount: int
    display_order: int = 0
    description: str | None = None
    highlight_label: str | None = None

    @field_validator("name")
    @classmethod
    def check_name_length(cls, v: str) -> str:
        if len(v) > 50:
            msg = "name must be at most 50 characters"
            raise ValueError(msg)
        return v

    @field_validator("price_cents")
    @classmethod
    def check_price_positive(cls, v: int) -> int:
        if v <= 0:
            msg = "price_cents must be > 0"
            raise ValueError(msg)
        if v > 10_000_000:
            msg = "price_cents must be <= 10000000"
            raise ValueError(msg)
        return v

    @field_validator("credit_amount")
    @classmethod
    def check_credit_positive(cls, v: int) -> int:
        if v <= 0:
            msg = "credit_amount must be > 0"
            raise ValueError(msg)
        if v > 1_000_000_000:
            msg = "credit_amount must be <= 1000000000"
            raise ValueError(msg)
        return v

    @field_validator("display_order")
    @classmethod
    def check_display_order_range(cls, v: int) -> int:
        if v < 0 or v > 1000:
            msg = "display_order must be between 0 and 1000"
            raise ValueError(msg)
        return v

    @field_validator("description")
    @classmethod
    def check_description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError(_MSG_DESC_MAX_255)
        return v

    @field_validator("highlight_label")
    @classmethod
    def check_highlight_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 50:
            msg = "highlight_label must be at most 50 characters"
            raise ValueError(msg)
        return v


class CreditPackUpdate(BaseModel):
    """Request schema for PATCH /admin/credit-packs/:id.

    All fields optional — only provided fields are updated.

    Attributes:
        name: New pack name.
        price_cents: New price in cents.
        credit_amount: New credit amount.
        display_order: New sort order.
        is_active: Toggle active status.
        description: New description.
        highlight_label: New badge text.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price_cents: int | None = None
    credit_amount: int | None = None
    display_order: int | None = None
    is_active: bool | None = None
    description: str | None = None
    highlight_label: str | None = None

    @field_validator("name")
    @classmethod
    def check_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 50:
            msg = "name must be at most 50 characters"
            raise ValueError(msg)
        return v

    @field_validator("price_cents")
    @classmethod
    def check_price_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "price_cents must be > 0"
            raise ValueError(msg)
        if v is not None and v > 10_000_000:
            msg = "price_cents must be <= 10000000"
            raise ValueError(msg)
        return v

    @field_validator("credit_amount")
    @classmethod
    def check_credit_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "credit_amount must be > 0"
            raise ValueError(msg)
        if v is not None and v > 1_000_000_000:
            msg = "credit_amount must be <= 1000000000"
            raise ValueError(msg)
        return v

    @field_validator("display_order")
    @classmethod
    def check_display_order_range(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 1000):
            msg = "display_order must be between 0 and 1000"
            raise ValueError(msg)
        return v

    @field_validator("description")
    @classmethod
    def check_description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError(_MSG_DESC_MAX_255)
        return v

    @field_validator("highlight_label")
    @classmethod
    def check_highlight_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 50:
            msg = "highlight_label must be at most 50 characters"
            raise ValueError(msg)
        return v


class CreditPackResponse(BaseModel):
    """Response schema for credit pack items.

    Attributes:
        id: UUID as string.
        name: Pack name.
        price_cents: Price in USD cents.
        price_display: Formatted price (e.g. '$5.00').
        credit_amount: Credits granted.
        stripe_price_id: Stripe Price ID or None.
        display_order: Sort order.
        is_active: Whether the pack is active.
        description: Short description or None.
        highlight_label: Badge text or None.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    price_cents: int
    price_display: str
    credit_amount: int
    stripe_price_id: str | None = None
    display_order: int
    is_active: bool
    description: str | None = None
    highlight_label: str | None = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# System Config
# =============================================================================


class SystemConfigUpsert(BaseModel):
    """Request schema for PUT /admin/config/:key.

    Attributes:
        value: Config value as string.
        description: Human-readable description, max 255 chars.
    """

    model_config = ConfigDict(extra="forbid")

    value: str
    description: str | None = None

    @field_validator("value")
    @classmethod
    def check_value_length(cls, v: str) -> str:
        if len(v) > 10_000:
            msg = "value must be at most 10000 characters"
            raise ValueError(msg)
        return v

    @field_validator("description")
    @classmethod
    def check_description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError(_MSG_DESC_MAX_255)
        return v


class SystemConfigResponse(BaseModel):
    """Response schema for system config items.

    Attributes:
        key: Config key (PK).
        value: Config value.
        description: Description or None.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str
    description: str | None = None
    updated_at: datetime


# =============================================================================
# Admin Users
# =============================================================================


class AdminUserUpdate(BaseModel):
    """Request schema for PATCH /admin/users/:id.

    Attributes:
        is_admin: New admin status.
    """

    model_config = ConfigDict(extra="forbid")

    is_admin: bool


class AdminUserResponse(BaseModel):
    """Response schema for admin user items.

    Attributes:
        id: UUID as string.
        email: User email.
        name: User display name or None.
        is_admin: Whether the user is an admin.
        is_env_protected: Whether the user is protected by ADMIN_EMAILS env var.
        balance_usd: Balance as string with 6 decimal places.
        created_at: Account creation timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    name: str | None = None
    is_admin: bool
    is_env_protected: bool
    balance_usd: str
    created_at: datetime


# =============================================================================
# Cache Refresh
# =============================================================================


class CacheRefreshResponse(BaseModel):
    """Response schema for POST /admin/cache/refresh.

    Attributes:
        message: Confirmation message.
        caching_enabled: Whether caching is active (false for MVP).
    """

    model_config = ConfigDict(extra="forbid")

    message: str
    caching_enabled: bool
