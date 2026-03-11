/**
 * Tests for credits API client functions.
 *
 * REQ-029 §8.1–§8.3: Credits API client functions hit correct URLs
 * with correct methods and params.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	createCheckoutSession,
	fetchCreditPacks,
	fetchPurchases,
} from "./credits";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiGet = vi.fn();
	const mockApiPost = vi.fn();
	return { mockApiGet, mockApiPost };
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
}));

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const TEST_PACK_ID = "pack-uuid-123";
const TEST_SESSION_ID = "cs_test_abc";
const TEST_CHECKOUT_URL = `https://checkout.stripe.com/pay/${TEST_SESSION_ID}`;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Credits API Client", () => {
	// -----------------------------------------------------------------
	// GET /credits/packs
	// -----------------------------------------------------------------

	describe("fetchCreditPacks", () => {
		it("calls GET /credits/packs", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchCreditPacks();
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/credits/packs");
		});

		it("returns the API response", async () => {
			const mockPacks = [
				{
					id: "pack-1",
					name: "Starter",
					price_cents: 500,
					price_display: "$5.00",
					grant_cents: 500,
					amount_display: "$5.00",
					description: "Get started",
					highlight_label: null,
				},
			];
			mocks.mockApiGet.mockResolvedValue({ data: mockPacks });
			const result = await fetchCreditPacks();
			expect(result).toEqual({ data: mockPacks });
		});
	});

	// -----------------------------------------------------------------
	// POST /credits/checkout
	// -----------------------------------------------------------------

	describe("createCheckoutSession", () => {
		it("calls POST /credits/checkout with pack_id", async () => {
			mocks.mockApiPost.mockResolvedValue({
				data: {
					checkout_url: TEST_CHECKOUT_URL,
					session_id: TEST_SESSION_ID,
				},
			});
			await createCheckoutSession(TEST_PACK_ID);
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/credits/checkout", {
				pack_id: TEST_PACK_ID,
			});
		});

		it("returns checkout URL and session ID", async () => {
			const mockResponse = {
				data: {
					checkout_url: TEST_CHECKOUT_URL,
					session_id: TEST_SESSION_ID,
				},
			};
			mocks.mockApiPost.mockResolvedValue(mockResponse);
			const result = await createCheckoutSession(TEST_PACK_ID);
			expect(result).toEqual(mockResponse);
		});
	});

	// -----------------------------------------------------------------
	// GET /credits/purchases
	// -----------------------------------------------------------------

	describe("fetchPurchases", () => {
		it("calls GET /credits/purchases with pagination params", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [], meta: {} });
			await fetchPurchases(2, 10);
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/credits/purchases", {
				page: 2,
				per_page: 10,
			});
		});

		it("uses default pagination when no params provided", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [], meta: {} });
			await fetchPurchases();
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/credits/purchases", {
				page: 1,
				per_page: 20,
			});
		});

		it("returns paginated purchase data", async () => {
			const mockResponse = {
				data: [
					{
						id: "txn-1",
						amount_usd: "10.000000",
						amount_display: "$10.00",
						transaction_type: "purchase",
						description: "Starter pack",
						created_at: "2026-03-10T15:30:00Z",
					},
				],
				meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
			};
			mocks.mockApiGet.mockResolvedValue(mockResponse);
			const result = await fetchPurchases();
			expect(result).toEqual(mockResponse);
		});
	});
});
