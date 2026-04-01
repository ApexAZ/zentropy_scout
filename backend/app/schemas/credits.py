"""Credit endpoint request/response schemas.

REQ-029 §8.1–§8.3: Pydantic models for the credit API endpoints —
pack listing, checkout session creation, and purchase history.

All monetary values are serialized as strings to preserve decimal precision.
All schemas use ConfigDict(extra="forbid") to reject unexpected fields.

Coordinates with:
  - (no internal app imports — standalone Pydantic schemas)

Called by: api/v1/credits.py.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


def format_usd_display(cents: int) -> str:
    """Format cents as a USD display string.

    Args:
        cents: Amount in USD cents (e.g. 500).

    Returns:
        Formatted string (e.g. "$5.00").
    """
    if cents < 0:
        return f"-${abs(cents) / 100:.2f}"
    return f"${cents / 100:.2f}"


# =============================================================================
# Checkout
# =============================================================================


class CheckoutRequest(BaseModel):
    """Request schema for POST /api/v1/credits/checkout.

    REQ-029 §8.2: Initiates a Stripe Checkout session for a funding pack.

    Attributes:
        pack_id: UUID of the funding pack to purchase.
    """

    model_config = ConfigDict(extra="forbid")

    pack_id: uuid.UUID


class CheckoutResponse(BaseModel):
    """Response schema for POST /api/v1/credits/checkout.

    REQ-029 §8.2: Returns the Stripe hosted checkout URL for redirect.

    Attributes:
        checkout_url: Full Stripe hosted checkout URL.
        session_id: Stripe Checkout Session ID.
    """

    model_config = ConfigDict(extra="forbid")

    checkout_url: str
    session_id: str


# =============================================================================
# Pack Listing
# =============================================================================


class PackResponse(BaseModel):
    """Response schema for GET /api/v1/credits/packs.

    REQ-029 §8.1: Public pricing data for a single funding pack.

    Attributes:
        id: Pack UUID as string.
        name: Pack name (e.g. "Standard").
        price_cents: Price in USD cents.
        price_display: Formatted price (e.g. "$5.00").
        grant_cents: USD cents granted to balance.
        amount_display: Formatted grant amount (e.g. "$5.00").
        description: Human-readable description, or None.
        highlight_label: Optional badge label (e.g. "Most Popular").
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    price_cents: int
    price_display: str
    grant_cents: int
    amount_display: str
    description: str | None = None
    highlight_label: str | None = None


# =============================================================================
# Purchase History
# =============================================================================


class PurchaseResponse(BaseModel):
    """Response item for GET /api/v1/credits/purchases.

    REQ-029 §8.3: A credit transaction visible in purchase history.

    Attributes:
        id: Transaction UUID as string.
        amount_usd: Signed amount with 6 decimal places.
        amount_display: Formatted display (e.g. "$10.00" or "-$5.00").
        transaction_type: One of purchase, signup_grant, admin_grant, refund.
        description: Human-readable description, or None.
        created_at: Transaction timestamp (ISO 8601).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    amount_usd: str
    amount_display: str
    transaction_type: str
    description: str | None = None
    created_at: datetime
