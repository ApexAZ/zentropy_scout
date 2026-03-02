/**
 * Tests for admin API client functions.
 *
 * REQ-022 §11: Admin API client functions hit correct URLs with correct methods.
 * Tests verify URL construction and HTTP method for each endpoint group.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	createModel,
	createPack,
	createPricing,
	createRouting,
	deleteConfig,
	deleteModel,
	deletePack,
	deletePricing,
	deleteRouting,
	fetchConfig,
	fetchModels,
	fetchPacks,
	fetchPricing,
	fetchRouting,
	fetchUsers,
	refreshCache,
	toggleAdmin,
	updateModel,
	updatePack,
	updatePricing,
	updateRouting,
	upsertConfig,
} from "./admin";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiGet = vi.fn();
	const mockApiPost = vi.fn();
	const mockApiPatch = vi.fn();
	const mockApiPut = vi.fn();
	const mockApiDelete = vi.fn();
	return { mockApiGet, mockApiPost, mockApiPatch, mockApiPut, mockApiDelete };
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiPut: mocks.mockApiPut,
	apiDelete: mocks.mockApiDelete,
}));

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const TEST_PROVIDER = "claude";
const TEST_MODEL = "claude-3-5-haiku-20241022";
const TEST_DISPLAY_NAME = "Claude 3.5 Haiku";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Admin API Client", () => {
	// -----------------------------------------------------------------
	// Model Registry
	// -----------------------------------------------------------------

	describe("Model Registry", () => {
		it("fetchModels calls GET /admin/models with query params", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchModels({ provider: TEST_PROVIDER, is_active: true });
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/models", {
				provider: TEST_PROVIDER,
				is_active: true,
			});
		});

		it("createModel calls POST /admin/models with body", async () => {
			const body = {
				provider: TEST_PROVIDER,
				model: TEST_MODEL,
				display_name: TEST_DISPLAY_NAME,
				model_type: "llm",
			};
			mocks.mockApiPost.mockResolvedValue({ data: { id: "1", ...body } });
			await createModel(body);
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/admin/models", body);
		});

		it("updateModel calls PATCH /admin/models/:id with body", async () => {
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			await updateModel("abc-123", { display_name: "New Name" });
			expect(mocks.mockApiPatch).toHaveBeenCalledWith("/admin/models/abc-123", {
				display_name: "New Name",
			});
		});

		it("deleteModel calls DELETE /admin/models/:id", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);
			await deleteModel("abc-123");
			expect(mocks.mockApiDelete).toHaveBeenCalledWith("/admin/models/abc-123");
		});
	});

	// -----------------------------------------------------------------
	// Pricing Config
	// -----------------------------------------------------------------

	describe("Pricing Config", () => {
		it("fetchPricing calls GET /admin/pricing with query params", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchPricing({ provider: "openai" });
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/pricing", {
				provider: "openai",
			});
		});

		it("createPricing calls POST /admin/pricing with body", async () => {
			const body = {
				provider: TEST_PROVIDER,
				model: TEST_MODEL,
				input_cost_per_1k: "0.001",
				output_cost_per_1k: "0.005",
				margin_multiplier: "2.0",
				effective_date: "2026-03-01",
			};
			mocks.mockApiPost.mockResolvedValue({ data: { id: "1", ...body } });
			await createPricing(body);
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/admin/pricing", body);
		});

		it("updatePricing calls PATCH /admin/pricing/:id", async () => {
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			await updatePricing("p-123", { margin_multiplier: "1.5" });
			expect(mocks.mockApiPatch).toHaveBeenCalledWith("/admin/pricing/p-123", {
				margin_multiplier: "1.5",
			});
		});

		it("deletePricing calls DELETE /admin/pricing/:id", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);
			await deletePricing("p-123");
			expect(mocks.mockApiDelete).toHaveBeenCalledWith("/admin/pricing/p-123");
		});
	});

	// -----------------------------------------------------------------
	// Task Routing
	// -----------------------------------------------------------------

	describe("Task Routing", () => {
		it("fetchRouting calls GET /admin/routing with query params", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchRouting({ provider: "gemini" });
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/routing", {
				provider: "gemini",
			});
		});

		it("createRouting calls POST /admin/routing with body", async () => {
			const body = {
				provider: TEST_PROVIDER,
				task_type: "extraction",
				model: TEST_MODEL,
			};
			mocks.mockApiPost.mockResolvedValue({ data: { id: "1", ...body } });
			await createRouting(body);
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/admin/routing", body);
		});

		it("updateRouting calls PATCH /admin/routing/:id", async () => {
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			await updateRouting("r-123", { model: "new-model" });
			expect(mocks.mockApiPatch).toHaveBeenCalledWith("/admin/routing/r-123", {
				model: "new-model",
			});
		});

		it("deleteRouting calls DELETE /admin/routing/:id", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);
			await deleteRouting("r-123");
			expect(mocks.mockApiDelete).toHaveBeenCalledWith("/admin/routing/r-123");
		});
	});

	// -----------------------------------------------------------------
	// Credit Packs
	// -----------------------------------------------------------------

	describe("Credit Packs", () => {
		it("fetchPacks calls GET /admin/credit-packs", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchPacks();
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/credit-packs");
		});

		it("createPack calls POST /admin/credit-packs with body", async () => {
			const body = { name: "Starter", price_cents: 500, credit_amount: 100000 };
			mocks.mockApiPost.mockResolvedValue({ data: { id: "1", ...body } });
			await createPack(body);
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/admin/credit-packs",
				body,
			);
		});

		it("updatePack calls PATCH /admin/credit-packs/:id", async () => {
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			await updatePack("pk-123", { price_cents: 999 });
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				"/admin/credit-packs/pk-123",
				{ price_cents: 999 },
			);
		});

		it("deletePack calls DELETE /admin/credit-packs/:id", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);
			await deletePack("pk-123");
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				"/admin/credit-packs/pk-123",
			);
		});
	});

	// -----------------------------------------------------------------
	// System Config
	// -----------------------------------------------------------------

	describe("System Config", () => {
		it("fetchConfig calls GET /admin/config", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [] });
			await fetchConfig();
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/config");
		});

		it("upsertConfig calls PUT /admin/config/:key with body", async () => {
			mocks.mockApiPut.mockResolvedValue({ data: {} });
			await upsertConfig("signup_grant_credits", {
				value: "1000",
				description: "Credits for new signups",
			});
			expect(mocks.mockApiPut).toHaveBeenCalledWith(
				"/admin/config/signup_grant_credits",
				{
					value: "1000",
					description: "Credits for new signups",
				},
			);
		});

		it("deleteConfig calls DELETE /admin/config/:key", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);
			await deleteConfig("signup_grant_credits");
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				"/admin/config/signup_grant_credits",
			);
		});
	});

	// -----------------------------------------------------------------
	// Admin Users
	// -----------------------------------------------------------------

	describe("Admin Users", () => {
		it("fetchUsers calls GET /admin/users with pagination params", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: [], meta: {} });
			await fetchUsers({ page: 2, per_page: 10, is_admin: true });
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/admin/users", {
				page: 2,
				per_page: 10,
				is_admin: true,
			});
		});

		it("toggleAdmin calls PATCH /admin/users/:id with is_admin", async () => {
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			await toggleAdmin("u-123", true);
			expect(mocks.mockApiPatch).toHaveBeenCalledWith("/admin/users/u-123", {
				is_admin: true,
			});
		});
	});

	// -----------------------------------------------------------------
	// Cache Refresh
	// -----------------------------------------------------------------

	describe("Cache Refresh", () => {
		it("refreshCache calls POST /admin/cache/refresh", async () => {
			mocks.mockApiPost.mockResolvedValue({
				data: { message: "OK", caching_enabled: false },
			});
			await refreshCache();
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/admin/cache/refresh");
		});
	});
});
