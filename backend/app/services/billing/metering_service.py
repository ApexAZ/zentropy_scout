"""Metering service — DB-backed pricing and cost recording.

REQ-022 §7: Calculates costs for LLM/embedding API calls using
admin-configured pricing from the pricing_config table, with per-model
margin multipliers.
REQ-030 §5.2: Pre-debit reservation via reserve() — estimates worst-case
cost and holds it before the LLM call.
REQ-030 §5.3: Settlement via settle() — atomically records usage, debits
balance, releases hold, and marks reservation as settled within a savepoint.
REQ-030 §5.5: Release via release() — decrements held balance and marks
reservation as released when the LLM call fails.
REQ-030 §5.8: Response metadata persistence via persist_response_metadata()
— best-effort outbox pattern that writes LLM response data to the reservation
row before settle(), enabling the background sweep to retry settlement.

Coordinates with:
  - admin/admin_config_service.py — imports AdminConfigService for pricing lookups

Called by: providers/metered_provider.py, billing/reservation_sweep.py, app/api/deps.py,
and unit tests.
"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NoPricingConfigError, UnregisteredModelError
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.usage_reservation import UsageReservation
from app.services.admin.admin_config_service import AdminConfigService

logger = logging.getLogger(__name__)

_THOUSAND = Decimal(1000)
_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_MAX_INPUT_TOKENS = 4096
_STATUS_HELD = "held"
# AF-05: Smallest positive value for Numeric(10,6). Prevents IntegrityError
# when admin configures zero-cost pricing (PricingConfig allows >= 0 but
# UsageReservation requires estimated_cost_usd > 0).
_MINIMUM_ESTIMATED_COST = Decimal("0.000001")


class _ReservationSweptError(Exception):
    """Raised when settle finds the sweep already handled the reservation.

    Not APIError: sentinel for savepoint rollback, never reaches callers.
    """


class MeteringService:
    """Records LLM/embedding usage and debits user balances.

    REQ-022 §7: Pricing and margins come from the pricing_config table
    via AdminConfigService, enabling per-model margin configuration.

    Args:
        db: Async database session for recording usage.
        admin_config: Service for reading pricing from the database.
    """

    def __init__(
        self,
        db: AsyncSession,
        admin_config: AdminConfigService,
    ) -> None:
        self._db = db
        self._admin_config = admin_config

    async def _get_pricing(
        self, provider: str, model: str
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get (input_per_1k, output_per_1k, margin) from DB.

        REQ-022 §7.3: Checks model registry first, then pricing config.

        Args:
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.

        Returns:
            Tuple of (input_cost_per_1k, output_cost_per_1k, margin_multiplier).

        Raises:
            UnregisteredModelError: If model not in registry or inactive.
            NoPricingConfigError: If no effective pricing exists.
        """
        if not await self._admin_config.is_model_registered(provider, model):
            raise UnregisteredModelError(provider=provider, model=model)

        pricing = await self._admin_config.get_pricing(provider, model)
        if pricing is None:
            raise NoPricingConfigError(provider=provider, model=model)

        return (
            pricing.input_cost_per_1k,
            pricing.output_cost_per_1k,
            pricing.margin_multiplier,
        )

    async def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[Decimal, Decimal]:
        """Calculate raw and billed cost for an API call.

        REQ-022 §7.4: cost = (tokens/1K * price/1K) * per-model margin.

        Args:
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            input_tokens: Input/prompt tokens consumed.
            output_tokens: Output/completion tokens consumed.

        Returns:
            Tuple of (raw_cost_usd, billed_cost_usd).

        Raises:
            UnregisteredModelError: If model not in registry.
            NoPricingConfigError: If no pricing exists for model.
        """
        input_per_1k, output_per_1k, margin = await self._get_pricing(provider, model)

        raw_cost = (
            Decimal(input_tokens) * input_per_1k
            + Decimal(output_tokens) * output_per_1k
        ) / _THOUSAND
        billed_cost = raw_cost * margin
        return raw_cost, billed_cost

    async def reserve(
        self,
        user_id: uuid.UUID,
        task_type: str,
        max_tokens: int | None = None,
        max_input_tokens: int | None = None,
    ) -> UsageReservation:
        """Reserve estimated cost from user's available balance.

        REQ-030 §5.2, AF-03, AF-05: Resolves routing, looks up pricing,
        calculates worst-case cost from input + output token ceilings × prices
        × margin (floored at 0.000001 to satisfy ck_reservation_estimated_positive),
        inserts a UsageReservation, and atomically increments held_balance_usd.

        Args:
            user_id: User making the LLM call.
            task_type: Task type for routing and pricing lookup.
            max_tokens: Output token ceiling. Defaults to 4096 if None or
                negative; 0 is valid (embeddings produce no output tokens).
            max_input_tokens: Input token ceiling. Defaults to 4096 if None
                or negative; 0 is valid.

        Returns:
            UsageReservation with status='held'.

        Raises:
            NoPricingConfigError: If no routing or pricing exists.
            UnregisteredModelError: If the routed model is not registered.
        """
        # 1. Resolve routing
        routing = await self._admin_config.get_routing_for_task(task_type)
        if routing is None:
            raise NoPricingConfigError(provider="unrouted", model=task_type)
        provider, model = routing

        # 2. Look up pricing (validates model registration)
        input_per_1k, output_per_1k, margin = await self._get_pricing(provider, model)

        # 3. Default ceilings (None → default; negative → default; 0 is valid
        #    for embeddings which produce zero output tokens — AF-13)
        if max_tokens is None or max_tokens < 0:
            max_tokens = _DEFAULT_MAX_TOKENS
        if max_input_tokens is None or max_input_tokens < 0:
            max_input_tokens = _DEFAULT_MAX_INPUT_TOKENS

        # 4. Estimated cost: (input_ceiling * input_per_1k + max_tokens * output_per_1k) / 1000 * margin
        # AF-03: Includes input token cost to prevent under-estimation for large-prompt scenarios
        # AF-05: Floor at _MINIMUM_ESTIMATED_COST to satisfy ck_reservation_estimated_positive
        estimated_cost = max(
            (
                Decimal(max_input_tokens) * input_per_1k
                + Decimal(max_tokens) * output_per_1k
            )
            / _THOUSAND
            * margin,
            _MINIMUM_ESTIMATED_COST,
        )

        # 5. Insert reservation
        reservation = UsageReservation(
            user_id=user_id,
            estimated_cost_usd=estimated_cost,
            status=_STATUS_HELD,
            task_type=task_type,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
        )
        self._db.add(reservation)

        # 6. Atomically increment held_balance_usd
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                text(
                    "UPDATE users SET held_balance_usd = held_balance_usd + :amount "
                    "WHERE id = :user_id"
                ),
                {"amount": estimated_cost, "user_id": user_id},
            ),
        )
        if result.rowcount == 0:
            logger.error("Reserve failed: user %s not found", user_id)
            msg = f"User {user_id} not found"
            raise ValueError(msg)

        # 7. Flush and return
        await self._db.flush()
        return reservation

    async def settle(
        self,
        reservation: UsageReservation,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Settle a reservation with actual token counts.

        REQ-030 §5.3: Atomically records usage, creates debit transaction,
        debits balance, releases hold, and updates reservation status.
        All operations are wrapped in a savepoint (begin_nested). If any
        step fails, the savepoint rolls back — reservation stays 'held'
        (fail-closed). The background sweep will release it.

        Args:
            reservation: The held reservation to settle.
            provider: Provider that handled the call (from response).
            model: Exact model identifier (from response).
            input_tokens: Actual input tokens from the response.
            output_tokens: Actual output tokens from the response.
        """
        if reservation.status != _STATUS_HELD:
            logger.warning(
                "Attempted to settle reservation %s with status '%s' (expected 'held')",
                reservation.id,
                reservation.status,
            )
            return

        try:
            async with self._db.begin_nested():
                # 1. Look up pricing
                input_per_1k, output_per_1k, margin = await self._get_pricing(
                    provider, model
                )

                # 2. Calculate actual cost
                raw_cost = (
                    Decimal(input_tokens) * input_per_1k
                    + Decimal(output_tokens) * output_per_1k
                ) / _THOUSAND
                billed_cost = raw_cost * margin

                # 3. Insert usage record
                usage_id = uuid.uuid4()
                usage_record = LLMUsageRecord(
                    id=usage_id,
                    user_id=reservation.user_id,
                    provider=provider,
                    model=model,
                    task_type=reservation.task_type,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    raw_cost_usd=raw_cost,
                    billed_cost_usd=billed_cost,
                    margin_multiplier=margin,
                )
                self._db.add(usage_record)

                # 4. Insert debit transaction
                credit_txn = CreditTransaction(
                    id=uuid.uuid4(),
                    user_id=reservation.user_id,
                    amount_usd=-billed_cost,
                    transaction_type="usage_debit",
                    reference_id=str(usage_id),
                    description=f"{provider}/{model} - {reservation.task_type}",
                )
                self._db.add(credit_txn)

                # 5. Atomic debit + release hold (AF-02: RETURNING for
                # overdraft detection — balance_usd has no CHECK constraint)
                bal_result = await self._db.execute(
                    text(
                        "UPDATE users "
                        "SET balance_usd = balance_usd - :actual, "
                        "    held_balance_usd = held_balance_usd - :estimated "
                        "WHERE id = :user_id "
                        "RETURNING balance_usd"
                    ),
                    {
                        "actual": billed_cost,
                        "estimated": reservation.estimated_cost_usd,
                        "user_id": reservation.user_id,
                    },
                )
                new_balance: Decimal = bal_result.scalar_one()
                if new_balance < 0:
                    logger.error(
                        "Balance overdraft after settlement: user %s, "
                        "reservation %s, debit $%s, new balance $%s",
                        reservation.user_id,
                        reservation.id,
                        billed_cost,
                        new_balance,
                    )

                # 6. Conditional reservation update — prevents settle/sweep
                # race (AF-01). The WHERE status = 'held' guard ensures only
                # one process (settle or sweep) transitions the reservation.
                # If rowcount == 0, the sweep already handled it — raise to
                # trigger savepoint rollback (undoes steps 3-5).
                now = datetime.now(UTC)
                updated = cast(
                    CursorResult[Any],
                    await self._db.execute(
                        text(
                            "UPDATE usage_reservations "
                            "SET status = 'settled', actual_cost_usd = :actual_cost, "
                            "    provider = :prov, model = :model, settled_at = :now "
                            "WHERE id = :id AND status = 'held'"
                        ),
                        {
                            "actual_cost": billed_cost,
                            "prov": provider,
                            "model": model,
                            "now": now,
                            "id": reservation.id,
                        },
                    ),
                )
                if updated.rowcount == 0:
                    msg = f"Reservation {reservation.id} already handled by sweep"
                    raise _ReservationSweptError(msg)

                # Sync in-memory ORM state (DB already updated by SQL above)
                reservation.status = "settled"
                reservation.actual_cost_usd = billed_cost
                reservation.provider = provider
                reservation.model = model
                reservation.settled_at = now

        except _ReservationSweptError:
            logger.warning(
                "Reservation %s was handled by sweep before settlement — "
                "savepoint rolled back, no double-decrement",
                reservation.id,
            )
        except (SQLAlchemyError, NoPricingConfigError, UnregisteredModelError):
            # AF-07: Narrow catch — only expected DB and pricing errors.
            # Programming errors (TypeError, AttributeError) propagate to
            # callers so they are surfaced, not silently swallowed.
            logger.exception(
                "Settlement failed for reservation %s (user %s) — "
                "hold remains active, background sweep will release",
                reservation.id,
                reservation.user_id,
            )

    async def release(
        self,
        reservation: UsageReservation,
    ) -> None:
        """Release a held reservation (LLM call failed).

        REQ-030 §5.5: Atomically decrements held_balance_usd and marks
        reservation as 'released'. If release fails, the hold stays active
        and the background sweep will eventually release it.

        Args:
            reservation: The held reservation to release.
        """
        if reservation.status != _STATUS_HELD:
            logger.warning(
                "Attempted to release reservation %s with status '%s' (expected 'held')",
                reservation.id,
                reservation.status,
            )
            return

        try:
            async with self._db.begin_nested():
                # 1. Conditional reservation update — prevents release/sweep
                # race (AF-01). Claim the reservation before decrementing.
                now = datetime.now(UTC)
                updated = cast(
                    CursorResult[Any],
                    await self._db.execute(
                        text(
                            "UPDATE usage_reservations "
                            "SET status = 'released', settled_at = :now "
                            "WHERE id = :id AND status = 'held'"
                        ),
                        {"now": now, "id": reservation.id},
                    ),
                )
                if updated.rowcount == 0:
                    logger.warning(
                        "Reservation %s was already handled by sweep — "
                        "skipping release",
                        reservation.id,
                    )
                    return

                # 2. Decrement held balance (only if we claimed the reservation)
                await self._db.execute(
                    text(
                        "UPDATE users "
                        "SET held_balance_usd = held_balance_usd - :amount "
                        "WHERE id = :user_id"
                    ),
                    {
                        "amount": reservation.estimated_cost_usd,
                        "user_id": reservation.user_id,
                    },
                )

                # Sync in-memory ORM state
                reservation.status = "released"
                reservation.settled_at = now

            # 3. Flush (outside savepoint)
            await self._db.flush()

        except SQLAlchemyError:
            # AF-07: Narrow catch — only expected DB errors. Programming
            # errors propagate to callers so they are surfaced.
            logger.exception(
                "Release failed for reservation %s (user %s) — "
                "hold remains active, background sweep will release",
                reservation.id,
                reservation.user_id,
            )

    async def persist_response_metadata(
        self,
        reservation: UsageReservation,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Persist LLM response metadata on the reservation row (outbox pattern).

        REQ-030 §5.8: Writes response metadata before settle() so the
        background sweep can retry settlement if settle() fails. Uses
        raw SQL UPDATE with WHERE status = 'held' guard to prevent
        writing to reservations already handled by the sweep.

        Best-effort: catches SQLAlchemyError, logs at error level, does
        NOT re-raise. A persist failure must not prevent settle() from
        being attempted or the response from being returned.

        Does NOT use a savepoint (begin_nested) — this is a simple
        idempotent UPDATE that should not interfere with the subsequent
        settle() savepoint.

        Args:
            reservation: The held reservation to annotate.
            model: Exact model identifier from the LLM response.
            input_tokens: Actual input tokens from the LLM response.
            output_tokens: Actual output tokens from the LLM response.
        """
        try:
            await self._db.execute(
                text(
                    "UPDATE usage_reservations "
                    "SET response_model = :response_model, "
                    "    response_input_tokens = :input_tokens, "
                    "    response_output_tokens = :output_tokens, "
                    "    call_completed_at = :completed_at "
                    "WHERE id = :id AND status = 'held'"
                ),
                {
                    "response_model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "completed_at": datetime.now(UTC),
                    "id": reservation.id,
                },
            )
        except SQLAlchemyError:
            logger.exception(
                "Failed to persist response metadata for reservation %s "
                "(user %s) — settlement will proceed without outbox data",
                reservation.id,
                reservation.user_id,
            )
