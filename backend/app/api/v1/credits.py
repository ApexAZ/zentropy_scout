"""Credits API router.

REQ-029 §8.1–§8.3: Endpoints for pack listing (public), checkout session
creation (auth), and purchase history (auth). All follow REQ-006 response
envelope conventions.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.config import settings
from app.core.errors import APIError
from app.core.pagination import PaginationParams, pagination_params
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.core.stripe_client import StripeClientDep
from app.models.admin_config import FundingPack
from app.repositories.credit_repository import CreditRepository
from app.repositories.user_repository import UserRepository
from app.schemas.credits import (
    CheckoutRequest,
    CheckoutResponse,
    PackResponse,
    PurchaseResponse,
    format_usd_display,
)
from app.services.stripe_service import create_checkout_session

router = APIRouter()

# =============================================================================
# Shared types
# =============================================================================

_DECIMAL_FMT = "{:.6f}"
Pagination = Annotated[PaginationParams, Depends(pagination_params)]

# Transaction types visible in purchase history (excludes usage_debit).
_PURCHASE_HISTORY_TYPES = ("purchase", "signup_grant", "admin_grant", "refund")

# REQ-029 §13.1: Error constants for deduplication.
_INVALID_PACK_ID = "INVALID_PACK_ID"
_PACK_NOT_AVAILABLE_MSG = "The requested funding pack is not available."


# =============================================================================
# GET /packs — public pack listing
# =============================================================================


@router.get("/packs")
async def get_packs(
    db: DbSession,
) -> DataResponse[list[PackResponse]]:
    """Return active funding packs with Stripe pricing configured.

    REQ-029 §8.1: Public endpoint — no authentication required.
    Only returns packs that are active and have a stripe_price_id.
    Ordered by display_order ascending.
    """
    stmt = (
        select(FundingPack)
        .where(
            FundingPack.is_active.is_(True),
            FundingPack.stripe_price_id.isnot(None),
        )
        .order_by(FundingPack.display_order.asc())
    )
    result = await db.execute(stmt)
    packs = result.scalars().all()

    return DataResponse(
        data=[
            PackResponse(
                id=str(pack.id),
                name=pack.name,
                price_cents=pack.price_cents,
                price_display=format_usd_display(pack.price_cents),
                grant_cents=pack.grant_cents,
                amount_display=format_usd_display(pack.grant_cents),
                description=pack.description,
                highlight_label=pack.highlight_label,
            )
            for pack in packs
        ]
    )


# =============================================================================
# POST /checkout — create Stripe Checkout Session
# =============================================================================


@router.post("/checkout")
async def post_checkout(
    body: CheckoutRequest,
    user_id: CurrentUserId,
    db: DbSession,
    stripe_client: StripeClientDep,
) -> DataResponse[CheckoutResponse]:
    """Create a Stripe Checkout Session for a funding pack.

    REQ-029 §8.2: Validates pack, checks credits_enabled, creates
    checkout session via Stripe service.

    Raises:
        APIError: INVALID_PACK_ID (400), STRIPE_ERROR (502),
            CREDITS_UNAVAILABLE (503).
    """
    if not settings.credits_enabled:
        raise APIError(
            code="CREDITS_UNAVAILABLE",
            message="Credits system is currently unavailable.",
            status_code=503,
        )

    # Look up and validate the pack
    pack = await db.get(FundingPack, body.pack_id)
    if pack is None or not pack.is_active or not pack.stripe_price_id:
        raise APIError(
            code=_INVALID_PACK_ID,
            message=_PACK_NOT_AVAILABLE_MSG,
            status_code=400,
        )

    # Get user email for Stripe Customer.
    # Security: error uses INVALID_PACK_ID to avoid revealing user existence.
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise APIError(
            code=_INVALID_PACK_ID,
            message=_PACK_NOT_AVAILABLE_MSG,
            status_code=400,
        )

    checkout_url, session_id = await create_checkout_session(
        db,
        user_id=user_id,
        user_email=user.email,
        pack=pack,
        stripe_client=stripe_client,
    )

    return DataResponse(
        data=CheckoutResponse(
            checkout_url=checkout_url,
            session_id=session_id,
        )
    )


# =============================================================================
# GET /purchases — purchase history
# =============================================================================


@router.get("/purchases")
async def get_purchases(
    user_id: CurrentUserId,
    db: DbSession,
    pagination: Pagination,
) -> ListResponse[PurchaseResponse]:
    """Return paginated purchase history for the current user.

    REQ-029 §8.3: Includes purchase, signup_grant, admin_grant, and refund
    transaction types. Excludes usage_debit (internal metering records).
    """
    txns, total = await CreditRepository.list_by_user(
        db,
        user_id,
        offset=pagination.offset,
        limit=pagination.limit,
        transaction_types=_PURCHASE_HISTORY_TYPES,
    )

    return ListResponse(
        data=[
            PurchaseResponse(
                id=str(txn.id),
                amount_usd=_DECIMAL_FMT.format(txn.amount_usd),
                amount_display=format_usd_display(int(txn.amount_usd * Decimal(100))),
                transaction_type=txn.transaction_type,
                description=txn.description,
                created_at=txn.created_at,
            )
            for txn in txns
        ],
        meta=PaginationMeta(
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
        ),
    )
