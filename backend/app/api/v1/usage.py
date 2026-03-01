"""Usage API router.

REQ-020 §8: Endpoints for balance, usage summary, history, and transactions.
All endpoints require authentication. Monetary values are strings with 6 decimals.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUserId, DbSession
from app.core.pagination import PaginationParams, pagination_params
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.repositories.credit_repository import CreditRepository
from app.repositories.usage_repository import UsageRepository
from app.schemas.usage import (
    BalanceResponse,
    CreditTransactionResponse,
    ProviderSummary,
    TaskTypeSummary,
    UsageRecordResponse,
    UsageSummaryResponse,
)

router = APIRouter()

# =============================================================================
# Shared types
# =============================================================================

_DECIMAL_FMT = "{:.6f}"
Pagination = Annotated[PaginationParams, Depends(pagination_params)]

_VALID_TRANSACTION_TYPES = Literal["purchase", "usage_debit", "admin_grant", "refund"]

PeriodStart = Annotated[
    date | None,
    Query(
        description="Start of period (ISO 8601 date). Defaults to first of current month."
    ),
]
PeriodEnd = Annotated[
    date | None,
    Query(description="End of period (ISO 8601 date). Defaults to today."),
]
TaskTypeFilter = Annotated[
    str | None,
    Query(max_length=50, description="Filter by task type"),
]
ProviderFilter = Annotated[
    str | None,
    Query(max_length=20, description="Filter by provider"),
]
TransactionTypeFilter = Annotated[
    _VALID_TRANSACTION_TYPES | None,
    Query(description="Filter: purchase, usage_debit, admin_grant, refund"),
]


# =============================================================================
# GET /balance
# =============================================================================


@router.get("/balance")
async def get_balance(
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[BalanceResponse]:
    """Return the user's current balance.

    REQ-020 §8.1: No query parameters. Returns balance_usd and as_of.
    """
    balance = await CreditRepository.get_balance(db, user_id)
    return DataResponse(
        data=BalanceResponse(
            balance_usd=_DECIMAL_FMT.format(balance),
            as_of=datetime.now(UTC),
        )
    )


# =============================================================================
# GET /summary
# =============================================================================


@router.get("/summary")
async def get_summary(
    user_id: CurrentUserId,
    db: DbSession,
    period_start: PeriodStart = None,
    period_end: PeriodEnd = None,
) -> DataResponse[UsageSummaryResponse]:
    """Return aggregated usage for a time period.

    REQ-020 §8.2: Defaults to current calendar month. Returns totals
    and breakdowns by task_type and provider.
    """
    today = datetime.now(UTC).date()
    start = period_start or today.replace(day=1)
    end = period_end or today

    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_DATE_RANGE",
                "message": "period_start must be on or before period_end",
            },
        )

    # Convert date to datetime for repository query
    start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)
    # End is inclusive — use start of next day as exclusive upper bound
    end_dt = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)

    summary = await UsageRepository.get_summary(db, user_id, start_dt, end_dt)

    return DataResponse(
        data=UsageSummaryResponse(
            period_start=start,
            period_end=end,
            total_calls=summary["total_calls"],
            total_input_tokens=summary["total_input_tokens"],
            total_output_tokens=summary["total_output_tokens"],
            total_raw_cost_usd=_DECIMAL_FMT.format(summary["total_raw_cost_usd"]),
            total_billed_cost_usd=_DECIMAL_FMT.format(summary["total_billed_cost_usd"]),
            by_task_type=[
                TaskTypeSummary(
                    task_type=entry["task_type"],
                    call_count=entry["call_count"],
                    input_tokens=entry["input_tokens"],
                    output_tokens=entry["output_tokens"],
                    billed_cost_usd=_DECIMAL_FMT.format(entry["billed_cost_usd"]),
                )
                for entry in summary["by_task_type"]
            ],
            by_provider=[
                ProviderSummary(
                    provider=entry["provider"],
                    call_count=entry["call_count"],
                    billed_cost_usd=_DECIMAL_FMT.format(entry["billed_cost_usd"]),
                )
                for entry in summary["by_provider"]
            ],
        )
    )


# =============================================================================
# GET /history
# =============================================================================


@router.get("/history")
async def get_history(
    user_id: CurrentUserId,
    db: DbSession,
    pagination: Pagination,
    task_type: TaskTypeFilter = None,
    provider: ProviderFilter = None,
) -> ListResponse[UsageRecordResponse]:
    """Return paginated usage record history.

    REQ-020 §8.3: Individual records expose billed_cost_usd only.
    Does not expose raw_cost_usd or margin_multiplier.
    """
    records, total = await UsageRepository.list_by_user(
        db,
        user_id,
        offset=pagination.offset,
        limit=pagination.limit,
        task_type=task_type,
        provider=provider,
    )

    return ListResponse(
        data=[
            UsageRecordResponse(
                id=str(record.id),
                provider=record.provider,
                model=record.model,
                task_type=record.task_type,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                billed_cost_usd=_DECIMAL_FMT.format(record.billed_cost_usd),
                created_at=record.created_at,
            )
            for record in records
        ],
        meta=PaginationMeta(
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
        ),
    )


# =============================================================================
# GET /transactions
# =============================================================================


@router.get("/transactions")
async def get_transactions(
    user_id: CurrentUserId,
    db: DbSession,
    pagination: Pagination,
    type: TransactionTypeFilter = None,  # noqa: A002 — matches REQ-020 §8.4 query param name
) -> ListResponse[CreditTransactionResponse]:
    """Return paginated credit transaction history.

    REQ-020 §8.4: Signed amounts. Does not expose reference_id.
    """
    txns, total = await CreditRepository.list_by_user(
        db,
        user_id,
        offset=pagination.offset,
        limit=pagination.limit,
        transaction_type=type,
    )

    return ListResponse(
        data=[
            CreditTransactionResponse(
                id=str(txn.id),
                amount_usd=_DECIMAL_FMT.format(txn.amount_usd),
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
