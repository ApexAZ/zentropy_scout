/**
 * Usage and billing response types matching backend/app/schemas/usage.py.
 *
 * REQ-020 §8: Response shapes for the 4 usage API endpoints.
 * All monetary values are strings with 6 decimal places from the API;
 * frontend displays 2 decimal places (REQ-020 §2.5).
 */

// ---------------------------------------------------------------------------
// Sub-model interfaces
// ---------------------------------------------------------------------------

/** Usage breakdown for a single task type. */
export interface TaskTypeSummary {
	task_type: string;
	call_count: number;
	input_tokens: number;
	output_tokens: number;
	/** Billed cost as string with 6 decimal places (e.g., "4.230000"). */
	billed_cost_usd: string;
}

/** Usage breakdown for a single provider. */
export interface ProviderSummary {
	provider: string;
	call_count: number;
	/** Billed cost as string with 6 decimal places. */
	billed_cost_usd: string;
}

// ---------------------------------------------------------------------------
// Endpoint response interfaces
// ---------------------------------------------------------------------------

/** Response for GET /api/v1/usage/balance. */
export interface BalanceResponse {
	/** Current balance with 6 decimal places (e.g., "10.500000"). */
	balance_usd: string;
	/** ISO 8601 timestamp when the balance was read. */
	as_of: string;
}

/** Response for GET /api/v1/usage/summary. */
export interface UsageSummaryResponse {
	/** ISO date (YYYY-MM-DD). */
	period_start: string;
	/** ISO date (YYYY-MM-DD). */
	period_end: string;
	total_calls: number;
	total_input_tokens: number;
	total_output_tokens: number;
	/** Total raw provider cost with 6 decimal places. */
	total_raw_cost_usd: string;
	/** Total billed cost after margin with 6 decimal places. */
	total_billed_cost_usd: string;
	by_task_type: TaskTypeSummary[];
	by_provider: ProviderSummary[];
}

/** Response item for GET /api/v1/usage/history. */
export interface UsageRecordResponse {
	id: string;
	provider: string;
	model: string;
	task_type: string;
	input_tokens: number;
	output_tokens: number;
	/** Billed cost with 6 decimal places. */
	billed_cost_usd: string;
	/** ISO 8601 timestamp when the API call was made. */
	created_at: string;
}

/** Response item for GET /api/v1/usage/transactions. */
export interface CreditTransactionResponse {
	id: string;
	/** Signed amount with 6 decimal places (+credit, -debit). */
	amount_usd: string;
	/** One of: purchase, usage_debit, admin_grant, refund. */
	transaction_type: string;
	description: string | null;
	/** ISO 8601 timestamp. */
	created_at: string;
}
