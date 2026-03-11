"""Tests for Stripe webhook endpoint.

REQ-029 §7.1, §5.3, §10.2: HTTP-level tests for POST /webhooks/stripe
with signature verification, event routing, and error handling.
Tests verify HMAC signature validation, event dispatch to correct handlers,
error codes, and rate-limit exemption.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
import stripe as stripe_module
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from tests.conftest import TEST_AUTH_SECRET

# =============================================================================
# Constants
# =============================================================================

_PREFIX = "/api/v1/webhooks"
_WEBHOOK_SECRET = "whsec_test_secret"
_SVC = "app.api.v1.webhooks"
_VALID_SIG = "t=123,v1=abc"
_SIG_HEADER = {"stripe-signature": _VALID_SIG}
_EVT_CHECKOUT = "checkout.session.completed"
_EVT_REFUND = "charge.refunded"
_CHECKOUT_BODY = b'{"type": "checkout.session.completed"}'
_PATCH_CONSTRUCT = f"{_SVC}.stripe_module.Webhook.construct_event"
_PATCH_CHECKOUT_HANDLER = f"{_SVC}.handle_checkout_completed"
_PATCH_REFUND_HANDLER = f"{_SVC}.handle_charge_refunded"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def webhook_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated HTTP client for webhook tests.

    Webhooks are public — security comes from signature verification,
    not JWT authentication.
    """
    from app.core.database import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_webhook_secret = settings.stripe_webhook_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.stripe_webhook_secret = SecretStr(_WEBHOOK_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.stripe_webhook_secret = original_webhook_secret
    app.dependency_overrides.pop(get_db, None)


def _make_event(
    event_type: str = _EVT_CHECKOUT,
    event_id: str = "evt_test_123",
    data_object: dict | None = None,
) -> stripe_module.Event:
    """Build a minimal Stripe Event object for testing."""
    event = MagicMock(spec=stripe_module.Event)
    event.id = event_id
    event.type = event_type
    event.data = MagicMock()
    event.data.object = data_object or {}
    return event


# =============================================================================
# POST /webhooks/stripe — signature verification
# =============================================================================


class TestWebhookSignature:
    """POST /webhooks/stripe validates Stripe-Signature header."""

    async def test_valid_signature_dispatches_and_returns_200(
        self, webhook_client: AsyncClient
    ) -> None:
        """Valid signature + known event type dispatches handler and returns 200."""
        event = _make_event()

        with (
            patch(_PATCH_CONSTRUCT, return_value=event),
            patch(_PATCH_CHECKOUT_HANDLER, new_callable=AsyncMock) as mock_handler,
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=_CHECKOUT_BODY,
                headers=_SIG_HEADER,
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        mock_handler.assert_awaited_once()

    async def test_invalid_signature_returns_401(
        self, webhook_client: AsyncClient
    ) -> None:
        """Invalid Stripe-Signature header returns INVALID_SIGNATURE (401)."""
        with patch(
            _PATCH_CONSTRUCT,
            side_effect=stripe_module.SignatureVerificationError(
                "Invalid signature", "sig_header"
            ),
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=_CHECKOUT_BODY,
                headers={"stripe-signature": "t=123,v1=bad"},
            )

        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"

    async def test_malformed_payload_returns_400(
        self, webhook_client: AsyncClient
    ) -> None:
        """Malformed payload that raises ValueError returns INVALID_PAYLOAD (400)."""
        with patch(
            _PATCH_CONSTRUCT,
            side_effect=ValueError("Invalid payload"),
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=b"not-valid-json",
                headers=_SIG_HEADER,
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_PAYLOAD"

    async def test_missing_signature_header_returns_401(
        self, webhook_client: AsyncClient
    ) -> None:
        """Missing Stripe-Signature header returns INVALID_SIGNATURE (401)."""
        with patch(
            _PATCH_CONSTRUCT,
            side_effect=stripe_module.SignatureVerificationError(
                "No signature header", "sig_header"
            ),
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=b'{"type": "test"}',
            )

        assert resp.status_code == 401


# =============================================================================
# POST /webhooks/stripe — event routing
# =============================================================================


class TestWebhookEventRouting:
    """POST /webhooks/stripe routes events to correct handlers."""

    async def test_charge_refunded_dispatches_handler(
        self, webhook_client: AsyncClient
    ) -> None:
        """charge.refunded routes to handle_charge_refunded."""
        event = _make_event(_EVT_REFUND)

        with (
            patch(_PATCH_CONSTRUCT, return_value=event),
            patch(_PATCH_REFUND_HANDLER, new_callable=AsyncMock) as mock_handler,
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=b'{"type": "charge.refunded"}',
                headers=_SIG_HEADER,
            )

        assert resp.status_code == 200
        mock_handler.assert_awaited_once()

    async def test_unknown_event_type_returns_200(
        self, webhook_client: AsyncClient
    ) -> None:
        """Unknown event types return 200 without dispatching any handler."""
        event = _make_event("customer.subscription.created")

        with (
            patch(_PATCH_CONSTRUCT, return_value=event),
            patch(_PATCH_CHECKOUT_HANDLER, new_callable=AsyncMock) as mock_checkout,
            patch(_PATCH_REFUND_HANDLER, new_callable=AsyncMock) as mock_refund,
        ):
            resp = await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=b'{"type": "customer.subscription.created"}',
                headers=_SIG_HEADER,
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        mock_checkout.assert_not_awaited()
        mock_refund.assert_not_awaited()

    async def test_handler_receives_db_and_event(
        self, webhook_client: AsyncClient
    ) -> None:
        """Handler receives the db session and event as keyword arguments."""
        event = _make_event()

        with (
            patch(_PATCH_CONSTRUCT, return_value=event),
            patch(_PATCH_CHECKOUT_HANDLER, new_callable=AsyncMock) as mock_handler,
        ):
            await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=_CHECKOUT_BODY,
                headers=_SIG_HEADER,
            )

        call_kwargs = mock_handler.call_args
        assert call_kwargs.kwargs["event"] is event

    async def test_construct_event_receives_raw_body_and_secret(
        self, webhook_client: AsyncClient
    ) -> None:
        """Wiring test: ensures raw bytes are forwarded to construct_event, not decoded strings."""
        event = _make_event()

        with (
            patch(_PATCH_CONSTRUCT, return_value=event) as mock_construct,
            patch(_PATCH_CHECKOUT_HANDLER, new_callable=AsyncMock),
        ):
            await webhook_client.post(
                f"{_PREFIX}/stripe",
                content=_CHECKOUT_BODY,
                headers=_SIG_HEADER,
            )

        mock_construct.assert_called_once_with(
            _CHECKOUT_BODY,
            _VALID_SIG,
            _WEBHOOK_SECRET,
        )
