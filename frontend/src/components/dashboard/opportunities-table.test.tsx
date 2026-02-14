/**
 * Tests for the OpportunitiesTable component (§7.2).
 *
 * REQ-012 §8.2: Opportunities tab — job table with favorite,
 * title, location, salary, scores, ghost, and date columns.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TABLE_TESTID = "opportunities-table";
const LOADING_TESTID = "loading-spinner";
const EMPTY_MESSAGE = "No opportunities found.";
const FAVORITE_ERROR_MESSAGE = "Failed to update favorite.";
const FAVORITE_TOGGLE_JOB1 = "favorite-toggle-job-1";
const GHOST_WARNING_JOB1 = "ghost-warning-job-1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns a YYYY-MM-DD date string for N days before today. */
function daysAgoDate(days: number): string {
	const d = new Date();
	d.setDate(d.getDate() - days);
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, "0");
	const dd = String(d.getDate()).padStart(2, "0");
	return `${y}-${m}-${dd}`;
}

function makeJob(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: "p-1",
		external_id: null,
		source_id: "src-1",
		also_found_on: { sources: [] },
		job_title: `Software Engineer ${id}`,
		company_name: `Company ${id}`,
		company_url: null,
		source_url: null,
		apply_url: null,
		location: "Austin, TX",
		work_model: "Remote",
		seniority_level: "Mid",
		salary_min: 120000,
		salary_max: 150000,
		salary_currency: "USD",
		description: "Job description",
		culture_text: null,
		requirements: null,
		years_experience_min: null,
		years_experience_max: null,
		posted_date: null,
		application_deadline: null,
		first_seen_date: daysAgoDate(3),
		status: "Discovered",
		is_favorite: false,
		fit_score: 85,
		stretch_score: 65,
		score_details: null,
		failed_non_negotiables: null,
		ghost_score: 10,
		ghost_signals: null,
		description_hash: "abc123",
		repost_count: 0,
		previous_posting_ids: null,
		last_verified_at: null,
		dismissed_at: null,
		expired_at: null,
		created_at: "2026-02-10T12:00:00Z",
		updated_at: "2026-02-10T12:00:00Z",
		...overrides,
	};
}

const MOCK_LIST_META = { total: 2, page: 1, per_page: 20, total_pages: 1 };

const MOCK_JOBS_RESPONSE = {
	data: [makeJob("job-1"), makeJob("job-2")],
	meta: MOCK_LIST_META,
};

const MOCK_EMPTY_RESPONSE = {
	data: [],
	meta: { ...MOCK_LIST_META, total: 0 },
};

function makeSingleJobResponse(overrides?: Record<string, unknown>) {
	return {
		data: [makeJob("job-1", overrides)],
		meta: { ...MOCK_LIST_META, total: 1 },
	};
}

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
		mockApiGet: vi.fn(),
		mockApiPatch: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockPush: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { OpportunitiesTable } from "./opportunities-table";

// ---------------------------------------------------------------------------
// Setup / Teardown
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

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockPush.mockReset();
	mocks.mockShowToast.success.mockReset();
	mocks.mockShowToast.error.mockReset();
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("OpportunitiesTable", () => {
	describe("loading state", () => {
		it("shows loading spinner initially", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("rendering", () => {
		it("renders table container after data loads", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});
		});

		it("renders job title", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("Software Engineer job-1")).toBeInTheDocument();
			});
		});

		it("renders company name", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("Company job-1")).toBeInTheDocument();
			});
		});

		it("renders location with work model", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(
					screen.getByText("Austin, TX \u00b7 Remote"),
				).toBeInTheDocument();
			});
		});

		it("renders salary range", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("$120k\u2013$150k USD")).toBeInTheDocument();
			});
		});

		it("renders 'Not disclosed' when salary is null", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({
					salary_min: null,
					salary_max: null,
					salary_currency: null,
				}),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("Not disclosed")).toBeInTheDocument();
			});
		});

		it("renders fit score badge", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(
					screen.getByLabelText("Fit score: 85, Medium"),
				).toBeInTheDocument();
			});
		});

		it("renders stretch score badge", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(
					screen.getByLabelText("Stretch score: 65, Moderate Growth"),
				).toBeInTheDocument();
			});
		});

		it("renders 'Not scored' for null fit score", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ fit_score: null }),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(
					screen.getByLabelText("Fit score: Not scored"),
				).toBeInTheDocument();
			});
		});

		it("renders ghost warning icon for ghost_score >= 50", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 75 }),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(GHOST_WARNING_JOB1)).toBeInTheDocument();
			});
		});

		it("does not render ghost icon for ghost_score < 50", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});

			expect(screen.queryByTestId(GHOST_WARNING_JOB1)).not.toBeInTheDocument();
		});

		it("renders relative date from first_seen_date", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ first_seen_date: daysAgoDate(0) }),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("Today")).toBeInTheDocument();
			});
		});
	});

	describe("empty state", () => {
		it("shows empty message when no jobs", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
			});
		});
	});

	describe("error state", () => {
		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("row click", () => {
		it("navigates to /jobs/[id] on row click", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByText("Software Engineer job-1")).toBeInTheDocument();
			});

			const row = screen.getByText("Software Engineer job-1").closest("tr");
			await user.click(row!);

			expect(mocks.mockPush).toHaveBeenCalledWith("/jobs/job-1");
		});
	});

	describe("favorite toggle", () => {
		it("calls apiPatch when favorite button clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({
				data: makeJob("job-1", { is_favorite: true }),
			});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_JOB1)).toBeInTheDocument();
			});

			await user.click(screen.getByTestId(FAVORITE_TOGGLE_JOB1));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith("/job-postings/job-1", {
				is_favorite: true,
			});
		});

		it("does not navigate when favorite button clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({
				data: makeJob("job-1", { is_favorite: true }),
			});

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_JOB1)).toBeInTheDocument();
			});

			await user.click(screen.getByTestId(FAVORITE_TOGGLE_JOB1));

			expect(mocks.mockPush).not.toHaveBeenCalled();
		});

		it("shows error toast on favorite toggle failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("INTERNAL_ERROR", "Server error", 500),
			);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_JOB1)).toBeInTheDocument();
			});

			await user.click(screen.getByTestId(FAVORITE_TOGGLE_JOB1));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					FAVORITE_ERROR_MESSAGE,
				);
			});
		});
	});

	describe("API call", () => {
		it("calls apiGet with status=Discovered", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<OpportunitiesTable />
				</Wrapper>,
			);

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith("/job-postings", {
					status: "Discovered",
				});
			});
		});
	});
});
