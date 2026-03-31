/**
 * Admin API client functions.
 *
 * REQ-022 §11: Typed functions for all admin CRUD endpoints.
 * All functions use the shared apiGet/apiPost/apiPatch/apiPut/apiDelete
 * wrappers from api-client.ts.
 *
 * @module lib/api/admin
 * @coordinates-with api-client (shared HTTP wrappers),
 *   types/admin (all request/response shapes),
 *   components/admin/* tabs (models, pricing, routing, packs, system, users)
 */

import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	AdminUserItem,
	AdminUserUpdateRequest,
	CacheRefreshResult,
	FundingPackCreateRequest,
	FundingPackItem,
	FundingPackUpdateRequest,
	ModelRegistryCreateRequest,
	ModelRegistryItem,
	ModelRegistryUpdateRequest,
	PricingConfigCreateRequest,
	PricingConfigItem,
	PricingConfigUpdateRequest,
	RoutingTestRequest,
	RoutingTestResponse,
	SystemConfigItem,
	SystemConfigUpsertRequest,
	TaskRoutingCreateRequest,
	TaskRoutingItem,
	TaskRoutingUpdateRequest,
} from "@/types/admin";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api-client";

type QueryParamValue = string | number | boolean | undefined | null;

// =============================================================================
// Model Registry
// =============================================================================

export async function fetchModels(
	params?: Record<string, QueryParamValue>,
): Promise<ApiResponse<ModelRegistryItem[]>> {
	return apiGet("/admin/models", params);
}

export async function createModel(
	body: ModelRegistryCreateRequest,
): Promise<ApiResponse<ModelRegistryItem>> {
	return apiPost("/admin/models", body);
}

export async function updateModel(
	id: string,
	body: ModelRegistryUpdateRequest,
): Promise<ApiResponse<ModelRegistryItem>> {
	return apiPatch(`/admin/models/${encodeURIComponent(id)}`, body);
}

export async function deleteModel(id: string): Promise<void> {
	return apiDelete(`/admin/models/${encodeURIComponent(id)}`);
}

// =============================================================================
// Pricing Config
// =============================================================================

export async function fetchPricing(
	params?: Record<string, QueryParamValue>,
): Promise<ApiResponse<PricingConfigItem[]>> {
	return apiGet("/admin/pricing", params);
}

export async function createPricing(
	body: PricingConfigCreateRequest,
): Promise<ApiResponse<PricingConfigItem>> {
	return apiPost("/admin/pricing", body);
}

export async function updatePricing(
	id: string,
	body: PricingConfigUpdateRequest,
): Promise<ApiResponse<PricingConfigItem>> {
	return apiPatch(`/admin/pricing/${encodeURIComponent(id)}`, body);
}

export async function deletePricing(id: string): Promise<void> {
	return apiDelete(`/admin/pricing/${encodeURIComponent(id)}`);
}

// =============================================================================
// Task Routing
// =============================================================================

export async function fetchRouting(
	params?: Record<string, QueryParamValue>,
): Promise<ApiResponse<TaskRoutingItem[]>> {
	return apiGet("/admin/routing", params);
}

export async function createRouting(
	body: TaskRoutingCreateRequest,
): Promise<ApiResponse<TaskRoutingItem>> {
	return apiPost("/admin/routing", body);
}

export async function updateRouting(
	id: string,
	body: TaskRoutingUpdateRequest,
): Promise<ApiResponse<TaskRoutingItem>> {
	return apiPatch(`/admin/routing/${encodeURIComponent(id)}`, body);
}

export async function deleteRouting(id: string): Promise<void> {
	return apiDelete(`/admin/routing/${encodeURIComponent(id)}`);
}

/** REQ-028 §5.1: Test a routing configuration by sending a prompt to the configured provider. */
export async function testRouting(
	body: RoutingTestRequest,
): Promise<ApiResponse<RoutingTestResponse>> {
	return apiPost("/admin/routing/test", body);
}

/** REQ-028 §6.1: Fetch providers that have API keys configured. */
export async function fetchAvailableProviders(): Promise<
	ApiResponse<string[]>
> {
	return apiGet("/admin/available-providers");
}

// =============================================================================
// Funding Packs
// =============================================================================

export async function fetchPacks(): Promise<ApiResponse<FundingPackItem[]>> {
	return apiGet("/admin/funding-packs");
}

export async function createPack(
	body: FundingPackCreateRequest,
): Promise<ApiResponse<FundingPackItem>> {
	return apiPost("/admin/funding-packs", body);
}

export async function updatePack(
	id: string,
	body: FundingPackUpdateRequest,
): Promise<ApiResponse<FundingPackItem>> {
	return apiPatch(`/admin/funding-packs/${encodeURIComponent(id)}`, body);
}

export async function deletePack(id: string): Promise<void> {
	return apiDelete(`/admin/funding-packs/${encodeURIComponent(id)}`);
}

// =============================================================================
// System Config
// =============================================================================

export async function fetchConfig(): Promise<ApiResponse<SystemConfigItem[]>> {
	return apiGet("/admin/config");
}

export async function upsertConfig(
	key: string,
	body: SystemConfigUpsertRequest,
): Promise<ApiResponse<SystemConfigItem>> {
	return apiPut(`/admin/config/${encodeURIComponent(key)}`, body);
}

export async function deleteConfig(key: string): Promise<void> {
	return apiDelete(`/admin/config/${encodeURIComponent(key)}`);
}

// =============================================================================
// Admin Users
// =============================================================================

export async function fetchUsers(
	params?: Record<string, QueryParamValue>,
): Promise<ApiListResponse<AdminUserItem>> {
	return apiGet("/admin/users", params);
}

export async function toggleAdmin(
	id: string,
	isAdmin: boolean,
): Promise<ApiResponse<AdminUserItem>> {
	const body: AdminUserUpdateRequest = { is_admin: isAdmin };
	return apiPatch(`/admin/users/${encodeURIComponent(id)}`, body);
}

// =============================================================================
// Cache Refresh
// =============================================================================

export async function refreshCache(): Promise<ApiResponse<CacheRefreshResult>> {
	return apiPost("/admin/cache/refresh");
}
