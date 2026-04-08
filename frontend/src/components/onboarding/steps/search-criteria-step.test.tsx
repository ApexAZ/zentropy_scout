/**
 * Tests for the search criteria step component (onboarding Step 10).
 *
 * REQ-034 §9.1: SearchProfile display with editable tag lists for
 * fit and stretch buckets, auto-generation, and approval.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SearchCriteriaStep } from "./search-criteria-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const PROFILE_ID = "00000000-0000-4000-b000-000000000002";
const LOADING_TESTID = "loading-search-criteria";
const APPROVE_BUTTON_TESTID = "approve-button";
const BACK_BUTTON_TESTID = "back-button";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";
const MOCK_TIMESTAMP = "2026-04-07T12:00:00Z";

const MOCK_PROFILE = {
	id: PROFILE_ID,
	persona_id: DEFAULT_PERSONA_ID,
	fit_searches: [
		{
			label: "Senior Python Engineer",
			keywords: ["python", "fastapi"],
			titles: ["Senior Software Engineer"],
			remoteok_tags: ["python"],
			location: null,
		},
	],
	stretch_searches: [
		{
			label: "Management Track",
			keywords: ["engineering management"],
			titles: ["Engineering Manager"],
			remoteok_tags: ["management"],
			location: null,
		},
	],
	persona_fingerprint: "abc123",
	is_stale: false,
	generated_at: MOCK_TIMESTAMP,
	approved_at: null,
	created_at: MOCK_TIMESTAMP,
	updated_at: MOCK_TIMESTAMP,
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	class MockApiError extends Error {
		code: string;
		status: number;
		constructor(code: string, message: string, status: number) {
			super(message);
			this.name = "ApiError";
			this.code = code;
			this.status = status;
		}
	}
	return {
		mockGetSearchProfile: vi.fn(),
		mockGenerateSearchProfile: vi.fn(),
		mockUpdateSearchProfile: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockBack: vi.fn(),
	};
});

vi.mock("@/lib/api/search-profiles", () => ({
	getSearchProfile: mocks.mockGetSearchProfile,
	generateSearchProfile: mocks.mockGenerateSearchProfile,
	updateSearchProfile: mocks.mockUpdateSearchProfile,
}));

vi.mock("@/lib/api-client", () => ({
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		back: mocks.mockBack,
	}),
}));

/** Reusable 404 error for auto-generation tests. */
const NOT_FOUND_ERROR = new mocks.MockApiError("NOT_FOUND", "Not found", 404);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Render step and return a user event instance. */
function renderStep() {
	const user = userEvent.setup();
	render(<SearchCriteriaStep />);
	return user;
}

