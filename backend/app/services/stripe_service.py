"""Stripe service — checkout session creation, webhooks, and signup grant.

REQ-029 §6.2, §6.3, §7, §12, §13.3: Business logic for Stripe Checkout
integration. Handles customer management, checkout session creation,
webhook event processing, and signup credit grants.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

import stripe as stripe_module
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient

from app.core.config import settings
from app.core.errors import APIError, InvalidStateError, ValidationError
from app.models.admin_config import FundingPack
from app.repositories.credit_repository import CreditRepository
from app.repositories.stripe_repository import StripePurchaseRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# REQ-029 §13.3: User-safe error messages — never expose Stripe internals.
_DEFAULT_STRIPE_ERROR_MESSAGE = "Payment service error. Please try again."
_STRIPE_ERROR_MESSAGES: dict[type[stripe_module.StripeError], str] = {
    stripe_module.RateLimitError: (
        "Payment service is busy. Please try again in a moment."
    ),
    stripe_module.AuthenticationError: ("Payment service temporarily unavailable."),
    stripe_module.APIConnectionError: (
        "Payment service temporarily unavailable. Please try again."
    ),
    stripe_module.InvalidRequestError: _DEFAULT_STRIPE_ERROR_MESSAGE,
}


class StripeServiceError(APIError):
    """Stripe API call failed (502).

    REQ-029 §13.3: Maps Stripe exceptions to user-safe messages.
    Internal Stripe details (codes, request IDs) are logged, never exposed.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            code="STRIPE_ERROR",
            message=message,
            status_code=502,
        )


def _handle_stripe_error(exc: stripe_module.StripeError) -> StripeServiceError:
    """Map a Stripe exception to a StripeServiceError with user-safe message."""
    user_message = _STRIPE_ERROR_MESSAGES.get(type(exc), _DEFAULT_STRIPE_ERROR_MESSAGE)
    logger.error(
        "Stripe API error: type=%s code=%s",
        type(exc).__name__,
        getattr(exc, "code", "unknown"),
    )
    return StripeServiceError(user_message)


async def get_or_create_customer(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    email: str,
    stripe_client: StripeClient,
) -> str:
    """Get or create a Stripe Customer for a user.

    REQ-029 §6.3: Checks users.stripe_customer_id first. If not set,
    creates a new Stripe Customer via the API and persists the ID.

    Handles concurrent requests via the UNIQUE constraint on
    stripe_customer_id — if a race causes an IntegrityError, re-reads
    the user to return the customer ID set by the winning request.

    Args:
        db: Async database session.
        user_id: User to look up.
        email: User email for the Stripe Customer record.
        stripe_client: Configured StripeClient instance.

    Returns:
        Stripe Customer ID (cus_xxx).

    Raises:
        StripeServiceError: If the Stripe API call fails.
    """
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise ValidationError(f"User {user_id} not found")

    if user.stripe_customer_id:
        return user.stripe_customer_id

    try:
        customer = await stripe_client.v1.customers.create_async(
            params={
                "email": email,
                "metadata": {"zentropy_user_id": str(user_id)},
            }
        )
    except stripe_module.StripeError as exc:
        raise _handle_stripe_error(exc) from exc

    user.stripe_customer_id = customer.id
    try:
        await db.flush()
    except IntegrityError:
        # Race condition: another request set stripe_customer_id first.
        # Roll back the failed flush and re-read the user.
        await db.rollback()
        user = await UserRepository.get_by_id(db, user_id)
        if user and user.stripe_customer_id:
            return user.stripe_customer_id
        raise StripeServiceError(_DEFAULT_STRIPE_ERROR_MESSAGE) from None

    return customer.id


