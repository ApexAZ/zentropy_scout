/**
 * Tests for the ApplicationsList component (§10.1).
 *
 * REQ-012 §11.1: Dedicated /applications page — full table with
 * all statuses, toolbar (search, filter, sort, show archived, select),
 * multi-select mode with bulk archive, and row click navigation.
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

const LIST_TESTID = "applications-list";
const LOADING_TESTID = "loading-spinner";
const EMPTY_MESSAGE = "No applications yet.";
const SEARCH_PLACEHOLDER = "Search applications...";
const STATUS_FILTER_LABEL = "Status filter";
const SORT_BY_LABEL = "Sort by";
const SHOW_ARCHIVED_LABEL = "Show archived";
const EM_DASH = "\u2014";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns an ISO 8601 datetime string for N days before now (UTC). */
function daysAgoIso(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	return d.toISOString();
}

function makeApplication(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: "p-1",
		job_posting_id: "jp-1",
		job_variant_id: "jv-1",
		cover_letter_id: null,
		submitted_resume_pdf_id: null,
		submitted_cover_letter_pdf_id: null,
		job_snapshot: {
			title: `Frontend Developer ${id}`,
			company_name: `Company ${id}`,
			company_url: null,
			description: "Job description",
			requirements: null,
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			location: null,
			work_model: null,
			source_url: null,
			captured_at: "2026-02-10T12:00:00Z",
		},
		status: "Applied",
		current_interview_stage: null,
		offer_details: null,
		rejection_details: null,
		notes: null,
		is_pinned: false,
		applied_at: "2026-02-10T12:00:00Z",
		status_updated_at: "2026-02-12T08:00:00Z",
		created_at: "2026-02-10T12:00:00Z",
		updated_at: "2026-02-12T08:00:00Z",
		archived_at: null,
		...overrides,
	};
}

const MOCK_LIST_META = { total: 2, page: 1, per_page: 20, total_pages: 1 };

const MOCK_APPS_RESPONSE = {
	data: [makeApplication("app-1"), makeApplication("app-2")],
	meta: MOCK_LIST_META,
};

