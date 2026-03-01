/**
 * Mock data factories for usage page E2E tests.
 *
 * Provides balance, summary, history, and transaction responses
 * matching backend/app/schemas/usage.py and types/usage.ts.
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type { Persona } from "@/types/persona";
import type {
	BalanceResponse,
	CreditTransactionResponse,
	UsageRecordResponse,
	UsageSummaryResponse,
} from "@/types/usage";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const USAGE_RECORD_IDS = ["ur-001", "ur-002", "ur-003"] as const;

export const TRANSACTION_IDS = ["tx-001", "tx-002", "tx-003"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-03-01T12:00:00Z";
const PERSONA_ID = "00000000-0000-4000-a000-000000000077";

// ---------------------------------------------------------------------------
// Persona (required for persona status guard)
// ---------------------------------------------------------------------------

const ONBOARDED_PERSONA: Persona = {
	id: PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000099",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1 555-123-4567",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: "https://linkedin.example.com/in/janedoe",
	portfolio_url: null,
	professional_summary: "Experienced software engineer",
	years_experience: 8,
	current_role: "Senior Engineer",
	current_company: "Acme Corp",
	target_roles: ["Staff Engineer", "Engineering Manager"],
	target_skills: ["Kubernetes", "People Management"],
	stretch_appetite: "Medium",
	commutable_cities: ["San Francisco", "Oakland"],
	max_commute_minutes: 45,
	remote_preference: "Hybrid OK",
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: 180000,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "<25%",
	minimum_fit_threshold: 60,
	auto_draft_threshold: 80,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: "base-resume",
	created_at: NOW,
	updated_at: NOW,
};

/** Onboarded persona list for the persona status guard. */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return { data: [{ ...ONBOARDED_PERSONA }], meta: listMeta(1) };
}

function listMeta(total: number, page = 1, perPage = 50): PaginationMeta {
	return {
		total,
		page,
		per_page: perPage,
		total_pages: Math.ceil(total / perPage),
	};
}

// ---------------------------------------------------------------------------
// Balance
// ---------------------------------------------------------------------------

/** Default balance: $10.50 (green threshold). */
export function balanceResponse(
	balance = "10.500000",
): ApiResponse<BalanceResponse> {
	return {
		data: {
			balance_usd: balance,
			as_of: NOW,
		},
	};
}

// ---------------------------------------------------------------------------
// Usage Summary
// ---------------------------------------------------------------------------

export function usageSummaryResponse(): ApiResponse<UsageSummaryResponse> {
	return {
		data: {
			period_start: "2026-03-01",
			period_end: "2026-03-31",
			total_calls: 42,
			total_input_tokens: 15000,
			total_output_tokens: 5000,
			total_raw_cost_usd: "3.000000",
			total_billed_cost_usd: "3.900000",
			by_task_type: [
				{
					task_type: "extraction",
					call_count: 30,
					input_tokens: 10000,
					output_tokens: 3000,
					billed_cost_usd: "2.340000",
				},
				{
					task_type: "generation",
					call_count: 12,
					input_tokens: 5000,
					output_tokens: 2000,
					billed_cost_usd: "1.560000",
				},
			],
			by_provider: [
				{
					provider: "claude",
					call_count: 35,
					billed_cost_usd: "3.250000",
				},
				{
					provider: "openai",
					call_count: 7,
					billed_cost_usd: "0.650000",
				},
			],
		},
	};
}

/** Summary with zero usage for empty state testing. */
export function emptyUsageSummaryResponse(): ApiResponse<UsageSummaryResponse> {
	return {
		data: {
			period_start: "2026-03-01",
			period_end: "2026-03-31",
			total_calls: 0,
			total_input_tokens: 0,
			total_output_tokens: 0,
			total_raw_cost_usd: "0.000000",
			total_billed_cost_usd: "0.000000",
			by_task_type: [],
			by_provider: [],
		},
	};
}

// ---------------------------------------------------------------------------
// Usage History (Recent Activity)
// ---------------------------------------------------------------------------

