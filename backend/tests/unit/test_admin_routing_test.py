"""Tests for POST /admin/routing/test endpoint.

REQ-028 §5: Admin-only endpoint for testing LLM routing configuration.
Verifies auth gates, routing dispatch, fallback behavior, validation,
timeout handling, and provider error handling.

Uses real PostgreSQL via db_session fixture (integration tests).
LLM providers are mocked via dependency injection overrides.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.admin_config import TaskRoutingConfig
from app.models.user import User
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMResponse
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt

# =============================================================================
# Constants
# =============================================================================

_ADMIN_USER_ID = TEST_USER_ID
_ADMIN_EMAIL = "admin-routing-test@test.example.com"
_ENDPOINT = "/api/v1/admin/routing/test"

_MOCK_CLAUDE_MODEL = "claude-3-5-haiku-20241022"
_MOCK_OPENAI_MODEL = "gpt-4o-mini"

_TEST_TASK_TYPE = "extraction"
_TEST_PROMPT = "Test prompt"


# =============================================================================
# Mock helpers
# =============================================================================


def _make_mock_adapter(
    provider_name: str,
    model: str = "test-model",
) -> AsyncMock:
    """Create a mock LLM adapter with a working complete() method."""
    adapter = AsyncMock()
    adapter.provider_name = provider_name

    async def mock_complete(
        messages,  # noqa: ARG001
        task,  # noqa: ARG001
        *,
        model_override=None,
        **kwargs,  # noqa: ARG001
    ):
        return LLMResponse(
            content=f"Test response from {provider_name}",
            model=model_override or model,
            input_tokens=15,
            output_tokens=28,
            finish_reason="stop",
            latency_ms=342.5,
        )

    adapter.complete = AsyncMock(side_effect=mock_complete)
    return adapter


def _test_body(
    task_type: str = _TEST_TASK_TYPE,
    prompt: str = _TEST_PROMPT,
) -> dict:
    """Build a test request body."""
    return {"task_type": task_type, "prompt": prompt}


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
async def mock_adapters() -> dict[str, AsyncMock]:
    """Create mock LLM adapters for all providers."""
    return {
        "claude": _make_mock_adapter("claude", _MOCK_CLAUDE_MODEL),
        "openai": _make_mock_adapter("openai", _MOCK_OPENAI_MODEL),
        "gemini": _make_mock_adapter("gemini", "gemini-2.0-flash"),
    }


@pytest_asyncio.fixture
async def routing_client(
    db_engine,
    admin_user,  # noqa: ARG001
    mock_adapters,
) -> AsyncGenerator[AsyncClient, None]:
    """Admin HTTP client with mocked LLM providers for routing tests."""
    from app.api.deps import get_llm_provider_dep, get_llm_registry_dep
    from app.core.database import get_db
    from app.main import app

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_registry_dep] = lambda: dict(mock_adapters)
    app.dependency_overrides[get_llm_provider_dep] = lambda: mock_adapters["claude"]

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_admin_emails = settings.admin_emails
    original_rate_limit_enabled = settings.rate_limit_enabled
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.admin_emails = _ADMIN_EMAIL
    # Disable rate limiting in tests to avoid flakiness
    settings.rate_limit_enabled = False

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
    settings.rate_limit_enabled = original_rate_limit_enabled
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_llm_registry_dep, None)
    app.dependency_overrides.pop(get_llm_provider_dep, None)


@pytest_asyncio.fixture
async def non_admin_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Non-admin HTTP client for 403 gate test."""
    from app.core.database import get_db
    from app.main import app

    non_admin_id = uuid.UUID("00000000-0000-0000-0000-000000000088")

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            existing = await session.get(User, non_admin_id)
            if existing is None:
                user = User(
                    id=non_admin_id,
                    email="nonadmin-routing@test.example.com",
                    is_admin=False,
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
# Auth gate
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestAuthGate:
    """POST /admin/routing/test requires admin access."""

    async def test_non_admin_gets_403(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403 Forbidden."""
        resp = await non_admin_client.post(_ENDPOINT, json=_test_body())
        assert resp.status_code == 403


# =============================================================================
# Happy path -- routing configured
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestWithRouting:
    """Tests when DB routing is configured for the task type."""

    async def test_dispatches_to_routed_provider(
        self,
        routing_client: AsyncClient,
        db_session: AsyncSession,
        mock_adapters: dict[str, AsyncMock],
    ) -> None:
        """Routing entry for extraction -> openai dispatches to OpenAI adapter."""
        routing = TaskRoutingConfig(
            provider="openai",
            task_type=_TEST_TASK_TYPE,
            model=_MOCK_OPENAI_MODEL,
        )
        db_session.add(routing)
        await db_session.commit()

        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(prompt="Test extraction prompt"),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["provider"] == "openai"
        assert data["model"] == _MOCK_OPENAI_MODEL
        assert data["response"] == "Test response from openai"
        assert data["latency_ms"] == pytest.approx(342.5)
        assert data["input_tokens"] == 15
        assert data["output_tokens"] == 28

        # Verify the openai adapter was called (not claude)
        mock_adapters["openai"].complete.assert_called_once()
        mock_adapters["claude"].complete.assert_not_called()

    async def test_passes_model_override_to_adapter(
        self,
        routing_client: AsyncClient,
        db_session: AsyncSession,
        mock_adapters: dict[str, AsyncMock],
    ) -> None:
        """Routing model is passed as model_override to adapter.complete()."""
        routing = TaskRoutingConfig(
            provider="claude",
            task_type="chat_response",
            model="claude-3-5-sonnet-20241022",
        )
        db_session.add(routing)
        await db_session.commit()

        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(task_type="chat_response", prompt="Hello"),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["model"] == "claude-3-5-sonnet-20241022"

        call_kwargs = mock_adapters["claude"].complete.call_args
        assert call_kwargs.kwargs.get("model_override") == "claude-3-5-sonnet-20241022"


# =============================================================================
# Fallback -- no routing configured
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestFallback:
    """Tests when no DB routing exists for the task type."""

    async def test_falls_back_to_default_provider(
        self,
        routing_client: AsyncClient,
        mock_adapters: dict[str, AsyncMock],
    ) -> None:
        """No routing entry -> uses fallback provider with no model override."""
        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(prompt="Test fallback"),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["provider"] == "claude"
        assert data["model"] == _MOCK_CLAUDE_MODEL
        assert data["response"] == "Test response from claude"

        call_kwargs = mock_adapters["claude"].complete.call_args
        assert call_kwargs.kwargs.get("model_override") is None


# =============================================================================
# Validation
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestValidation:
    """Request body validation tests."""

    async def test_invalid_task_type_rejected(
        self, routing_client: AsyncClient
    ) -> None:
        """Invalid task_type string is rejected."""
        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(task_type="nonexistent_task"),
        )
        assert resp.status_code == 400

    async def test_default_task_type_rejected(
        self, routing_client: AsyncClient
    ) -> None:
        """'_default' is a routing placeholder, not a valid task type for testing."""
        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(task_type="_default"),
        )
        assert resp.status_code == 400

    async def test_empty_prompt_rejected(self, routing_client: AsyncClient) -> None:
        """Empty or whitespace-only prompt is rejected."""
        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(prompt="   "),
        )
        assert resp.status_code == 400

    async def test_prompt_too_long_rejected(self, routing_client: AsyncClient) -> None:
        """Prompt exceeding 1000 chars is rejected."""
        resp = await routing_client.post(
            _ENDPOINT,
            json=_test_body(prompt="x" * 1001),
        )
        assert resp.status_code == 400

    async def test_extra_fields_rejected(self, routing_client: AsyncClient) -> None:
        """Extra fields in request body are rejected (ConfigDict extra=forbid)."""
        body = _test_body()
        body["extra"] = "bad"
        resp = await routing_client.post(_ENDPOINT, json=body)
        assert resp.status_code == 400

    async def test_missing_fields_rejected(self, routing_client: AsyncClient) -> None:
        """Missing required fields are rejected."""
        resp = await routing_client.post(
            _ENDPOINT,
            json={"task_type": _TEST_TASK_TYPE},
        )
        assert resp.status_code == 400


# =============================================================================
# Provider unavailable
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestProviderUnavailable:
    """Tests when routing points to a provider not in the registry."""

    async def test_missing_provider_returns_422(
        self,
        routing_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Routing to a provider without API key returns 422."""
        from app.api.deps import get_llm_registry_dep
        from app.main import app

        # Override registry to only have claude (no openai)
        claude_only = {"claude": _make_mock_adapter("claude")}
        app.dependency_overrides[get_llm_registry_dep] = lambda: claude_only

        routing = TaskRoutingConfig(
            provider="openai",
            task_type=_TEST_TASK_TYPE,
            model=_MOCK_OPENAI_MODEL,
        )
        db_session.add(routing)
        await db_session.commit()

        resp = await routing_client.post(_ENDPOINT, json=_test_body())

        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == "PROVIDER_UNAVAILABLE"
        assert "openai" in error["message"]


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestErrorHandling:
    """Tests for timeout and provider error handling."""

    async def test_timeout_returns_504(
        self,
        routing_client: AsyncClient,
        mock_adapters: dict[str, AsyncMock],
    ) -> None:
        """LLM call exceeding timeout returns 504."""

        async def slow_complete(*args, **kwargs):  # noqa: ARG001
            await asyncio.sleep(60)

        mock_adapters["claude"].complete = AsyncMock(side_effect=slow_complete)

        # Patch timeout to avoid waiting 30s in tests
        import app.api.v1.admin as admin_module

        original_timeout = admin_module._ROUTING_TEST_TIMEOUT
        admin_module._ROUTING_TEST_TIMEOUT = 0.1

        try:
            resp = await routing_client.post(_ENDPOINT, json=_test_body())
        finally:
            admin_module._ROUTING_TEST_TIMEOUT = original_timeout

        assert resp.status_code == 504
        error = resp.json()["error"]
        assert error["code"] == "LLM_TIMEOUT"

    async def test_provider_error_returns_502(
        self,
        routing_client: AsyncClient,
        mock_adapters: dict[str, AsyncMock],
    ) -> None:
        """ProviderError from adapter returns 502 with generic message."""
        mock_adapters["claude"].complete = AsyncMock(
            side_effect=ProviderError("API rate limit exceeded")
        )

        resp = await routing_client.post(_ENDPOINT, json=_test_body())

        assert resp.status_code == 502
        error = resp.json()["error"]
        assert error["code"] == "PROVIDER_ERROR"
        # Generic message — does NOT leak internal provider error details
        assert "returned an error" in error["message"]
        assert "rate limit" not in error["message"].lower()


# =============================================================================
# Response envelope
# =============================================================================


@pytest.mark.asyncio
class TestRoutingTestResponseEnvelope:
    """Tests for correct response structure."""

    async def test_response_matches_spec_shape(
        self, routing_client: AsyncClient
    ) -> None:
        """Response body matches REQ-028 §5.1 envelope."""
        resp = await routing_client.post(_ENDPOINT, json=_test_body())

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert set(data.keys()) == {
            "provider",
            "model",
            "response",
            "latency_ms",
            "input_tokens",
            "output_tokens",
        }

    async def test_no_metering_recorded(
        self,
        routing_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test calls do not create usage records (no metering)."""
        from sqlalchemy import text

        resp = await routing_client.post(_ENDPOINT, json=_test_body())
        assert resp.status_code == 200

        result = await db_session.execute(
            text("SELECT count(*) FROM llm_usage_records WHERE user_id = :uid"),
            {"uid": str(_ADMIN_USER_ID)},
        )
        count = result.scalar()
        assert count == 0
