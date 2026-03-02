/**
 * Admin API resource types matching backend/app/schemas/admin.py.
 *
 * REQ-022 §10: TypeScript interfaces for all admin endpoint resources.
 * All monetary values are strings to preserve decimal precision.
 */

// =============================================================================
// Model Registry
// =============================================================================

export interface ModelRegistryItem {
	id: string;
	provider: string;
	model: string;
	display_name: string;
	model_type: string;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

export interface ModelRegistryCreateRequest {
	provider: string;
	model: string;
	display_name: string;
	model_type: string;
}

export interface ModelRegistryUpdateRequest {
	display_name?: string;
	is_active?: boolean;
	model_type?: string;
}

// =============================================================================
// Pricing Config
// =============================================================================

export interface PricingConfigItem {
	id: string;
	provider: string;
	model: string;
	input_cost_per_1k: string;
	output_cost_per_1k: string;
	margin_multiplier: string;
	effective_date: string;
	is_current: boolean;
	created_at: string;
	updated_at: string;
}

export interface PricingConfigCreateRequest {
	provider: string;
	model: string;
	input_cost_per_1k: string;
	output_cost_per_1k: string;
	margin_multiplier: string;
	effective_date: string;
}

export interface PricingConfigUpdateRequest {
	input_cost_per_1k?: string;
	output_cost_per_1k?: string;
	margin_multiplier?: string;
}

// =============================================================================
// Task Routing
// =============================================================================

export interface TaskRoutingItem {
	id: string;
	provider: string;
	task_type: string;
	model: string;
	model_display_name: string | null;
	created_at: string;
	updated_at: string;
}

export interface TaskRoutingCreateRequest {
	provider: string;
	task_type: string;
	model: string;
}

export interface TaskRoutingUpdateRequest {
	model?: string;
}

// =============================================================================
// Credit Packs
// =============================================================================

export interface CreditPackItem {
	id: string;
	name: string;
	price_cents: number;
	price_display: string;
	credit_amount: number;
	stripe_price_id: string | null;
	display_order: number;
	is_active: boolean;
	description: string | null;
	highlight_label: string | null;
	created_at: string;
	updated_at: string;
}

export interface CreditPackCreateRequest {
	name: string;
	price_cents: number;
	credit_amount: number;
	display_order?: number;
	description?: string | null;
	highlight_label?: string | null;
}

export interface CreditPackUpdateRequest {
	name?: string;
	price_cents?: number;
	credit_amount?: number;
	display_order?: number;
	is_active?: boolean;
	description?: string | null;
	highlight_label?: string | null;
}

// =============================================================================
// System Config
// =============================================================================

export interface SystemConfigItem {
	key: string;
	value: string;
	description: string | null;
	updated_at: string;
}

export interface SystemConfigUpsertRequest {
	value: string;
	description?: string | null;
}

// =============================================================================
// Admin Users
// =============================================================================

export interface AdminUserItem {
	id: string;
	email: string;
	name: string | null;
	is_admin: boolean;
	is_env_protected: boolean;
	balance_usd: string;
	created_at: string;
}

export interface AdminUserUpdateRequest {
	is_admin: boolean;
}

// =============================================================================
// Cache Refresh
// =============================================================================

export interface CacheRefreshResult {
	message: string;
	caching_enabled: boolean;
}
