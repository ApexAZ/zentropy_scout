"""Admin API request/response schemas.

REQ-022 §10.1–§10.7: Pydantic models for all admin endpoint resources —
model registry, pricing config, task routing, funding packs, system config,
admin users, and cache refresh.

All monetary values are serialized as strings to preserve decimal precision.
All schemas use ConfigDict(extra="forbid") to reject unexpected fields.

Coordinates with:
  - providers/llm/base.py — imports TaskType for route validation

Called by: api/v1/admin.py.
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


def _validate_decimal(
    value: str,
    field_name: str,
    *,
    allow_zero: bool = True,
) -> str:
    """Validate a string parses as a finite Decimal.

    Args:
        value: Raw string to parse.
        field_name: Field name for error messages.
        allow_zero: If True, value must be >= 0. If False, must be > 0.
    """
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
    if allow_zero and d < 0:
        msg = f"{field_name} must be >= 0"
        raise ValueError(msg)
    if not allow_zero and d <= 0:
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
        return _validate_decimal(v, "input_cost_per_1k")

    @field_validator("output_cost_per_1k")
    @classmethod
    def check_output_cost(cls, v: str) -> str:
        return _validate_decimal(v, "output_cost_per_1k")

    @field_validator("margin_multiplier")
    @classmethod
    def check_margin(cls, v: str) -> str:
        return _validate_decimal(v, "margin_multiplier", allow_zero=False)


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
            return _validate_decimal(v, "input_cost_per_1k")
        return v

    @field_validator("output_cost_per_1k")
    @classmethod
    def check_output_cost(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_decimal(v, "output_cost_per_1k")
        return v

    @field_validator("margin_multiplier")
    @classmethod
    def check_margin(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_decimal(v, "margin_multiplier", allow_zero=False)
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
# Funding Packs — shared validation helpers
# =============================================================================


def _check_pack_name(v: str) -> None:
    if len(v) > 50:
        msg = "name must be at most 50 characters"
        raise ValueError(msg)


def _check_price_cents(v: int) -> None:
    if v <= 0:
        msg = "price_cents must be > 0"
        raise ValueError(msg)
    if v > 10_000_000:
        msg = "price_cents must be <= 10000000"
        raise ValueError(msg)


def _check_grant_cents(v: int) -> None:
    if v <= 0:
        msg = "grant_cents must be > 0"
        raise ValueError(msg)
    if v > 1_000_000_000:
        msg = "grant_cents must be <= 1000000000"
        raise ValueError(msg)


def _check_display_order(v: int) -> None:
    if v < 0 or v > 1000:
        msg = "display_order must be between 0 and 1000"
        raise ValueError(msg)


def _check_highlight_label(v: str) -> None:
    if len(v) > 50:
        msg = "highlight_label must be at most 50 characters"
        raise ValueError(msg)


# =============================================================================
# Funding Packs
# =============================================================================


class FundingPackCreate(BaseModel):
    """Request schema for POST /admin/funding-packs.

    Attributes:
        name: Pack name, max 50 chars.
        price_cents: Price in USD cents (> 0).
        grant_cents: USD cents granted to user's balance (> 0).
        display_order: Sort order in UI. Defaults to 0.
        description: Short description, max 255 chars.
        highlight_label: Optional badge text, max 50 chars.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    price_cents: int
    grant_cents: int
    display_order: int = 0
    description: str | None = None
    highlight_label: str | None = None

    @field_validator("name")
    @classmethod
    def check_name_length(cls, v: str) -> str:
        _check_pack_name(v)
        return v

    @field_validator("price_cents")
    @classmethod
    def check_price_positive(cls, v: int) -> int:
        _check_price_cents(v)
        return v

    @field_validator("grant_cents")
    @classmethod
    def check_grant_positive(cls, v: int) -> int:
        _check_grant_cents(v)
        return v

    @field_validator("display_order")
    @classmethod
    def check_display_order_range(cls, v: int) -> int:
        _check_display_order(v)
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
        if v is not None:
            _check_highlight_label(v)
        return v


class FundingPackUpdate(BaseModel):
    """Request schema for PATCH /admin/funding-packs/:id.

    All fields optional — only provided fields are updated.

    Attributes:
        name: New pack name.
        price_cents: New price in cents.
        grant_cents: New grant amount in USD cents.
        display_order: New sort order.
        is_active: Toggle active status.
        description: New description.
        highlight_label: New badge text.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price_cents: int | None = None
    grant_cents: int | None = None
    display_order: int | None = None
    is_active: bool | None = None
    description: str | None = None
    highlight_label: str | None = None

    @field_validator("name")
    @classmethod
    def check_name_length(cls, v: str | None) -> str | None:
        if v is not None:
            _check_pack_name(v)
        return v

    @field_validator("price_cents")
    @classmethod
    def check_price_positive(cls, v: int | None) -> int | None:
        if v is not None:
            _check_price_cents(v)
        return v

    @field_validator("grant_cents")
    @classmethod
    def check_grant_positive(cls, v: int | None) -> int | None:
        if v is not None:
            _check_grant_cents(v)
        return v

    @field_validator("display_order")
    @classmethod
    def check_display_order_range(cls, v: int | None) -> int | None:
        if v is not None:
            _check_display_order(v)
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
        if v is not None:
            _check_highlight_label(v)
        return v


class FundingPackResponse(BaseModel):
    """Response schema for funding pack items.

    Attributes:
        id: UUID as string.
        name: Pack name.
        price_cents: Price in USD cents.
        price_display: Formatted price (e.g. '$5.00').
        grant_cents: USD cents granted to user's balance.
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
    grant_cents: int
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


# =============================================================================
# Routing Test (REQ-028 §5)
# =============================================================================

# Task types valid for LLM execution (excludes '_default' routing placeholder).
_VALID_LLM_TASK_TYPES = frozenset({t.value for t in TaskType})


class RoutingTestRequest(BaseModel):
    """Request schema for POST /admin/routing/test.

    REQ-028 §5.1: Admin sends a task type and test prompt to verify
    which provider+model handles the request.

    Attributes:
        task_type: TaskType enum value (e.g. 'extraction').
        prompt: Test prompt to send to the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    task_type: str
    prompt: str

    @field_validator("task_type")
    @classmethod
    def check_task_type(cls, v: str) -> str:
        if v not in _VALID_LLM_TASK_TYPES:
            msg = (
                f"task_type must be one of: {', '.join(sorted(_VALID_LLM_TASK_TYPES))}"
            )
            raise ValueError(msg)
        return v

    @field_validator("prompt")
    @classmethod
    def check_prompt(cls, v: str) -> str:
        if not v.strip():
            msg = "prompt must not be empty or whitespace-only"
            raise ValueError(msg)
        if len(v) > 1000:
            msg = "prompt must be at most 1000 characters"
            raise ValueError(msg)
        return v


class RoutingTestResponse(BaseModel):
    """Response schema for POST /admin/routing/test.

    REQ-028 §5.1: Returns the provider, model, response text,
    latency, and token counts from the test call.

    Attributes:
        provider: Provider that handled the request.
        model: Actual model used.
        response: LLM response text.
        latency_ms: Response time in milliseconds.
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    response: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
