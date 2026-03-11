"""Tests for credits API endpoints.

REQ-029 §8.1–§8.3: HTTP-level tests for GET /packs (public),
POST /checkout (auth + Stripe), and GET /purchases (auth + pagination).
Tests verify auth gates, response envelope shapes, error codes, and
the credits_enabled feature flag.
"""

import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin_config import FundingPack
from app.models.usage import CreditTransaction
from app.models.user import User
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt

# =============================================================================
# Constants
# =============================================================================

_PREFIX = "/api/v1/credits"
_TEST_EMAIL = "credits-test@example.com"
_SVC = "app.api.v1.credits"
_CHECKOUT_URL = "https://checkout.stripe.com/pay/cs_test_abc"
_SESSION_ID = "cs_test_abc"
_CODE_INVALID_PACK = "INVALID_PACK_ID"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def credits_user(db_session: AsyncSession) -> User:
    """Create a test user for credit endpoint tests."""
    user = User(id=TEST_USER_ID, email=_TEST_EMAIL)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_client(
    db_session: AsyncSession,
    credits_user,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated HTTP client for credit endpoint tests."""
    from app.core.database import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_credits_enabled = settings.credits_enabled
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.credits_enabled = True

    test_jwt = create_test_jwt(TEST_USER_ID)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.credits_enabled = original_credits_enabled
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def unauth_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated HTTP client (no JWT cookie)."""
    from app.core.database import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_credits_enabled = settings.credits_enabled
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.credits_enabled = True

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.credits_enabled = original_credits_enabled
    app.dependency_overrides.pop(get_db, None)


async def _seed_pack(
    db: AsyncSession,
    *,
    name: str = "Starter",
    price_cents: int = 500,
    grant_cents: int = 500,
    stripe_price_id: str | None = "price_test_starter",
    is_active: bool = True,
    display_order: int = 1,
    description: str | None = "Test pack",
    highlight_label: str | None = None,
) -> FundingPack:
    """Insert a funding pack for testing."""
    pack = FundingPack(
        name=name,
        price_cents=price_cents,
        grant_cents=grant_cents,
        stripe_price_id=stripe_price_id,
        is_active=is_active,
        display_order=display_order,
        description=description,
        highlight_label=highlight_label,
    )
    db.add(pack)
    await db.flush()
    await db.refresh(pack)
    return pack


async def _seed_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount_usd: Decimal = Decimal("10.000000"),
    transaction_type: str = "purchase",
    description: str | None = "Test purchase",
) -> CreditTransaction:
    """Insert a credit transaction for testing."""
    txn = CreditTransaction(
        user_id=user_id,
        amount_usd=amount_usd,
        transaction_type=transaction_type,
        description=description,
    )
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return txn


# =============================================================================
# GET /packs — public pack listing
# =============================================================================


