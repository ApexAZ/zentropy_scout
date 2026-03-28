"""StripeClient factory and FastAPI dependency injection.

REQ-029 §5.2: Creates StripeClient instances with pinned API version.
Uses the StripeClient pattern (not deprecated stripe.api_key global).
"""

from typing import Annotated

from fastapi import Depends
from stripe import StripeClient

from app.core.config import settings

# Pin Stripe API version to prevent silent breaking changes from Dashboard updates.
# Update intentionally with testing, not as a surprise from Stripe's rolling updates.
STRIPE_API_VERSION = "2025-12-15.clover"


def get_stripe_client() -> StripeClient:
    """Create a StripeClient instance for Stripe API calls.

    Uses STRIPE_SECRET_KEY from settings (SecretStr, unwrapped here).
    The StripeClient pattern avoids mutable global state.

    Returns:
        Configured StripeClient with pinned API version.
    """
    return StripeClient(
        api_key=settings.stripe_secret_key.get_secret_value(),
        stripe_version=STRIPE_API_VERSION,
    )


StripeClientDep = Annotated[StripeClient, Depends(get_stripe_client)]