async def create_checkout_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    user_email: str,
    pack: FundingPack,
    stripe_client: StripeClient,
) -> tuple[str, str]:
    """Create a Stripe Checkout Session for a funding pack purchase.

    REQ-029 §6.2: Validates the pack, gets/creates a Stripe Customer,
    creates the hosted checkout session, and records a pending purchase.

    Args:
        db: Async database session.
        user_id: Purchasing user.
        user_email: User email for customer creation.
        pack: FundingPack to purchase (must be active with stripe_price_id).
        stripe_client: Configured StripeClient instance.

    Returns:
        Tuple of (checkout_url, session_id).

    Raises:
        ValidationError: If pack has no stripe_price_id.
        InvalidStateError: If pack is not active.
        StripeServiceError: If a Stripe API call fails.
    """
    if not pack.stripe_price_id:
        raise ValidationError("Pack does not have a stripe_price_id configured")
    if not pack.is_active:
        raise InvalidStateError("Pack is not active and cannot be purchased")

    customer_id = await get_or_create_customer(
        db, user_id=user_id, email=user_email, stripe_client=stripe_client
    )

    # REQ-029 §6.2: {CHECKOUT_SESSION_ID} is a Stripe template variable —
    # Stripe replaces it during redirect. Use double braces in the f-string.
    success_url = (
        f"{settings.frontend_url}/usage"
        f"?status=success&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{settings.frontend_url}/usage?status=cancelled"

    try:
        session = await stripe_client.v1.checkout.sessions.create_async(
            params={
                "customer": customer_id,
                "line_items": [
                    {"price": pack.stripe_price_id, "quantity": 1},
                ],
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "user_id": str(user_id),
                    "pack_id": str(pack.id),
                    "grant_cents": str(pack.grant_cents),
                },
            }
        )
    except stripe_module.StripeError as exc:
        raise _handle_stripe_error(exc) from exc

    if not session.url:
        logger.error("Stripe returned session without URL: %s", session.id)
        raise StripeServiceError(_DEFAULT_STRIPE_ERROR_MESSAGE)

    await StripePurchaseRepository.create(
        db,
        user_id=user_id,
        pack_id=pack.id,
        stripe_session_id=session.id,
        stripe_customer_id=customer_id,
        amount_cents=pack.price_cents,
        grant_cents=pack.grant_cents,
    )

    return session.url, session.id


async def handle_checkout_completed(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Process a checkout.session.completed webhook event.

    REQ-029 §7.2: Verifies payment status, extracts metadata, checks
    idempotency via stripe_event_id, credits the user's balance, and
    marks the purchase as completed.

    Always returns normally (no exceptions) — the webhook endpoint must
    return 200 to prevent Stripe retries (REQ-029 §7.4).
    """
    try:
        await _process_checkout_completed(db, event=event)
    except Exception:
        logger.exception("Unexpected error processing checkout event %s", event.id)


async def _process_checkout_completed(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Inner logic — separated so the outer function catches all exceptions."""
    session: dict[str, Any] = event.data.object
    event_id: str = event.id
    session_id: str = session["id"]
    payment_status: str = session["payment_status"]

    # Only process paid sessions (REQ-029 §7.2)
    if payment_status != "paid":
        logger.warning(
            "Checkout session %s has status %s, skipping",
            session_id,
            payment_status,
        )
        return

    # Extract metadata — skip on missing/invalid fields (REQ-029 §13.2).
    # TypeError guards against metadata being None instead of a dict.
    metadata: dict[str, str] = session.get("metadata", {}) or {}
    try:
        user_id = uuid.UUID(metadata["user_id"])
        grant_cents = int(metadata["grant_cents"])
    except (KeyError, ValueError, TypeError):
        logger.error(
            "Checkout session %s has missing/invalid metadata"
            " (expected user_id, grant_cents)",
            session_id,
        )
        return

    if grant_cents <= 0:
        logger.error(
            "Checkout session %s has non-positive grant_cents: %d",
            session_id,
            grant_cents,
        )
        return

    # Idempotency check — skip if event already processed
    existing = await CreditRepository.find_by_stripe_event_id(db, event_id)
    if existing:
        return

    # Validate user exists
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        logger.error("User %s not found for checkout session %s", user_id, session_id)
        return

    # Credit the balance (REQ-021 §6.7: transaction + atomic update)
    grant_usd = Decimal(grant_cents) / Decimal(100)
    await CreditRepository.create(
        db,
        user_id=user_id,
        amount_usd=grant_usd,
        transaction_type="purchase",
        reference_id=session_id,
        stripe_event_id=event_id,
        description="Funding pack purchase",
    )
    await CreditRepository.atomic_credit(db, user_id=user_id, amount=grant_usd)

    # Update stripe_purchases record
    await StripePurchaseRepository.mark_completed(
        db,
        stripe_session_id=session_id,
        stripe_payment_intent=session["payment_intent"],
    )
