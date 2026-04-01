"""Stripe webhook router.

REQ-029 §7.1, §5.3; REQ-030 §7.3: Receives Stripe webhook events,
verifies HMAC signatures, and routes to the appropriate handler. Public
endpoint — security comes from signature verification, not JWT authentication.

Rate-limiting exempt (REQ-029 §10.2): Stripe may send bursts of
webhooks; the @limiter.limit decorator is intentionally omitted.

Coordinates with:
  - api/deps.py (DbSession)
  - core/config.py (settings)
  - core/errors.py (APIError)
  - services/billing/stripe_webhook_service.py (handle_charge_refunded,
    handle_checkout_completed, handle_checkout_expired)

Called by: api/v1/router.py.
"""

import logging

import stripe as stripe_module
from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.core.config import settings
from app.core.errors import APIError
from app.services.billing.stripe_webhook_service import (
    handle_charge_refunded,
    handle_checkout_completed,
    handle_checkout_expired,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events.

    REQ-029 §7.1: Reads raw request body, verifies Stripe-Signature
    header via HMAC-SHA256, routes to the appropriate handler, and
    returns 200 OK. Non-2xx responses trigger Stripe retries (§7.4).
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe_module.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret.get_secret_value(),
        )
    except ValueError as err:
        raise APIError(
            code="INVALID_PAYLOAD",
            message="Invalid webhook payload.",
            status_code=400,
        ) from err
    except stripe_module.SignatureVerificationError as err:
        raise APIError(
            code="INVALID_SIGNATURE",
            message="Invalid webhook signature.",
            status_code=401,
        ) from err

    logger.info("Webhook received: %s (event %s)", event.type, event.id)

    match event.type:
        case "checkout.session.completed":
            await handle_checkout_completed(db, event=event)
        case "charge.refunded":
            await handle_charge_refunded(db, event=event)
        case "checkout.session.expired":
            await handle_checkout_expired(db, event=event)
        case _:
            pass  # Ignore unhandled events — return 200 to stop retries

    return {"received": True}
