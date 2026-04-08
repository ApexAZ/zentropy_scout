/**
 * Tests for search-profiles API client functions.
 *
 * REQ-034 @4.5: SearchProfile API client functions hit correct URLs
 * with correct methods and params.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	generateSearchProfile,
	getSearchProfile,
	updateSearchProfile,
} from "./search-profiles";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiGet = vi.fn();
	const mockApiPost = vi.fn();
	const mockApiPatch = vi.fn();
	return { mockApiGet, mockApiPost, mockApiPatch };
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
}));

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const TEST_PERSONA_ID = "persona-uuid-123";
const TEST_TIMESTAMP = "2026-04-07T12:00:00Z";
const TEST_APPROVAL_TIMESTAMP = "2026-04-07T13:00:00Z";

const MOCK_PROFILE = {
	id: "profile-uuid-456",
	persona_id: TEST_PERSONA_ID,
	fit_searches: [
		{
			label: "Senior Engineer",
			keywords: ["backend", "python"],
			titles: ["Senior Software Engineer"],
			remoteok_tags: ["python", "backend"],
			location: null,
		},
	],
	stretch_searches: [
		{
			label: "Engineering Manager",
			keywords: ["engineering manager"],
			titles: ["Engineering Manager"],
			remoteok_tags: ["management"],
			location: null,
		},
	],
	persona_fingerprint: "abc123",
	is_stale: false,
	generated_at: TEST_TIMESTAMP,
	approved_at: null,
	created_at: TEST_TIMESTAMP,
	updated_at: TEST_TIMESTAMP,
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SearchProfile API Client", () => {
	// -----------------------------------------------------------------
	// GET /search-profiles/{personaId}
	// -----------------------------------------------------------------

	describe("getSearchProfile", () => {
		it("calls GET /search-profiles/{personaId}", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: MOCK_PROFILE });
			await getSearchProfile(TEST_PERSONA_ID);
			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/search-profiles/${encodeURIComponent(TEST_PERSONA_ID)}`,
			);
		});

		it("returns the API response", async () => {
			const response = { data: MOCK_PROFILE };
			mocks.mockApiGet.mockResolvedValue(response);
			const result = await getSearchProfile(TEST_PERSONA_ID);
			expect(result).toEqual(response);
		});
	});

	// -----------------------------------------------------------------
	// POST /search-profiles/{personaId}/generate
	// -----------------------------------------------------------------

	describe("generateSearchProfile", () => {
		it("calls POST /search-profiles/{personaId}/generate", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: MOCK_PROFILE });
			await generateSearchProfile(TEST_PERSONA_ID);
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/search-profiles/${encodeURIComponent(TEST_PERSONA_ID)}/generate`,
			);
		});

		it("returns the generated profile", async () => {
			const response = { data: MOCK_PROFILE };
			mocks.mockApiPost.mockResolvedValue(response);
			const result = await generateSearchProfile(TEST_PERSONA_ID);
			expect(result).toEqual(response);
		});
	});

	// -----------------------------------------------------------------
	// PATCH /search-profiles/{personaId}
	// -----------------------------------------------------------------

	describe("updateSearchProfile", () => {
		it("calls PATCH /search-profiles/{personaId} with update data", async () => {
			const update = {
				fit_searches: MOCK_PROFILE.fit_searches,
				approved_at: TEST_APPROVAL_TIMESTAMP,
			};
			mocks.mockApiPatch.mockResolvedValue({ data: MOCK_PROFILE });
			await updateSearchProfile(TEST_PERSONA_ID, update);
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/search-profiles/${encodeURIComponent(TEST_PERSONA_ID)}`,
				update,
			);
		});

		it("returns the updated profile", async () => {
			const update = { approved_at: TEST_APPROVAL_TIMESTAMP };
			const response = {
				data: { ...MOCK_PROFILE, approved_at: TEST_APPROVAL_TIMESTAMP },
			};
			mocks.mockApiPatch.mockResolvedValue(response);
			const result = await updateSearchProfile(TEST_PERSONA_ID, update);
			expect(result).toEqual(response);
		});
	});
});