/** Wait for the profile to finish loading (happy path). */
async function waitForLoaded() {
	await screen.findByTestId(APPROVE_BUTTON_TESTID);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SearchCriteriaStep", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mocks.mockGetSearchProfile.mockResolvedValue({ data: MOCK_PROFILE });
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	describe("loading state", () => {
		it("shows loading spinner while fetching profile", () => {
			mocks.mockGetSearchProfile.mockReturnValue(new Promise(() => {}));
			renderStep();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("shows generating message when auto-triggering generation", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(NOT_FOUND_ERROR);
			mocks.mockGenerateSearchProfile.mockReturnValue(new Promise(() => {}));

			renderStep();

			await waitFor(() => {
				expect(
					screen.getByText(/generating your search criteria/i),
				).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Auto-generation
	// -----------------------------------------------------------------------

	describe("auto-generation", () => {
		it("triggers generation when profile does not exist (404)", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(NOT_FOUND_ERROR);
			mocks.mockGenerateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});

			renderStep();

			await waitFor(() => {
				expect(mocks.mockGenerateSearchProfile).toHaveBeenCalledWith(
					DEFAULT_PERSONA_ID,
				);
			});
		});

		it("displays profile after generation completes", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(NOT_FOUND_ERROR);
			mocks.mockGenerateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});

			renderStep();

			await waitFor(() => {
				expect(screen.getByText("Senior Python Engineer")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Profile display
	// -----------------------------------------------------------------------

	describe("profile display", () => {
		it("renders title and description", async () => {
			renderStep();
			await waitForLoaded();

			expect(
				screen.getByRole("heading", { name: /your job search criteria/i }),
			).toBeInTheDocument();
		});

		it("displays fit bucket label", async () => {
			renderStep();
			await waitForLoaded();

			expect(screen.getByText("Senior Python Engineer")).toBeInTheDocument();
		});

		it("displays fit bucket keywords as tags", async () => {
			renderStep();
			await waitForLoaded();

			expect(screen.getByText("python")).toBeInTheDocument();
			expect(screen.getByText("fastapi")).toBeInTheDocument();
		});

		it("displays fit bucket titles as tags", async () => {
			renderStep();
			await waitForLoaded();

			expect(screen.getByText("Senior Software Engineer")).toBeInTheDocument();
		});

		it("displays stretch bucket label", async () => {
			renderStep();
			await waitForLoaded();

			expect(screen.getByText("Management Track")).toBeInTheDocument();
		});

		it("displays stretch bucket keywords as tags", async () => {
			renderStep();
			await waitForLoaded();

			expect(screen.getByText("engineering management")).toBeInTheDocument();
		});

		it("displays section headings for fit and stretch", async () => {
			renderStep();
			await waitForLoaded();

			expect(
				screen.getByRole("heading", { name: /best fit/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", { name: /growth opportunities/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tag editing
	// -----------------------------------------------------------------------

	describe("tag editing", () => {
		it("adds a keyword tag on Enter", async () => {
			const user = renderStep();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const keywordInput =
				within(fitBucket).getByPlaceholderText(/add keyword/i);
			await user.type(keywordInput, "django{Enter}");

			expect(within(fitBucket).getByText("django")).toBeInTheDocument();
		});

		it("removes a keyword tag when X is clicked", async () => {
			const user = renderStep();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const removeButton = within(fitBucket).getByRole("button", {
				name: /remove python/i,
			});
			await user.click(removeButton);

			expect(within(fitBucket).queryByText("python")).not.toBeInTheDocument();
		});

		it("adds a title tag on Enter", async () => {
			const user = renderStep();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const titleInput = within(fitBucket).getByPlaceholderText(/add title/i);
			await user.type(titleInput, "Backend Engineer{Enter}");

			expect(
				within(fitBucket).getByText("Backend Engineer"),
			).toBeInTheDocument();
		});

		it("removes a title tag when X is clicked", async () => {
			const user = renderStep();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const removeButton = within(fitBucket).getByRole("button", {
				name: /remove Senior Software Engineer/i,
			});
			await user.click(removeButton);

			expect(
				within(fitBucket).queryByText("Senior Software Engineer"),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Approve action
	// -----------------------------------------------------------------------

	describe("approve action", () => {
		it("calls updateSearchProfile with buckets and approved_at, then next()", async () => {
			mocks.mockUpdateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderStep();
			await waitForLoaded();

			await user.click(screen.getByTestId(APPROVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockUpdateSearchProfile).toHaveBeenCalledWith(
					DEFAULT_PERSONA_ID,
					expect.objectContaining({
						fit_searches: MOCK_PROFILE.fit_searches,
						stretch_searches: MOCK_PROFILE.stretch_searches,
						approved_at: expect.any(String),
					}),
				);
			});

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("sends edited tags in approval payload", async () => {
			mocks.mockUpdateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderStep();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const keywordInput =
				within(fitBucket).getByPlaceholderText(/add keyword/i);
			await user.type(keywordInput, "django{Enter}");

			await user.click(screen.getByTestId(APPROVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockUpdateSearchProfile).toHaveBeenCalledWith(
					DEFAULT_PERSONA_ID,
					expect.objectContaining({
						fit_searches: [
							expect.objectContaining({
								keywords: ["python", "fastapi", "django"],
							}),
						],
					}),
				);
			});
		});

		it("shows error when approval fails", async () => {
			mocks.mockUpdateSearchProfile.mockRejectedValue(
				new Error("Network error"),
			);
			const user = renderStep();
			await waitForLoaded();

			await user.click(screen.getByTestId(APPROVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});

			expect(mocks.mockNext).not.toHaveBeenCalled();
		});

		it("disables approve button while saving", async () => {
			mocks.mockUpdateSearchProfile.mockReturnValue(new Promise(() => {}));
			const user = renderStep();
			await waitForLoaded();

			await user.click(screen.getByTestId(APPROVE_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(APPROVE_BUTTON_TESTID);
				expect(btn).toBeDisabled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls back() when Back is clicked", async () => {
			const user = renderStep();
			await waitForLoaded();

			await user.click(screen.getByTestId(BACK_BUTTON_TESTID));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	describe("error handling", () => {
		it("shows error when initial fetch fails (non-404)", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(new Error("Network error"));

			renderStep();

			await waitFor(() => {
				expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
			});
		});

		it("shows error when generation fails", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(NOT_FOUND_ERROR);
			mocks.mockGenerateSearchProfile.mockRejectedValue(
				new Error("Generation failed"),
			);

			renderStep();

			await waitFor(() => {
				expect(screen.getByText(/failed to generate/i)).toBeInTheDocument();
			});
		});
	});
});
