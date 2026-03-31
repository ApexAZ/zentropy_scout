/**
 * Credits API client functions.
 *
 * REQ-029 §8.1–§8.3: Typed functions for credit pack listing,
 * checkout session creation, and purchase history retrieval.
 *
 * @module lib/api/credits
 * @coordinates-with api-client (shared HTTP wrappers),
 *   types/usage (PackItem, CheckoutResponse, PurchaseItem shapes),
 *   components/usage/funding-packs (pack listing + checkout),
 *   components/usage/usage-page (purchase history)
 */

import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { CheckoutResponse, PackItem, PurchaseItem } from "@/types/usage";
import { apiGet, apiPost } from "@/lib/api-client";

// =============================================================================
// GET /credits/packs — public pack listing
// =============================================================================

/** Fetch active funding packs with Stripe pricing configured. */
export async function fetchCreditPacks(): Promise<ApiResponse<PackItem[]>> {
	return apiGet("/credits/packs");
}

// =============================================================================
// POST /credits/checkout — create checkout session
// =============================================================================

/** Create a Stripe Checkout session for the given pack. */
export async function createCheckoutSession(
	packId: string,
): Promise<ApiResponse<CheckoutResponse>> {
	return apiPost("/credits/checkout", { pack_id: packId });
}

// =============================================================================
// GET /credits/purchases — purchase history
// =============================================================================

/** Fetch paginated purchase/grant/refund history for the current user. */
export async function fetchPurchases(
	page: number = 1,
	perPage: number = 20,
): Promise<ApiListResponse<PurchaseItem>> {
	return apiGet("/credits/purchases", { page, per_page: perPage });
}
