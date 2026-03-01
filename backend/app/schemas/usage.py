"""Usage and billing response schemas.

REQ-020 §8: Response models for the 4 usage API endpoints.
All monetary values are strings with 6 decimal places per §2.5.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

# =============================================================================
# Sub-models for summary breakdowns
# =============================================================================


class TaskTypeSummary(BaseModel):
    """Usage breakdown for a single task type.

    Attributes:
        task_type: Task type name (extraction, cover_letter, etc.).
        call_count: Number of API calls.
        input_tokens: Total input tokens consumed.
        output_tokens: Total output tokens consumed.
        billed_cost_usd: Total billed cost as string with 6 decimal places.
    """

    model_config = ConfigDict(extra="forbid")

    task_type: str
    call_count: int
    input_tokens: int
    output_tokens: int
    billed_cost_usd: str


class ProviderSummary(BaseModel):
    """Usage breakdown for a single provider.

    Attributes:
        provider: Provider name (claude, openai, gemini).
        call_count: Number of API calls.
        billed_cost_usd: Total billed cost as string with 6 decimal places.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    call_count: int
    billed_cost_usd: str


# =============================================================================
# Endpoint response schemas
# =============================================================================


class BalanceResponse(BaseModel):
    """Response for GET /api/v1/usage/balance.

    REQ-020 §8.1: Returns current balance as a string.

    Attributes:
        balance_usd: Current balance with 6 decimal places.
        as_of: Timestamp when the balance was read.
    """

    model_config = ConfigDict(extra="forbid")

    balance_usd: str
    as_of: datetime


class UsageSummaryResponse(BaseModel):
    """Response for GET /api/v1/usage/summary.

    REQ-020 §8.2: Aggregated usage for a time period.

    Attributes:
        period_start: Start of the reporting period.
        period_end: End of the reporting period.
        total_calls: Total number of API calls.
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens consumed.
        total_raw_cost_usd: Total raw provider cost (6 decimal places).
        total_billed_cost_usd: Total billed cost after margin (6 decimal places).
        by_task_type: Breakdown by task type.
        by_provider: Breakdown by provider.
    """

    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_raw_cost_usd: str
    total_billed_cost_usd: str
    by_task_type: list[TaskTypeSummary]
    by_provider: list[ProviderSummary]


class UsageRecordResponse(BaseModel):
    """Response item for GET /api/v1/usage/history.

    REQ-020 §8.3: Individual usage record (billed cost only, no raw/margin).

    Attributes:
        id: Usage record UUID.
        provider: Provider name.
        model: Exact model identifier.
        task_type: Task type name.
        input_tokens: Input tokens consumed.
        output_tokens: Output tokens consumed.
        billed_cost_usd: Billed cost with 6 decimal places.
        created_at: When the API call was made.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    model: str
    task_type: str
    input_tokens: int
    output_tokens: int
    billed_cost_usd: str
    created_at: datetime


class CreditTransactionResponse(BaseModel):
    """Response item for GET /api/v1/usage/transactions.

    REQ-020 §8.4: Credit transaction (signed amount, no reference_id).

    Attributes:
        id: Transaction UUID.
        amount_usd: Signed amount with 6 decimal places (+credit, -debit).
        transaction_type: One of purchase, usage_debit, admin_grant, refund.
        description: Human-readable description, or None.
        created_at: Transaction timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    amount_usd: str
    transaction_type: str
    description: str | None
    created_at: datetime
