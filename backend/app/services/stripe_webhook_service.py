"""Stripe webhook handlers — checkout.session.completed, checkout.session.expired, and charge.refunded.

REQ-029 §7.2, §7.3, §7.4; REQ-030 §7.2, §7.3: Business logic for processing
Stripe webhook events. All handlers follow the "never raise" contract — the
outer function catches all exceptions so the webhook endpoint always returns
200 (prevents Stripe retries).
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

import stripe as stripe_module
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.credit_repository import CreditRepository
from app.repositories.stripe_repository import StripePurchaseRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


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
    # Savepoint ensures CreditTransaction + balance update are atomic —
    # if atomic_credit fails after create flushes, the savepoint rolls back both.
    grant_usd = Decimal(grant_cents) / Decimal(100)
    async with db.begin_nested():
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
    updated = await StripePurchaseRepository.mark_completed(
        db,
        stripe_session_id=session_id,
        stripe_payment_intent=session["payment_intent"],
    )
    if not updated:
        logger.warning(
            "mark_completed found no pending purchase for session %s "
            "(user %s credited — reconciliation may be needed)",
            session_id,
            user_id,
        )


async def handle_checkout_expired(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Mark a pending purchase as expired when Stripe session expires.

    REQ-030 §7.3 (F-07): Handles checkout.session.expired events.
    Always returns normally (never-raise contract).
    """
    try:
        session: dict[str, Any] = event.data.object
        session_id: str = session["id"]
        await StripePurchaseRepository.mark_expired(db, stripe_session_id=session_id)
    except Exception:
        logger.exception("Error processing checkout.session.expired %s", event.id)


async def handle_charge_refunded(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Process a charge.refunded webhook event.

    REQ-029 §7.3: Handles full and partial refunds with cumulative tracking.
    Always returns normally (REQ-029 §7.4).
    """
    try:
        await _process_charge_refunded(db, event=event)
    except Exception:
        logger.exception("Unexpected error processing refund event %s", event.id)


async def _process_charge_refunded(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Inner logic for charge.refunded — separated for exception safety.

    REQ-030 §7.2: Three hardening changes over REQ-029 §7.3:
    (a) Savepoint wraps credit + debit + purchase update for atomicity.
    (b) Cap total_refunded_cents at purchase.amount_cents.
    (c) Null payment_intent guard (early return).
    """
    charge: dict[str, Any] = event.data.object
    event_id: str = event.id

    # REQ-030 §7.2c (F-05): Guard against null payment_intent.
    # Stripe checkout sessions always create a PaymentIntent, but the charge
    # schema has payment_intent as nullable (e.g., legacy direct charges).
    payment_intent_id = charge.get("payment_intent")
    if payment_intent_id is None:
        logger.error(
            "charge.refunded event %s has null payment_intent — skipping",
            event_id,
        )
        return

    # Idempotency check
    existing = await CreditRepository.find_by_stripe_event_id(db, event_id)
    if existing:
        return

    # Find the original purchase by payment_intent
    purchase = await StripePurchaseRepository.find_by_payment_intent(
        db, payment_intent_id
    )
    if not purchase:
        logger.error("No purchase found for payment_intent %s", payment_intent_id)
        return

    # REQ-030 §7.2b (F-04): Cap at purchase amount to prevent over-debit
    # from corrupted or unexpected Stripe data.
    total_refunded_cents = min(int(charge["amount_refunded"]), purchase.amount_cents)
    previous_refunded_cents: int = purchase.refund_amount_cents or 0
    this_refund_cents = total_refunded_cents - previous_refunded_cents
    if this_refund_cents <= 0:
        logger.warning("No new refund amount for charge %s", charge["id"])
        return

    this_refund_usd = Decimal(this_refund_cents) / Decimal(100)

    # REQ-030 §7.2a (F-03): Savepoint wraps all three operations.
    # If any step fails, the savepoint rolls back — no orphaned credit
    # transactions or incorrect balance debits.
    is_full_refund: bool = charge.get("refunded", False)
    async with db.begin_nested():
        await CreditRepository.create(
            db,
            user_id=purchase.user_id,
            amount_usd=-this_refund_usd,
            transaction_type="refund",
            reference_id=charge["id"],
            stripe_event_id=event_id,
            description=f"Refund — ${this_refund_usd:.2f}",
        )
        new_balance = await CreditRepository.atomic_refund_debit(
            db, user_id=purchase.user_id, amount=this_refund_usd
        )
        await StripePurchaseRepository.mark_refunded(
            db,
            purchase_id=purchase.id,
            refund_amount_cents=total_refunded_cents,
            is_full_refund=is_full_refund,
        )

    if new_balance < 0:
        logger.warning(
            "User %s balance went negative (%s) after refund",
            purchase.user_id,
            new_balance,
        )
