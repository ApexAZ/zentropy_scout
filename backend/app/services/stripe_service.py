"""Stripe service — checkout session creation, webhooks, and signup grant.

REQ-029 §6.2, §6.3, §7, §12, §13.3: Business logic for Stripe Checkout
integration. Handles customer management, checkout session creation,
webhook event processing, and signup credit grants.
"""

import logging
import uuid

import stripe as stripe_module
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient

from app.core.config import settings
from app.core.errors import APIError, InvalidStateError, ValidationError
from app.models.admin_config import FundingPack
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
    """Map a Stripe exception to a StripeServiceError with user-safe message.

    Logs the original error type and code server-side. The returned error
    only contains the user-safe message from the mapping table (REQ-029 §13.3).
    """
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
