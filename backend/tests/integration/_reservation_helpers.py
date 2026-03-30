"""Shared helpers for reservation integration tests.

Provides seed functions, mock factories, and constants used by both
test_reservation_lifecycle.py and test_reservation_advanced.py.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import (
    ModelRegistry,
    PricingConfig,
    TaskRoutingConfig,
)
from app.models.user import User
from app.providers.llm.base import LLMResponse
from app.providers.metered_provider import MeteredLLMProvider
from app.services.admin.admin_config_service import AdminConfigService
from app.services.billing.metering_service import MeteringService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY = date.today()
PROVIDER = "claude"
MODEL = "claude-3-5-haiku-20241022"
TASK = "extraction"
INITIAL_BALANCE = Decimal("100.000000")
INPUT_PER_1K = Decimal("0.000800")
OUTPUT_PER_1K = Decimal("0.004000")
MARGIN = Decimal("1.30")
ZERO = Decimal("0.000000")

BALANCE_QUERY = "SELECT balance_usd, held_balance_usd FROM users WHERE id = :uid"
HELD_QUERY = "SELECT held_balance_usd FROM users WHERE id = :uid"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def seed_model(db: AsyncSession) -> ModelRegistry:
    """Insert model registry entry for test model."""
    row = ModelRegistry(
        provider=PROVIDER,
        model=MODEL,
        display_name="Claude 3.5 Haiku",
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def seed_pricing(db: AsyncSession) -> PricingConfig:
    """Insert pricing config for test model."""
    row = PricingConfig(
        provider=PROVIDER,
        model=MODEL,
        input_cost_per_1k=INPUT_PER_1K,
        output_cost_per_1k=OUTPUT_PER_1K,
        margin_multiplier=MARGIN,
        effective_date=TODAY,
    )
    db.add(row)
    await db.flush()
    return row


async def seed_routing(db: AsyncSession) -> TaskRoutingConfig:
    """Insert task routing for extraction → test model."""
    row = TaskRoutingConfig(
        provider=PROVIDER,
        task_type=TASK,
        model=MODEL,
    )
    db.add(row)
    await db.flush()
    return row


async def seed_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str = "reservation-test@example.com",
    balance: Decimal = INITIAL_BALANCE,
) -> User:
    """Insert a test user with known balance."""
    user = User(
        id=user_id,
        email=email,
        balance_usd=balance,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_all(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Seed model, pricing, routing, and user for a complete pipeline."""
    await seed_model(db)
    await seed_pricing(db)
    await seed_routing(db)
    return await seed_user(db, user_id)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def mock_llm_response(
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> LLMResponse:
    """Create a mock LLMResponse with known token counts."""
    return LLMResponse(
        content="Test response",
        model=MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish_reason="stop",
        latency_ms=100.0,
    )


def mock_inner_adapter(
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> AsyncMock:
    """Create a mocked inner LLM adapter with provider_name and complete()."""
    inner = AsyncMock()
    inner.provider_name = PROVIDER
    inner.complete.return_value = mock_llm_response(input_tokens, output_tokens)
    return inner


def make_services(
    db: AsyncSession,
) -> tuple[MeteringService, AdminConfigService]:
    """Create MeteringService and AdminConfigService for a given session."""
    admin_config = AdminConfigService(db)
    return MeteringService(db, admin_config), admin_config


def make_metered_provider(
    db: AsyncSession,
    user_id: uuid.UUID,
    inner: AsyncMock | None = None,
) -> tuple[MeteredLLMProvider, AsyncMock]:
    """Create MeteredLLMProvider with real DB services and mocked adapter."""
    if inner is None:
        inner = mock_inner_adapter()
    metering, admin_config = make_services(db)
    provider = MeteredLLMProvider(
        inner, {PROVIDER: inner}, metering, admin_config, user_id
    )
    return provider, inner