const USAGE_RECORDS: UsageRecordResponse[] = [
	{
		id: USAGE_RECORD_IDS[0],
		provider: "claude",
		model: "claude-3-5-sonnet-20241022",
		task_type: "extraction",
		input_tokens: 500,
		output_tokens: 200,
		billed_cost_usd: "0.005850",
		created_at: "2026-03-01T10:00:00Z",
	},
	{
		id: USAGE_RECORD_IDS[1],
		provider: "claude",
		model: "claude-3-5-haiku-20241022",
		task_type: "generation",
		input_tokens: 1000,
		output_tokens: 500,
		billed_cost_usd: "0.001950",
		created_at: "2026-03-01T09:00:00Z",
	},
	{
		id: USAGE_RECORD_IDS[2],
		provider: "openai",
		model: "text-embedding-3-small",
		task_type: "embedding",
		input_tokens: 300,
		output_tokens: 0,
		billed_cost_usd: "0.000039",
		created_at: "2026-03-01T08:00:00Z",
	},
];

/** 3 usage records on a single page. */
export function usageHistoryList(): ApiListResponse<UsageRecordResponse> {
	return { data: [...USAGE_RECORDS], meta: listMeta(3) };
}

/** Empty usage history. */
export function emptyUsageHistoryList(): ApiListResponse<UsageRecordResponse> {
	return { data: [], meta: listMeta(0) };
}

/**
 * Multi-page usage history for pagination testing.
 * Returns page 1 of 2 (per_page=2) with first 2 records.
 */
export function usageHistoryPage1(): ApiListResponse<UsageRecordResponse> {
	return {
		data: [USAGE_RECORDS[0], USAGE_RECORDS[1]],
		meta: { total: 3, page: 1, per_page: 2, total_pages: 2 },
	};
}

/** Page 2 of 2 with last record. */
export function usageHistoryPage2(): ApiListResponse<UsageRecordResponse> {
	return {
		data: [USAGE_RECORDS[2]],
		meta: { total: 3, page: 2, per_page: 2, total_pages: 2 },
	};
}

// ---------------------------------------------------------------------------
// Credit Transactions
// ---------------------------------------------------------------------------

const TRANSACTIONS: CreditTransactionResponse[] = [
	{
		id: TRANSACTION_IDS[0],
		amount_usd: "10.000000",
		transaction_type: "purchase",
		description: "Initial credit purchase",
		created_at: "2026-02-28T12:00:00Z",
	},
	{
		id: TRANSACTION_IDS[1],
		amount_usd: "-0.005850",
		transaction_type: "usage_debit",
		description: "extraction — claude-3-5-sonnet-20241022",
		created_at: "2026-03-01T10:00:00Z",
	},
	{
		id: TRANSACTION_IDS[2],
		amount_usd: "5.000000",
		transaction_type: "admin_grant",
		description: null,
		created_at: "2026-03-01T11:00:00Z",
	},
];

/** 3 credit transactions on a single page. */
export function transactionList(): ApiListResponse<CreditTransactionResponse> {
	return { data: [...TRANSACTIONS], meta: listMeta(3) };
}

/**
 * Multi-page transaction history for pagination testing.
 * Returns page 1 of 2 (per_page=2) with first 2 transactions.
 */
export function transactionPage1(): ApiListResponse<CreditTransactionResponse> {
	return {
		data: [TRANSACTIONS[0], TRANSACTIONS[1]],
		meta: { total: 3, page: 1, per_page: 2, total_pages: 2 },
	};
}

/** Page 2 of 2 with last transaction. */
export function transactionPage2(): ApiListResponse<CreditTransactionResponse> {
	return {
		data: [TRANSACTIONS[2]],
		meta: { total: 3, page: 2, per_page: 2, total_pages: 2 },
	};
}

/** Empty transaction history. */
export function emptyTransactionList(): ApiListResponse<CreditTransactionResponse> {
	return { data: [], meta: listMeta(0) };
}
