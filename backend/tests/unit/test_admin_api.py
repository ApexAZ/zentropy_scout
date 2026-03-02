"""Tests for admin API endpoints.

REQ-022 §10.1–§10.7: HTTP-level tests for all 7 admin endpoint groups.
Tests verify auth gates (403 for non-admin), correct HTTP status codes
(201 for POST, 204 for DELETE), response envelope shapes, pagination,
and CRUD behavior for all admin resources.

Uses real PostgreSQL via db_session fixture (integration tests).
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.user import User
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt

# =============================================================================
# Constants
# =============================================================================

_ADMIN_USER_ID = TEST_USER_ID
_ADMIN_EMAIL = "admin@test.example.com"
_TODAY = date.today()
_PREFIX = "/api/v1/admin"

_TEST_PROVIDER = "claude"
_TEST_MODEL = "claude-3-5-haiku-20241022"
_TEST_DISPLAY_NAME = "Claude 3.5 Haiku"
_TEST_TASK_TYPE = "extraction"
_TEST_PACK_NAME = "Starter"

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user in the test database."""
    user = User(id=_ADMIN_USER_ID, email=_ADMIN_EMAIL, is_admin=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_client(
    db_engine,
    admin_user,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated admin HTTP client for admin API tests.

    Creates a client with admin JWT and DB override for admin API testing.
    """
    from app.core.database import get_db
    from app.main import app

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_admin_emails = settings.admin_emails
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.admin_emails = _ADMIN_EMAIL

    test_jwt = create_test_jwt(_ADMIN_USER_ID)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.admin_emails = original_admin_emails
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def non_admin_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Non-admin HTTP client for 403 gate tests."""
    from app.core.database import get_db
    from app.main import app

    non_admin_id = uuid.UUID("00000000-0000-0000-0000-000000000077")

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            # Ensure non-admin user exists
            existing = await session.get(User, non_admin_id)
            if existing is None:
                user = User(
                    id=non_admin_id, email="nonadmin@test.example.com", is_admin=False
                )
                session.add(user)
                await session.commit()
            yield session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    test_jwt = create_test_jwt(non_admin_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.pop(get_db, None)


# =============================================================================
# Helpers
# =============================================================================


async def _seed_model(
    client: AsyncClient,
    *,
    provider: str = _TEST_PROVIDER,
    model: str = _TEST_MODEL,
    display_name: str = _TEST_DISPLAY_NAME,
    model_type: str = "llm",
) -> dict:
    """Create a model via API and return the response data."""
    resp = await client.post(
        f"{_PREFIX}/models",
        json={
            "provider": provider,
            "model": model,
            "display_name": display_name,
            "model_type": model_type,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


async def _seed_pricing(
    client: AsyncClient,
    *,
    provider: str = _TEST_PROVIDER,
    model: str = _TEST_MODEL,
    effective_date: str | None = None,
) -> dict:
    """Create a pricing entry via API and return the response data."""
    resp = await client.post(
        f"{_PREFIX}/pricing",
        json={
            "provider": provider,
            "model": model,
            "input_cost_per_1k": "0.001000",
            "output_cost_per_1k": "0.005000",
            "margin_multiplier": "1.30",
            "effective_date": effective_date or _TODAY.isoformat(),
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


async def _seed_pack(
    client: AsyncClient,
    *,
    name: str = _TEST_PACK_NAME,
    price_cents: int = 500,
    credit_amount: int = 100_000,
) -> dict:
    """Create a credit pack via API and return the response data."""
    resp = await client.post(
        f"{_PREFIX}/credit-packs",
        json={
            "name": name,
            "price_cents": price_cents,
            "credit_amount": credit_amount,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


# =============================================================================
# Auth gate tests (403 for non-admin)
# =============================================================================


@pytest.mark.asyncio
class TestAdminAuthGate:
    """All admin endpoints return 403 for non-admin users."""

    async def test_models_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/models returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/models")
        assert resp.status_code == 403

    async def test_pricing_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/pricing returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/pricing")
        assert resp.status_code == 403

    async def test_routing_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/routing returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/routing")
        assert resp.status_code == 403

    async def test_packs_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/credit-packs returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/credit-packs")
        assert resp.status_code == 403

    async def test_config_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/config returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/config")
        assert resp.status_code == 403

    async def test_users_get_403(self, non_admin_client: AsyncClient) -> None:
        """GET /admin/users returns 403 for non-admin."""
        resp = await non_admin_client.get(f"{_PREFIX}/users")
        assert resp.status_code == 403

    async def test_cache_refresh_403(self, non_admin_client: AsyncClient) -> None:
        """POST /admin/cache/refresh returns 403 for non-admin."""
        resp = await non_admin_client.post(f"{_PREFIX}/cache/refresh")
        assert resp.status_code == 403


# =============================================================================
# Model Registry endpoints
# =============================================================================


@pytest.mark.asyncio
class TestModelEndpoints:
    """CRUD operations for /admin/models."""

    async def test_create_model_201(self, admin_client: AsyncClient) -> None:
        """POST /admin/models returns 201 with created model."""
        resp = await admin_client.post(
            f"{_PREFIX}/models",
            json={
                "provider": _TEST_PROVIDER,
                "model": _TEST_MODEL,
                "display_name": _TEST_DISPLAY_NAME,
                "model_type": "llm",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["provider"] == _TEST_PROVIDER
        assert data["model"] == _TEST_MODEL
        assert data["is_active"] is True

    async def test_list_models(self, admin_client: AsyncClient) -> None:
        """GET /admin/models returns data envelope with model list."""
        await _seed_model(admin_client)
        resp = await admin_client.get(f"{_PREFIX}/models")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert len(body["data"]) >= 1

    async def test_list_models_filter_provider(self, admin_client: AsyncClient) -> None:
        """GET /admin/models?provider=claude filters by provider."""
        await _seed_model(admin_client, provider=_TEST_PROVIDER)
        await _seed_model(
            admin_client, provider="openai", model="gpt-4o", display_name="GPT-4o"
        )
        resp = await admin_client.get(
            f"{_PREFIX}/models", params={"provider": _TEST_PROVIDER}
        )
        assert resp.status_code == 200
        models = resp.json()["data"]
        assert all(m["provider"] == _TEST_PROVIDER for m in models)

    async def test_update_model(self, admin_client: AsyncClient) -> None:
        """PATCH /admin/models/:id updates model properties."""
        model = await _seed_model(admin_client)
        resp = await admin_client.patch(
            f"{_PREFIX}/models/{model['id']}",
            json={"display_name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["display_name"] == "Updated Name"

    async def test_delete_model_204(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/models/:id returns 204 on success."""
        model = await _seed_model(admin_client)
        resp = await admin_client.delete(f"{_PREFIX}/models/{model['id']}")
        assert resp.status_code == 204

    async def test_delete_model_in_use_409(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/models/:id returns 409 when model referenced by routing."""
        model = await _seed_model(admin_client)
        # Create routing referencing this model
        await admin_client.post(
            f"{_PREFIX}/routing",
            json={
                "provider": _TEST_PROVIDER,
                "task_type": _TEST_TASK_TYPE,
                "model": _TEST_MODEL,
            },
        )
        resp = await admin_client.delete(f"{_PREFIX}/models/{model['id']}")
        assert resp.status_code == 409


# =============================================================================
# Pricing endpoints
# =============================================================================


@pytest.mark.asyncio
class TestPricingEndpoints:
    """CRUD operations for /admin/pricing."""

    async def test_create_pricing_201(self, admin_client: AsyncClient) -> None:
        """POST /admin/pricing returns 201 with created pricing."""
        await _seed_model(admin_client)
        resp = await admin_client.post(
            f"{_PREFIX}/pricing",
            json={
                "provider": _TEST_PROVIDER,
                "model": _TEST_MODEL,
                "input_cost_per_1k": "0.001000",
                "output_cost_per_1k": "0.005000",
                "margin_multiplier": "1.30",
                "effective_date": _TODAY.isoformat(),
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["input_cost_per_1k"] == "0.001000"
        assert data["is_current"] is True

    async def test_list_pricing_has_is_current(self, admin_client: AsyncClient) -> None:
        """GET /admin/pricing includes computed is_current flag."""
        await _seed_model(admin_client)
        await _seed_pricing(admin_client)
        resp = await admin_client.get(f"{_PREFIX}/pricing")
        assert resp.status_code == 200
        entries = resp.json()["data"]
        assert len(entries) >= 1
        assert "is_current" in entries[0]

    async def test_update_pricing(self, admin_client: AsyncClient) -> None:
        """PATCH /admin/pricing/:id updates pricing fields."""
        await _seed_model(admin_client)
        pricing = await _seed_pricing(admin_client)
        resp = await admin_client.patch(
            f"{_PREFIX}/pricing/{pricing['id']}",
            json={"margin_multiplier": "2.00"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["margin_multiplier"] == "2.000000"

    async def test_delete_pricing_204(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/pricing/:id returns 204 when safe to delete."""
        await _seed_model(admin_client)
        # Create two pricing entries so one can be deleted
        await _seed_pricing(admin_client)
        p2 = await _seed_pricing(
            admin_client,
            effective_date=(_TODAY - timedelta(days=30)).isoformat(),
        )
        resp = await admin_client.delete(f"{_PREFIX}/pricing/{p2['id']}")
        assert resp.status_code == 204


# =============================================================================
# Routing endpoints
# =============================================================================


@pytest.mark.asyncio
class TestRoutingEndpoints:
    """CRUD operations for /admin/routing."""

    async def test_create_routing_201(self, admin_client: AsyncClient) -> None:
        """POST /admin/routing returns 201 with created routing."""
        await _seed_model(admin_client)
        resp = await admin_client.post(
            f"{_PREFIX}/routing",
            json={
                "provider": _TEST_PROVIDER,
                "task_type": _TEST_TASK_TYPE,
                "model": _TEST_MODEL,
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["task_type"] == _TEST_TASK_TYPE

    async def test_list_routing_includes_display_name(
        self, admin_client: AsyncClient
    ) -> None:
        """GET /admin/routing includes model_display_name from registry."""
        await _seed_model(admin_client)
        await admin_client.post(
            f"{_PREFIX}/routing",
            json={
                "provider": _TEST_PROVIDER,
                "task_type": _TEST_TASK_TYPE,
                "model": _TEST_MODEL,
            },
        )
        resp = await admin_client.get(f"{_PREFIX}/routing")
        assert resp.status_code == 200
        entries = resp.json()["data"]
        assert len(entries) >= 1
        assert "model_display_name" in entries[0]
        assert entries[0]["model_display_name"] == _TEST_DISPLAY_NAME

    async def test_update_routing(self, admin_client: AsyncClient) -> None:
        """PATCH /admin/routing/:id updates the routed model."""
        await _seed_model(admin_client)
        # Create a second model to route to
        await _seed_model(
            admin_client,
            model="claude-sonnet-4-20250514",
            display_name="Claude Sonnet 4",
        )
        routing = (
            await admin_client.post(
                f"{_PREFIX}/routing",
                json={
                    "provider": _TEST_PROVIDER,
                    "task_type": _TEST_TASK_TYPE,
                    "model": _TEST_MODEL,
                },
            )
        ).json()["data"]
        resp = await admin_client.patch(
            f"{_PREFIX}/routing/{routing['id']}",
            json={"model": "claude-sonnet-4-20250514"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["model"] == "claude-sonnet-4-20250514"

    async def test_delete_routing_204(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/routing/:id returns 204 on success."""
        await _seed_model(admin_client)
        routing = (
            await admin_client.post(
                f"{_PREFIX}/routing",
                json={
                    "provider": _TEST_PROVIDER,
                    "task_type": _TEST_TASK_TYPE,
                    "model": _TEST_MODEL,
                },
            )
        ).json()["data"]
        resp = await admin_client.delete(f"{_PREFIX}/routing/{routing['id']}")
        assert resp.status_code == 204


# =============================================================================
# Credit Pack endpoints
# =============================================================================


@pytest.mark.asyncio
class TestCreditPackEndpoints:
    """CRUD operations for /admin/credit-packs."""

    async def test_create_pack_201(self, admin_client: AsyncClient) -> None:
        """POST /admin/credit-packs returns 201 with price_display."""
        data = await _seed_pack(admin_client)
        assert data["name"] == _TEST_PACK_NAME
        assert data["price_display"] == "$5.00"
        assert data["price_cents"] == 500

    async def test_list_packs(self, admin_client: AsyncClient) -> None:
        """GET /admin/credit-packs returns data envelope."""
        await _seed_pack(admin_client)
        resp = await admin_client.get(f"{_PREFIX}/credit-packs")
        assert resp.status_code == 200
        assert "data" in resp.json()

    async def test_update_pack(self, admin_client: AsyncClient) -> None:
        """PATCH /admin/credit-packs/:id updates pack properties."""
        pack = await _seed_pack(admin_client)
        resp = await admin_client.patch(
            f"{_PREFIX}/credit-packs/{pack['id']}",
            json={"name": "Pro"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Pro"

    async def test_delete_pack_204(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/credit-packs/:id returns 204."""
        pack = await _seed_pack(admin_client)
        resp = await admin_client.delete(f"{_PREFIX}/credit-packs/{pack['id']}")
        assert resp.status_code == 204


# =============================================================================
# System Config endpoints
# =============================================================================


@pytest.mark.asyncio
class TestSystemConfigEndpoints:
    """CRUD operations for /admin/config."""

    async def test_upsert_config_200(self, admin_client: AsyncClient) -> None:
        """PUT /admin/config/:key creates or updates a config entry."""
        resp = await admin_client.put(
            f"{_PREFIX}/config/signup_grant_credits",
            json={"value": "5000", "description": "Credits on signup"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["key"] == "signup_grant_credits"
        assert data["value"] == "5000"

    async def test_list_config(self, admin_client: AsyncClient) -> None:
        """GET /admin/config returns data envelope."""
        await admin_client.put(
            f"{_PREFIX}/config/test_key",
            json={"value": "test_value"},
        )
        resp = await admin_client.get(f"{_PREFIX}/config")
        assert resp.status_code == 200
        assert "data" in resp.json()

    async def test_delete_config_204(self, admin_client: AsyncClient) -> None:
        """DELETE /admin/config/:key returns 204."""
        await admin_client.put(
            f"{_PREFIX}/config/temp_key",
            json={"value": "temp_value"},
        )
        resp = await admin_client.delete(f"{_PREFIX}/config/temp_key")
        assert resp.status_code == 204


# =============================================================================
# Admin Users endpoints
# =============================================================================


@pytest.mark.asyncio
class TestAdminUsersEndpoints:
    """CRUD operations for /admin/users."""

    async def test_list_users_paginated(self, admin_client: AsyncClient) -> None:
        """GET /admin/users returns paginated response with meta."""
        resp = await admin_client.get(f"{_PREFIX}/users")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        meta = body["meta"]
        assert "total" in meta
        assert "page" in meta
        assert "per_page" in meta
        assert "total_pages" in meta

    async def test_list_users_filter_admin(self, admin_client: AsyncClient) -> None:
        """GET /admin/users?is_admin=true filters admin users."""
        resp = await admin_client.get(f"{_PREFIX}/users", params={"is_admin": "true"})
        assert resp.status_code == 200
        users = resp.json()["data"]
        assert all(u["is_admin"] is True for u in users)

    async def test_user_response_has_required_fields(
        self, admin_client: AsyncClient
    ) -> None:
        """Admin user response includes is_env_protected and balance_usd."""
        resp = await admin_client.get(f"{_PREFIX}/users")
        assert resp.status_code == 200
        users = resp.json()["data"]
        assert len(users) >= 1
        user = users[0]
        assert "is_env_protected" in user
        assert "balance_usd" in user
        assert "is_admin" in user

    async def test_toggle_admin_promotes_user(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PATCH /admin/users/:id promotes a non-admin user to admin."""
        # Create a non-admin target user directly in DB
        target_id = uuid.UUID("00000000-0000-0000-0000-000000000088")
        target = User(id=target_id, email="target@test.example.com", is_admin=False)
        db_session.add(target)
        await db_session.commit()

        resp = await admin_client.patch(
            f"{_PREFIX}/users/{target_id}",
            json={"is_admin": True},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_admin"] is True

    async def test_self_demotion_409(self, admin_client: AsyncClient) -> None:
        """PATCH /admin/users/:id returns 409 when demoting self."""
        resp = await admin_client.patch(
            f"{_PREFIX}/users/{str(_ADMIN_USER_ID)}",
            json={"is_admin": False},
        )
        assert resp.status_code == 409


# =============================================================================
# Cache refresh endpoint
# =============================================================================


@pytest.mark.asyncio
class TestCacheRefreshEndpoint:
    """POST /admin/cache/refresh returns no-op response for MVP."""

    async def test_cache_refresh_200(self, admin_client: AsyncClient) -> None:
        """POST /admin/cache/refresh returns 200 with caching_enabled=false."""
        resp = await admin_client.post(f"{_PREFIX}/cache/refresh")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["caching_enabled"] is False
        assert "message" in data
