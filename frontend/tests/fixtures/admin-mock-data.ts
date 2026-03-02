/**
 * Mock data factories for admin E2E tests.
 *
 * Provides response shapes for all admin CRUD endpoints matching
 * backend/app/schemas/admin.py and frontend/src/types/admin.ts.
 *
 * REQ-022 §15.4: Frontend test scenarios for admin config page.
 */

import type { PaginationMeta } from "@/types/api";
import type {
	AdminUserItem,
	CreditPackItem,
	ModelRegistryItem,
	PricingConfigItem,
	SystemConfigItem,
	TaskRoutingItem,
} from "@/types/admin";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const ADMIN_MODEL_IDS = ["model-001", "model-002", "model-003"] as const;
export const ADMIN_PRICING_IDS = ["pricing-001", "pricing-002"] as const;
export const ADMIN_ROUTING_IDS = ["routing-001", "routing-002"] as const;
export const ADMIN_PACK_IDS = ["pack-001", "pack-002"] as const;
export const ADMIN_USER_IDS = ["user-admin-001", "user-regular-001"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-03-01T12:00:00Z";

function listMeta(total: number, page = 1, perPage = 50): PaginationMeta {
	return {
		total,
		page,
		per_page: perPage,
		total_pages: Math.ceil(total / perPage) || 1,
	};
}

// ---------------------------------------------------------------------------
// Model Registry
// ---------------------------------------------------------------------------

const MODELS: ModelRegistryItem[] = [
	{
		id: ADMIN_MODEL_IDS[0],
		provider: "claude",
		model: "claude-3-5-sonnet-20241022",
		display_name: "Claude 3.5 Sonnet",
		model_type: "llm",
		is_active: true,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: ADMIN_MODEL_IDS[1],
		provider: "claude",
		model: "claude-3-5-haiku-20241022",
		display_name: "Claude 3.5 Haiku",
		model_type: "llm",
		is_active: true,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: ADMIN_MODEL_IDS[2],
		provider: "openai",
		model: "text-embedding-3-small",
		display_name: "Embedding 3 Small",
		model_type: "embedding",
		is_active: false,
		created_at: NOW,
		updated_at: NOW,
	},
];

/** GET /admin/models — list of registered models. */
export function modelsListResponse() {
	return { data: [...MODELS] };
}

/** POST /admin/models — created model response (201). */
export function modelCreatedResponse(): { data: ModelRegistryItem } {
	return { data: { ...MODELS[0], id: "model-new-001" } };
}

/** PATCH /admin/models/:id — updated model response. */
export function modelUpdatedResponse(overrides?: Partial<ModelRegistryItem>): {
	data: ModelRegistryItem;
} {
	return { data: { ...MODELS[0], ...overrides } };
}

// ---------------------------------------------------------------------------
// Pricing Config
// ---------------------------------------------------------------------------

const PRICING: PricingConfigItem[] = [
	{
		id: ADMIN_PRICING_IDS[0],
		provider: "claude",
		model: "claude-3-5-sonnet-20241022",
		input_cost_per_1k: "0.003000",
		output_cost_per_1k: "0.015000",
		margin_multiplier: "1.30",
		effective_date: "2026-01-01",
		is_current: true,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: ADMIN_PRICING_IDS[1],
		provider: "claude",
		model: "claude-3-5-haiku-20241022",
		input_cost_per_1k: "0.000800",
		output_cost_per_1k: "0.004000",
		margin_multiplier: "3.00",
		effective_date: "2026-01-01",
		is_current: true,
		created_at: NOW,
		updated_at: NOW,
	},
];

/** GET /admin/pricing — list of pricing entries. */
export function pricingListResponse() {
	return { data: [...PRICING] };
}

/** POST /admin/pricing — created pricing (201). */
export function pricingCreatedResponse(): { data: PricingConfigItem } {
	return { data: { ...PRICING[0], id: "pricing-new-001" } };
}

// ---------------------------------------------------------------------------
// Task Routing
// ---------------------------------------------------------------------------

const ROUTING: TaskRoutingItem[] = [
	{
		id: ADMIN_ROUTING_IDS[0],
		provider: "claude",
		task_type: "extraction",
		model: "claude-3-5-haiku-20241022",
		model_display_name: "Claude 3.5 Haiku",
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: ADMIN_ROUTING_IDS[1],
		provider: "claude",
		task_type: "_default",
		model: "claude-3-5-sonnet-20241022",
		model_display_name: "Claude 3.5 Sonnet",
		created_at: NOW,
		updated_at: NOW,
	},
];

/** GET /admin/routing — list of routing entries. */
export function routingListResponse() {
	return { data: [...ROUTING] };
}

// ---------------------------------------------------------------------------
// Credit Packs
// ---------------------------------------------------------------------------

const PACKS: CreditPackItem[] = [
	{
		id: ADMIN_PACK_IDS[0],
		name: "Starter",
		price_cents: 500,
		price_display: "$5.00",
		credit_amount: 500,
		stripe_price_id: null,
		display_order: 1,
		is_active: true,
		description: "Good for getting started",
		highlight_label: null,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: ADMIN_PACK_IDS[1],
		name: "Pro",
		price_cents: 2000,
		price_display: "$20.00",
		credit_amount: 2500,
		stripe_price_id: null,
		display_order: 2,
		is_active: true,
		description: "Best value",
		highlight_label: "Best Value",
		created_at: NOW,
		updated_at: NOW,
	},
];

/** GET /admin/credit-packs — list of credit packs. */
export function packsListResponse() {
	return { data: [...PACKS] };
}

// ---------------------------------------------------------------------------
// System Config
// ---------------------------------------------------------------------------

const SYSTEM_CONFIG: SystemConfigItem[] = [
	{
		key: "signup_grant_credits",
		value: "0",
		description: "Credits granted on signup",
		updated_at: NOW,
	},
];

/** GET /admin/config — list of system config entries. */
export function systemConfigListResponse() {
	return { data: [...SYSTEM_CONFIG] };
}

/** PUT /admin/config/:key — upserted config entry. */
export function systemConfigUpsertedResponse(
	key: string,
	value: string,
): { data: SystemConfigItem } {
	return {
		data: { key, value, description: null, updated_at: NOW },
	};
}

// ---------------------------------------------------------------------------
// Admin Users
// ---------------------------------------------------------------------------

const USERS: AdminUserItem[] = [
	{
		id: ADMIN_USER_IDS[0],
		email: "admin@example.com",
		name: "Admin User",
		is_admin: true,
		is_env_protected: true,
		balance_usd: "50.000000",
		created_at: NOW,
	},
	{
		id: ADMIN_USER_IDS[1],
		email: "regular@example.com",
		name: "Regular User",
		is_admin: false,
		is_env_protected: false,
		balance_usd: "10.000000",
		created_at: NOW,
	},
];

/** GET /admin/users — paginated user list. */
export function usersListResponse() {
	return { data: [...USERS], meta: listMeta(2) };
}

/** PATCH /admin/users/:id — toggled admin response. */
export function userToggledResponse(overrides?: Partial<AdminUserItem>): {
	data: AdminUserItem;
} {
	return { data: { ...USERS[1], ...overrides } };
}

// ---------------------------------------------------------------------------
// Cache Refresh
// ---------------------------------------------------------------------------

/** POST /admin/cache/refresh — no-op response. */
export function cacheRefreshResponse() {
	return {
		data: { message: "Cache refresh not applicable", caching_enabled: false },
	};
}

// ---------------------------------------------------------------------------
// Error responses
// ---------------------------------------------------------------------------

/** Standard error response matching backend envelope. */
export function adminErrorResponse(code: string, message: string) {
	return { error: { code, message } };
}
