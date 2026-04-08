/**
 * Tests for the JobSearchSection component (Phase 5 §4).
 *
 * REQ-034 §9.2: Job Search settings tab with editable search criteria,
 * poll schedule display, job source toggles, refresh button, and staleness banner.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const PROFILE_ID = "00000000-0000-4000-b000-000000000002";
const SECTION_TESTID = "job-search-section";
const LOADING_TESTID = "loading-spinner";
const STALENESS_TESTID = "staleness-banner";
const SAVE_BUTTON_TESTID = "save-criteria-button";
const REFRESH_BUTTON_TESTID = "refresh-criteria-button";
const MOCK_TIMESTAMP = "2026-04-07T12:00:00Z";

const MOCK_PROFILE = {
	id: PROFILE_ID,
	persona_id: PERSONA_ID,
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
	approved_at: MOCK_TIMESTAMP,
	created_at: MOCK_TIMESTAMP,
	updated_at: MOCK_TIMESTAMP,
};

const MOCK_STALE_PROFILE = {
	...MOCK_PROFILE,
	is_stale: true,
};

const MOCK_PERSONA = {
	id: PERSONA_ID,
	polling_frequency: "Daily",
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
		mockApiGet: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
	};
});

vi.mock("@/lib/api/search-profiles", () => ({
	getSearchProfile: mocks.mockGetSearchProfile,
	generateSearchProfile: mocks.mockGenerateSearchProfile,
	updateSearchProfile: mocks.mockUpdateSearchProfile,
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("./job-sources-section", () => ({
	JobSourcesSection: ({ personaId }: { personaId: string }) => (
		<div data-testid="mock-job-sources-section" data-persona-id={personaId} />
	),
}));

import { JobSearchSection } from "./job-search-section";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderSection() {
	const Wrapper = createWrapper();
	const user = userEvent.setup();
	render(
		<Wrapper>
			<JobSearchSection personaId={PERSONA_ID} />
		</Wrapper>,
	);
	return user;
}

function setupMockApi(
	profileResponse: unknown = { data: MOCK_PROFILE },
	personaResponse: unknown = { data: MOCK_PERSONA },
) {
	mocks.mockGetSearchProfile.mockResolvedValue(profileResponse);
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path.includes("/personas/")) {
			return Promise.resolve(personaResponse);
		}
		return Promise.reject(new Error(`Unexpected GET: ${path}`));
	});
}

async function waitForLoaded() {
	await screen.findByTestId(SECTION_TESTID);
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	setupMockApi();
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobSearchSection", () => {
	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	describe("loading state", () => {
		it("shows loading spinner while fetching profile", () => {
			mocks.mockGetSearchProfile.mockReturnValue(new Promise(() => {}));
			renderSection();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Error state
	// -----------------------------------------------------------------------

	describe("error state", () => {
		it("shows error when profile fetch fails", async () => {
			mocks.mockGetSearchProfile.mockRejectedValue(new Error("Network error"));
			renderSection();

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Staleness banner
	// -----------------------------------------------------------------------

	describe("staleness banner", () => {
		it("shows staleness banner when is_stale is true", async () => {
			setupMockApi({ data: MOCK_STALE_PROFILE });
			renderSection();
			await waitForLoaded();

			expect(screen.getByTestId(STALENESS_TESTID)).toBeInTheDocument();
			expect(screen.getByText(/persona has changed/i)).toBeInTheDocument();
		});

		it("hides staleness banner when is_stale is false", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.queryByTestId(STALENESS_TESTID)).not.toBeInTheDocument();
		});

		it("triggers regeneration when staleness banner refresh is clicked", async () => {
			setupMockApi({ data: MOCK_STALE_PROFILE });
			mocks.mockGenerateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderSection();
			await waitForLoaded();

			const banner = screen.getByTestId(STALENESS_TESTID);
			await user.click(
				within(banner).getByRole("button", { name: /refresh/i }),
			);

			await waitFor(() => {
				expect(mocks.mockGenerateSearchProfile).toHaveBeenCalledWith(
					PERSONA_ID,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Search criteria display
	// -----------------------------------------------------------------------

	describe("search criteria display", () => {
		it("displays fit bucket labels", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.getByText("Senior Python Engineer")).toBeInTheDocument();
		});

		it("displays fit bucket keywords as tags", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.getByText("python")).toBeInTheDocument();
			expect(screen.getByText("fastapi")).toBeInTheDocument();
		});

		it("displays stretch bucket labels", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.getByText("Management Track")).toBeInTheDocument();
		});

		it("displays section headings for fit and stretch", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.getByText("Best Fit")).toBeInTheDocument();
			expect(screen.getByText("Growth Opportunities")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tag editing
	// -----------------------------------------------------------------------

	describe("tag editing", () => {
		it("adds a keyword tag on Enter", async () => {
			const user = renderSection();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const keywordInput =
				within(fitBucket).getByPlaceholderText(/add keyword/i);
			await user.type(keywordInput, "django{Enter}");

			expect(within(fitBucket).getByText("django")).toBeInTheDocument();
		});

		it("removes a keyword tag when X is clicked", async () => {
			const user = renderSection();
			await waitForLoaded();

			const fitBucket = screen.getByTestId("fit-bucket-0");
			const removeButton = within(fitBucket).getByRole("button", {
				name: /remove python/i,
			});
			await user.click(removeButton);

			expect(within(fitBucket).queryByText("python")).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Save changes
	// -----------------------------------------------------------------------

	describe("save changes", () => {
		it("calls updateSearchProfile with current buckets on save", async () => {
			mocks.mockUpdateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderSection();
			await waitForLoaded();

			// Edit first so we have a meaningful save
			const fitBucket = screen.getByTestId("fit-bucket-0");
			const keywordInput =
				within(fitBucket).getByPlaceholderText(/add keyword/i);
			await user.type(keywordInput, "django{Enter}");

			await user.click(screen.getByTestId(SAVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockUpdateSearchProfile).toHaveBeenCalledWith(
					PERSONA_ID,
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

		it("shows success toast after save", async () => {
			mocks.mockUpdateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderSection();
			await waitForLoaded();

			await user.click(screen.getByTestId(SAVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("shows error toast on save failure", async () => {
			mocks.mockUpdateSearchProfile.mockRejectedValue(new Error("Save failed"));
			const user = renderSection();
			await waitForLoaded();

			await user.click(screen.getByTestId(SAVE_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Refresh criteria
	// -----------------------------------------------------------------------

	describe("refresh criteria", () => {
		it("calls generateSearchProfile on refresh click", async () => {
			mocks.mockGenerateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderSection();
			await waitForLoaded();

			await user.click(screen.getByTestId(REFRESH_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockGenerateSearchProfile).toHaveBeenCalledWith(
					PERSONA_ID,
				);
			});
		});

		it("shows success toast after refresh", async () => {
			mocks.mockGenerateSearchProfile.mockResolvedValue({
				data: MOCK_PROFILE,
			});
			const user = renderSection();
			await waitForLoaded();

			await user.click(screen.getByTestId(REFRESH_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("shows error toast on refresh failure", async () => {
			mocks.mockGenerateSearchProfile.mockRejectedValue(
				new Error("Gen failed"),
			);
			const user = renderSection();
			await waitForLoaded();

			await user.click(screen.getByTestId(REFRESH_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Poll schedule
	// -----------------------------------------------------------------------

	describe("poll schedule", () => {
		it("displays polling frequency from persona", async () => {
			renderSection();
			await waitForLoaded();

			expect(screen.getByText("Daily")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Job sources
	// -----------------------------------------------------------------------

	describe("job sources", () => {
		it("renders embedded JobSourcesSection", async () => {
			renderSection();
			await waitForLoaded();

			const mockSection = screen.getByTestId("mock-job-sources-section");
			expect(mockSection).toBeInTheDocument();
			expect(mockSection).toHaveAttribute("data-persona-id", PERSONA_ID);
		});
	});
});