class TestGetPacks:
    """GET /credits/packs returns active packs with stripe_price_id."""

    async def test_returns_active_packs(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns active packs with stripe_price_id set."""
        await _seed_pack(db_session, name="Starter", display_order=1)
        await _seed_pack(
            db_session,
            name="Standard",
            price_cents=1000,
            grant_cents=1000,
            display_order=2,
            highlight_label="Most Popular",
        )

        resp = await auth_client.get(f"{_PREFIX}/packs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["name"] == "Starter"
        assert data[0]["price_display"] == "$5.00"
        assert data[0]["amount_display"] == "$5.00"
        assert data[1]["highlight_label"] == "Most Popular"

    async def test_excludes_inactive_packs(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Inactive packs are excluded from the listing."""
        await _seed_pack(db_session, name="Active")
        await _seed_pack(db_session, name="Inactive", is_active=False)

        resp = await auth_client.get(f"{_PREFIX}/packs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Active"

    async def test_excludes_packs_without_stripe_price_id(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Packs without stripe_price_id are excluded."""
        await _seed_pack(db_session, name="Configured")
        await _seed_pack(db_session, name="Unconfigured", stripe_price_id=None)

        resp = await auth_client.get(f"{_PREFIX}/packs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Configured"

    async def test_empty_when_no_packs(self, auth_client: AsyncClient) -> None:
        """Returns empty list when no packs exist."""
        resp = await auth_client.get(f"{_PREFIX}/packs")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_accessible_without_auth(
        self, unauth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /packs is a public endpoint — no auth required."""
        await _seed_pack(db_session, name="Public")

        resp = await unauth_client.get(f"{_PREFIX}/packs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1

    async def test_ordered_by_display_order(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Packs are sorted by display_order ascending."""
        await _seed_pack(db_session, name="Third", display_order=3)
        await _seed_pack(db_session, name="First", display_order=1)
        await _seed_pack(db_session, name="Second", display_order=2)

        resp = await auth_client.get(f"{_PREFIX}/packs")

        data = resp.json()["data"]
        names = [p["name"] for p in data]
        assert names == ["First", "Second", "Third"]


# =============================================================================
# POST /checkout — create checkout session
# =============================================================================


class TestPostCheckout:
    """POST /credits/checkout creates a Stripe Checkout Session."""

    async def test_creates_checkout_session(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Valid pack_id creates a checkout session and returns URL."""
        pack = await _seed_pack(db_session)

        with patch(
            f"{_SVC}.create_checkout_session",
            new_callable=AsyncMock,
            return_value=(_CHECKOUT_URL, _SESSION_ID),
        ):
            resp = await auth_client.post(
                f"{_PREFIX}/checkout",
                json={"pack_id": str(pack.id)},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["checkout_url"] == _CHECKOUT_URL
        assert data["session_id"] == _SESSION_ID

    async def test_returns_400_for_unknown_pack(self, auth_client: AsyncClient) -> None:
        """Returns INVALID_PACK_ID for nonexistent pack."""
        resp = await auth_client.post(
            f"{_PREFIX}/checkout",
            json={"pack_id": str(uuid.uuid4())},
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == _CODE_INVALID_PACK

    async def test_returns_400_for_inactive_pack(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns INVALID_PACK_ID for inactive pack."""
        pack = await _seed_pack(db_session, is_active=False)

        resp = await auth_client.post(
            f"{_PREFIX}/checkout",
            json={"pack_id": str(pack.id)},
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == _CODE_INVALID_PACK

    async def test_returns_400_for_pack_without_stripe_price_id(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns INVALID_PACK_ID for pack without stripe_price_id."""
        pack = await _seed_pack(db_session, stripe_price_id=None)

        resp = await auth_client.post(
            f"{_PREFIX}/checkout",
            json={"pack_id": str(pack.id)},
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == _CODE_INVALID_PACK

    async def test_returns_502_on_stripe_error(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns STRIPE_ERROR when Stripe API fails."""
        from app.services.stripe_service import StripeServiceError

        pack = await _seed_pack(db_session)

        with patch(
            f"{_SVC}.create_checkout_session",
            new_callable=AsyncMock,
            side_effect=StripeServiceError("Payment service error. Please try again."),
        ):
            resp = await auth_client.post(
                f"{_PREFIX}/checkout",
                json={"pack_id": str(pack.id)},
            )

        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "STRIPE_ERROR"

    async def test_returns_503_when_credits_disabled(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns CREDITS_UNAVAILABLE when credits_enabled is false."""
        pack = await _seed_pack(db_session)

        settings.credits_enabled = False
        try:
            resp = await auth_client.post(
                f"{_PREFIX}/checkout",
                json={"pack_id": str(pack.id)},
            )
        finally:
            settings.credits_enabled = True

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "CREDITS_UNAVAILABLE"

    async def test_requires_auth(
        self, unauth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST /checkout requires authentication."""
        pack = await _seed_pack(db_session)

        resp = await unauth_client.post(
            f"{_PREFIX}/checkout",
            json={"pack_id": str(pack.id)},
        )

        assert resp.status_code == 401


# =============================================================================
# GET /purchases — purchase history
# =============================================================================


class TestGetPurchases:
    """GET /credits/purchases returns paginated purchase history."""

    async def test_returns_user_transactions(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns credit transactions for the current user."""
        await _seed_transaction(db_session, TEST_USER_ID, transaction_type="purchase")
        await _seed_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("0.100000"),
            transaction_type="signup_grant",
            description="Welcome bonus",
        )

        resp = await auth_client.get(f"{_PREFIX}/purchases")

        assert resp.status_code == 200
        data = resp.json()["data"]
        meta = resp.json()["meta"]
        assert len(data) == 2
        assert meta["total"] == 2

    async def test_includes_amount_display(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Response includes formatted amount_display field."""
        await _seed_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("10.000000"),
        )

        resp = await auth_client.get(f"{_PREFIX}/purchases")

        data = resp.json()["data"]
        assert data[0]["amount_display"] == "$10.00"
        assert data[0]["amount_usd"] == "10.000000"

    async def test_pagination(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Pagination returns correct subset and total count."""
        for i in range(5):
            await _seed_transaction(
                db_session,
                TEST_USER_ID,
                description=f"Purchase {i}",
            )

        resp = await auth_client.get(f"{_PREFIX}/purchases?page=1&per_page=2")

        data = resp.json()["data"]
        meta = resp.json()["meta"]
        assert len(data) == 2
        assert meta["total"] == 5
        assert meta["page"] == 1
        assert meta["per_page"] == 2
        assert meta["total_pages"] == 3

    async def test_filters_to_visible_transaction_types(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Only includes purchase, signup_grant, admin_grant, refund types."""
        await _seed_transaction(db_session, TEST_USER_ID, transaction_type="purchase")
        await _seed_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("-0.003640"),
            transaction_type="usage_debit",
            description="LLM call",
        )
        await _seed_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("0.100000"),
            transaction_type="signup_grant",
        )

        resp = await auth_client.get(f"{_PREFIX}/purchases")

        data = resp.json()["data"]
        types = {d["transaction_type"] for d in data}
        assert "usage_debit" not in types
        assert len(data) == 2

    async def test_cross_user_isolation(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Does not return other users' transactions."""
        other_user = User(id=uuid.uuid4(), email="other@test.example.com")
        db_session.add(other_user)
        await db_session.flush()

        await _seed_transaction(db_session, TEST_USER_ID)
        await _seed_transaction(db_session, other_user.id)

        resp = await auth_client.get(f"{_PREFIX}/purchases")

        data = resp.json()["data"]
        assert len(data) == 1

    async def test_requires_auth(self, unauth_client: AsyncClient) -> None:
        """GET /purchases requires authentication."""
        resp = await unauth_client.get(f"{_PREFIX}/purchases")

        assert resp.status_code == 401

    async def test_refund_shows_negative_display(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Refund transactions show negative amount_display."""
        await _seed_transaction(
            db_session,
            TEST_USER_ID,
            amount_usd=Decimal("-5.000000"),
            transaction_type="refund",
            description="Refund — $5.00",
        )

        resp = await auth_client.get(f"{_PREFIX}/purchases")

        data = resp.json()["data"]
        assert data[0]["amount_display"] == "-$5.00"
        assert data[0]["transaction_type"] == "refund"