const MOCK_EMPTY_RESPONSE = {
	data: [],
	meta: { ...MOCK_LIST_META, total: 0 },
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
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { ApplicationsList } from "./applications-list";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	// Override invalidateQueries to track calls
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderList() {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<ApplicationsList />
		</Wrapper>,
	);
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPost.mockReset();
	mocks.mockPush.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ApplicationsList", () => {
	describe("loading state", () => {
		it("shows loading spinner initially", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

			renderList();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
			);

			renderList();

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("empty state", () => {
		it("shows empty message when no applications", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
			});
		});
	});

	describe("column rendering", () => {
		it("renders job title from job_snapshot", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByText("Frontend Developer app-1"),
				).toBeInTheDocument();
			});
		});

		it("renders company name as sub-text", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByText("Company app-1")).toBeInTheDocument();
			});
		});

		it("renders status badge", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getAllByLabelText("Status: Applied").length,
				).toBeGreaterThan(0);
			});
		});

		it("renders interview stage pill when Interviewing", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeApplication("app-1", {
						status: "Interviewing",
						current_interview_stage: "Phone Screen",
					}),
				],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByText("Phone Screen")).toBeInTheDocument();
			});
		});

		it("renders em-dash for interview stage when not Interviewing", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeApplication("app-1", { status: "Applied" })],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId(LIST_TESTID)).toBeInTheDocument();
			});

			const list = screen.getByTestId(LIST_TESTID);
			expect(within(list).getByText(EM_DASH)).toBeInTheDocument();
		});

		it("renders applied date using formatDateTimeAgo", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeApplication("app-1", { applied_at: daysAgoIso(0) })],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByText("Today")).toBeInTheDocument();
			});
		});
	});

	describe("row click", () => {
		it("navigates to /applications/[id] on row click", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByText("Frontend Developer app-1"),
				).toBeInTheDocument();
			});

			const row = screen.getByText("Frontend Developer app-1").closest("tr");
			await user.click(row!);

			expect(mocks.mockPush).toHaveBeenCalledWith("/applications/app-1");
		});
	});

	describe("API call", () => {
		it("fetches all statuses by default", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications",
					expect.objectContaining({
						status: "Applied,Interviewing,Offer,Accepted,Rejected,Withdrawn",
					}),
				);
			});
		});
	});

	describe("toolbar", () => {
		it("renders search input", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText(SEARCH_PLACEHOLDER),
				).toBeInTheDocument();
			});
		});

		it("renders status filter dropdown with all statuses", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
				).toBeInTheDocument();
			});

			// Open dropdown and verify all options
			await user.click(
				screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
			);

			await waitFor(() => {
				expect(screen.getByRole("option", { name: "All" })).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Applied" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Interviewing" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Offer" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Accepted" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Rejected" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Withdrawn" }),
				).toBeInTheDocument();
			});
		});

		it("renders sort dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: SORT_BY_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("renders show archived toggle", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("renders select mode button", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});
		});
	});

	describe("status filter", () => {
		it("sends filtered status when status dropdown changes", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
				).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
			);

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Interviewing" }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("option", { name: "Interviewing" }));

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications",
					expect.objectContaining({ status: "Interviewing" }),
				);
			});
		});
	});

	describe("show archived", () => {
		it("excludes archived by default (no include_archived param)", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalled();
			});

			const lastCall = mocks.mockApiGet.mock.calls[0];
			expect(lastCall[1]).not.toHaveProperty("include_archived");
		});

		it("sends include_archived=true when toggle is checked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
				).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications",
					expect.objectContaining({ include_archived: true }),
				);
			});
		});
	});

	describe("search filtering", () => {
		it("filters rows client-side by search text", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByText("Frontend Developer app-1"),
				).toBeInTheDocument();
			});

			await user.type(screen.getByPlaceholderText(SEARCH_PLACEHOLDER), "app-2");

			await waitFor(() => {
				expect(
					screen.queryByText("Frontend Developer app-1"),
				).not.toBeInTheDocument();
			});
			expect(screen.getByText("Frontend Developer app-2")).toBeInTheDocument();
		});
	});

	describe("sort field change", () => {
		it("changes sort when dropdown value changes", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: SORT_BY_LABEL }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("combobox", { name: SORT_BY_LABEL }));

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Applied" }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("option", { name: "Applied" }));

			// Verify the dropdown accepted the new sort value
			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: SORT_BY_LABEL }),
				).toBeInTheDocument();
			});
		});
	});

	describe("multi-select mode", () => {
		it("enters select mode when Select button is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});
			expect(screen.getByTestId("selected-count")).toHaveTextContent(
				"0 selected",
			);
		});

		it("shows Bulk Archive and Cancel buttons in select mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("bulk-archive-button")).toBeInTheDocument();
				expect(screen.getByTestId("cancel-select-button")).toBeInTheDocument();
			});
		});

		it("exits select mode when Cancel is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("cancel-select-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("cancel-select-button"));

			await waitFor(() => {
				expect(
					screen.queryByTestId("selection-action-bar"),
				).not.toBeInTheDocument();
			});
			expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
		});

		it("disables Bulk Archive when no rows selected", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("bulk-archive-button")).toBeDisabled();
			});
		});

		it("disables row click in select mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByText("Frontend Developer app-1"),
				).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			const row = screen.getByText("Frontend Developer app-1").closest("tr");
			await user.click(row!);

			expect(mocks.mockPush).not.toHaveBeenCalled();
		});
	});

	describe("bulk archive", () => {
		it("calls bulk-archive endpoint with selected IDs and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue({
				data: { succeeded: ["app-1"], failed: [] },
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			// Enter select mode
			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			// Select a row checkbox
			const checkboxes = screen.getAllByRole("checkbox", {
				name: "Select row",
			});
			await user.click(checkboxes[0]);

			await waitFor(() => {
				expect(screen.getByTestId("selected-count")).toHaveTextContent(
					"1 selected",
				);
			});

			// Click bulk archive
			await user.click(screen.getByTestId("bulk-archive-button"));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/applications/bulk-archive",
					{ ids: ["app-1"] },
				);
			});

			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"1 application archived.",
			);
			expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
		});

		it("shows error toast when bulk archive fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			const checkboxes = screen.getAllByRole("checkbox", {
				name: "Select row",
			});
			await user.click(checkboxes[0]);

			await waitFor(() => {
				expect(screen.getByTestId("selected-count")).toHaveTextContent(
					"1 selected",
				);
			});

			await user.click(screen.getByTestId("bulk-archive-button"));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Bulk archive failed.",
				);
			});
		});

		it("shows plural success toast when multiple applications archived", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue({
				data: { succeeded: ["app-1", "app-2"], failed: [] },
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			const selectAll = screen.getByRole("checkbox", {
				name: "Select all",
			});
			await user.click(selectAll);

			await waitFor(() => {
				expect(screen.getByTestId("selected-count")).toHaveTextContent(
					"2 selected",
				);
			});

			await user.click(screen.getByTestId("bulk-archive-button"));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"2 applications archived.",
				);
			});
		});

		it("shows error toast when API returns all failed", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue({
				data: {
					succeeded: [],
					failed: [{ id: "app-1", error: "CONFLICT" }],
				},
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			const checkboxes = screen.getAllByRole("checkbox", {
				name: "Select row",
			});
			await user.click(checkboxes[0]);

			await waitFor(() => {
				expect(screen.getByTestId("selected-count")).toHaveTextContent(
					"1 selected",
				);
			});

			await user.click(screen.getByTestId("bulk-archive-button"));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Bulk archive failed.",
				);
			});
		});

		it("shows warning toast for partial bulk archive failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);
			mocks.mockApiPost.mockResolvedValue({
				data: {
					succeeded: ["app-1"],
					failed: [{ id: "app-2", error: "NOT_FOUND" }],
				},
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId("select-mode-button")).toBeInTheDocument();
			});

			await user.click(screen.getByTestId("select-mode-button"));

			await waitFor(() => {
				expect(screen.getByTestId("selection-action-bar")).toBeInTheDocument();
			});

			// Select all rows
			const selectAll = screen.getByRole("checkbox", {
				name: "Select all",
			});
			await user.click(selectAll);

			await waitFor(() => {
				expect(screen.getByTestId("selected-count")).toHaveTextContent(
					"2 selected",
				);
			});

			await user.click(screen.getByTestId("bulk-archive-button"));

			await waitFor(() => {
				expect(mocks.mockShowToast.warning).toHaveBeenCalledWith(
					"1 archived, 1 failed.",
				);
			});
		});
	});

	describe("page header", () => {
		it("renders the page title", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: "Applications" }),
				).toBeInTheDocument();
			});
		});
	});
});
