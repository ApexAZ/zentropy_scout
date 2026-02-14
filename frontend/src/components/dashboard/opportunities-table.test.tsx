/**
 * Tests for the OpportunitiesTable component (§7.2, §7.3, §7.4, §7.5, §7.6).
 *
 * REQ-012 §8.2: Opportunities tab — job table with favorite,
 * title, location, salary, scores, ghost, and date columns.
 * Toolbar: search, status filter, min-fit filter, sort dropdown.
 * Multi-select mode with bulk dismiss/favorite.
 * REQ-012 §8.5: "Show filtered jobs" toggle — dimmed rows,
 * Filtered badge, expandable failure reasons.
 * REQ-012 §8.6: Ghost detection with severity-based icon and tooltip.
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
const JOB1_TITLE = "Software Engineer job-1";
const SEARCH_PLACEHOLDER = "Search jobs...";
const FILTERED_JOB_TITLE = "Software Engineer job-filtered";
const SHOW_FILTERED_LABEL = "Show filtered jobs";
const EXPAND_REASONS_FILTERED = "expand-reasons-job-filtered";
const STATUS_FILTER_LABEL = "Status filter";
const SELECT_ROW_LABEL = "Select row";
const SELECT_ALL_LABEL = "Select all";
const BULK_ACTION_ERROR = "Bulk action failed.";
const SELECT_MODE_BUTTON = "select-mode-button";
const SELECTION_ACTION_BAR = "selection-action-bar";
const SELECTED_COUNT = "selected-count";
const BULK_DISMISS_BUTTON = "bulk-dismiss-button";
const BULK_FAVORITE_BUTTON = "bulk-favorite-button";
const CANCEL_SELECT_BUTTON = "cancel-select-button";

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

const MOCK_BULK_SUCCESS_SINGLE = {
	data: { succeeded: ["job-1"], failed: [] },
};

const MOCK_BULK_SUCCESS_MULTI = {
	data: { succeeded: ["job-1", "job-2"], failed: [] },
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
		mockApiGet: vi.fn(),
		mockApiPatch: vi.fn(),
		mockApiPost: vi.fn(),
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
	apiPost: mocks.mockApiPost,
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

function renderTable() {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<OpportunitiesTable />
		</Wrapper>,
	);
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockApiPost.mockReset();
	mocks.mockPush.mockReset();
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
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

			renderTable();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("rendering", () => {
		it("renders table container after data loads", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});
		});

		it("renders job title", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});
		});

		it("renders company name", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Company job-1")).toBeInTheDocument();
			});
		});

		it("renders location with work model", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByText("Austin, TX \u00b7 Remote"),
				).toBeInTheDocument();
			});
		});

		it("renders salary range", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			renderTable();

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

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Not disclosed")).toBeInTheDocument();
			});
		});

		it("renders fit score badge", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByLabelText("Fit score: 85, Medium"),
				).toBeInTheDocument();
			});
		});

		it("renders stretch score badge", async () => {
			mocks.mockApiGet.mockResolvedValue(makeSingleJobResponse());

			renderTable();

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

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByLabelText("Fit score: Not scored"),
				).toBeInTheDocument();
			});
		});

		it("does not render ghost icon for fresh tier (score 25)", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 25 }),
			);

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});

			expect(screen.queryByTestId(GHOST_WARNING_JOB1)).not.toBeInTheDocument();
		});

		it("renders relative date from first_seen_date", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ first_seen_date: daysAgoDate(0) }),
			);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Today")).toBeInTheDocument();
			});
		});
	});

	describe("empty state", () => {
		it("shows empty message when no jobs", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable();

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

			renderTable();

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("row click", () => {
		it("navigates to /jobs/[id] on row click", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			const row = screen.getByText(JOB1_TITLE).closest("tr");
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

			renderTable();

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

			renderTable();

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

			renderTable();

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

	describe("toolbar", () => {
		it("renders search input with placeholder", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText(SEARCH_PLACEHOLDER),
				).toBeInTheDocument();
			});
		});

		it("renders status filter dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("renders min-fit filter dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: "Minimum fit score" }),
				).toBeInTheDocument();
			});
		});

		it("renders sort dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: "Sort by" }),
				).toBeInTheDocument();
			});
		});

		it("renders Add Job button in toolbar", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId("add-job-button")).toBeInTheDocument();
			});
		});

		it("opens AddJobModal when Add Job button is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId("add-job-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("add-job-button"));

			await waitFor(() => {
				expect(
					screen.getByText("Paste a job posting to extract and save it."),
				).toBeInTheDocument();
			});
		});

		it("filters rows client-side by search text", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.type(screen.getByPlaceholderText(SEARCH_PLACEHOLDER), "job-2");

			await waitFor(() => {
				expect(screen.queryByText(JOB1_TITLE)).not.toBeInTheDocument();
			});
			expect(screen.getByText("Software Engineer job-2")).toBeInTheDocument();
		});
	});

	describe("API call", () => {
		it("calls apiGet with status=Discovered", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith("/job-postings", {
					status: "Discovered",
				});
			});
		});
	});

	describe("ghost detection", () => {
		it("shows amber icon with moderate risk label for score 26", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 26 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toBeInTheDocument();
				expect(icon).toHaveClass("text-amber-500");
				expect(icon).toHaveAttribute("aria-label", "Moderate ghost risk");
			});
		});

		it("shows orange icon with elevated risk label for score 51", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 51 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toBeInTheDocument();
				expect(icon).toHaveClass("text-orange-500");
				expect(icon).toHaveAttribute("aria-label", "Elevated ghost risk");
			});
		});

		it("shows red icon with high risk label for score 76", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 76 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toBeInTheDocument();
				expect(icon).toHaveClass("text-red-500");
				expect(icon).toHaveAttribute("aria-label", "High ghost risk");
			});
		});

		it("shows amber for score 50 (upper moderate boundary)", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 50 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toHaveClass("text-amber-500");
			});
		});

		it("shows orange for score 75 (upper elevated boundary)", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 75 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toHaveClass("text-orange-500");
			});
		});

		it("shows red for score 100 (upper high risk boundary)", async () => {
			mocks.mockApiGet.mockResolvedValue(
				makeSingleJobResponse({ ghost_score: 100 }),
			);

			renderTable();

			await waitFor(() => {
				const icon = screen.getByTestId(GHOST_WARNING_JOB1);
				expect(icon).toHaveClass("text-red-500");
			});
		});
	});

	describe("multi-select mode", () => {
		async function enterSelectMode(user: ReturnType<typeof userEvent.setup>) {
			await user.click(screen.getByTestId(SELECT_MODE_BUTTON));
		}

		it("renders Select button in toolbar", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId(SELECT_MODE_BUTTON)).toBeInTheDocument();
			});
		});

		it("shows checkbox column when Select is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			expect(
				screen.getByRole("checkbox", { name: SELECT_ALL_LABEL }),
			).toBeInTheDocument();
		});

		it("hides standard toolbar filters in select mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
				).toBeInTheDocument();
			});

			await enterSelectMode(user);

			expect(
				screen.queryByRole("combobox", { name: STATUS_FILTER_LABEL }),
			).not.toBeInTheDocument();
		});

		it("shows selection action bar with count and bulk buttons", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			expect(screen.getByTestId(SELECTED_COUNT)).toHaveTextContent(
				"0 selected",
			);
			expect(screen.getByTestId(BULK_DISMISS_BUTTON)).toBeInTheDocument();
			expect(screen.getByTestId(BULK_FAVORITE_BUTTON)).toBeInTheDocument();
			expect(screen.getByTestId(CANCEL_SELECT_BUTTON)).toBeInTheDocument();
		});

		it("updates selected count when rows are checked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);

			expect(screen.getByTestId(SELECTED_COUNT)).toHaveTextContent(
				"1 selected",
			);
		});

		it("disables bulk action buttons when no rows selected", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			expect(screen.getByTestId(BULK_DISMISS_BUTTON)).toBeDisabled();
			expect(screen.getByTestId(BULK_FAVORITE_BUTTON)).toBeDisabled();
		});

		it("calls POST /job-postings/bulk-dismiss with selected IDs", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_SINGLE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/job-postings/bulk-dismiss",
				{ ids: ["job-1"] },
			);
		});

		it("shows success toast after bulk dismiss", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_SINGLE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"1 job dismissed.",
				);
			});
		});

		it("exits select mode after successful bulk dismiss", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_SINGLE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			await waitFor(() => {
				expect(
					screen.queryByTestId(SELECTION_ACTION_BAR),
				).not.toBeInTheDocument();
			});
			expect(
				screen.queryByRole("checkbox", { name: SELECT_ALL_LABEL }),
			).not.toBeInTheDocument();
		});

		it("calls POST /job-postings/bulk-favorite with selected IDs", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_SINGLE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_FAVORITE_BUTTON));

			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/job-postings/bulk-favorite",
				{ ids: ["job-1"], is_favorite: true },
			);
		});

		it("shows success toast after bulk favorite", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_SINGLE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_FAVORITE_BUTTON));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"1 job favorited.",
				);
			});
		});

		it("shows error toast on bulk action failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("INTERNAL_ERROR", "Server error", 500),
			);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const checkboxes = screen.getAllByRole("checkbox", {
				name: SELECT_ROW_LABEL,
			});
			await user.click(checkboxes[0]);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					BULK_ACTION_ERROR,
				);
			});
		});

		it("exits select mode when Cancel is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			expect(screen.getByTestId(SELECTION_ACTION_BAR)).toBeInTheDocument();

			await user.click(screen.getByTestId(CANCEL_SELECT_BUTTON));

			expect(
				screen.queryByTestId(SELECTION_ACTION_BAR),
			).not.toBeInTheDocument();
		});

		it("does not navigate on row click in select mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			const row = screen.getByText(JOB1_TITLE).closest("tr");
			await user.click(row!);

			expect(mocks.mockPush).not.toHaveBeenCalled();
		});

		it("shows warning toast on partial failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue({
				data: {
					succeeded: ["job-1"],
					failed: [{ id: "job-2", error: "NOT_FOUND" }],
				},
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			await user.click(
				screen.getByRole("checkbox", { name: SELECT_ALL_LABEL }),
			);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			await waitFor(() => {
				expect(mocks.mockShowToast.warning).toHaveBeenCalledWith(
					"1 dismissed, 1 failed.",
				);
			});
		});

		it("shows plural toast for multiple dismissed jobs", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue(MOCK_BULK_SUCCESS_MULTI);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await enterSelectMode(user);

			await user.click(
				screen.getByRole("checkbox", { name: SELECT_ALL_LABEL }),
			);
			await user.click(screen.getByTestId(BULK_DISMISS_BUTTON));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"2 jobs dismissed.",
				);
			});
		});
	});

	describe("filtered jobs toggle", () => {
		function makeMixedResponse() {
			return {
				data: [
					makeJob("job-1"),
					makeJob("job-filtered", {
						failed_non_negotiables: [
							{ filter: "salary_min", job_value: 90000, persona_value: 120000 },
						],
						fit_score: null,
						stretch_score: null,
					}),
				],
				meta: MOCK_LIST_META,
			};
		}

		it("renders 'Show filtered jobs' checkbox in toolbar", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOBS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("hides jobs with failed_non_negotiables by default", async () => {
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			expect(screen.queryByText(FILTERED_JOB_TITLE)).not.toBeInTheDocument();
		});

		it("shows filtered jobs when toggle is checked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			expect(screen.getByText(FILTERED_JOB_TITLE)).toBeInTheDocument();
		});

		it("applies dimmed styling to filtered job rows", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			const filteredRow = screen.getByText(FILTERED_JOB_TITLE).closest("tr");
			expect(filteredRow).toHaveClass("opacity-50");
		});

		it("does not dim normal job rows", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			const normalRow = screen.getByText(JOB1_TITLE).closest("tr");
			expect(normalRow).not.toHaveClass("opacity-50");
		});

		it("shows Filtered badge on filtered job rows", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			expect(screen.getByLabelText("Status: Filtered")).toBeInTheDocument();
		});

		it("expands failure reasons when expand button is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			await user.click(screen.getByTestId(EXPAND_REASONS_FILTERED));

			expect(
				screen.getByTestId("failure-reasons-job-filtered"),
			).toBeInTheDocument();
		});

		it("formats salary failure reason correctly", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			await user.click(screen.getByTestId(EXPAND_REASONS_FILTERED));

			expect(
				screen.getByText(/Salary below minimum \(\$90k < \$120k\)/),
			).toBeInTheDocument();
		});

		it("shows warning text for undisclosed data", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeJob("job-1"),
					makeJob("job-undisclosed", {
						failed_non_negotiables: [
							{
								filter: "salary_min",
								job_value: null,
								persona_value: 120000,
							},
						],
						fit_score: null,
						stretch_score: null,
					}),
				],
				meta: MOCK_LIST_META,
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			await user.click(screen.getByTestId("expand-reasons-job-undisclosed"));

			expect(screen.getByText(/Salary not disclosed/)).toBeInTheDocument();
		});

		it("treats empty failed_non_negotiables array as non-filtered", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeJob("job-1", { failed_non_negotiables: [] })],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});
		});

		it("formats generic failure reason correctly", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeJob("job-1"),
					makeJob("job-wm", {
						failed_non_negotiables: [
							{
								filter: "work_model",
								job_value: "Onsite",
								persona_value: "Remote Only",
							},
						],
						fit_score: null,
						stretch_score: null,
					}),
				],
				meta: MOCK_LIST_META,
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			await user.click(screen.getByTestId("expand-reasons-job-wm"));

			expect(
				screen.getByText(/Work model: Onsite.*your preference: Remote Only/),
			).toBeInTheDocument();
		});

		it("hides filtered jobs when toggle is unchecked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(makeMixedResponse());

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(JOB1_TITLE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			expect(screen.getByText(FILTERED_JOB_TITLE)).toBeInTheDocument();

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_FILTERED_LABEL }),
			);

			expect(screen.queryByText(FILTERED_JOB_TITLE)).not.toBeInTheDocument();
		});
	});
});
