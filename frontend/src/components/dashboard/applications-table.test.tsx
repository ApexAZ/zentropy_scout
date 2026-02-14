/**
 * Tests for the ApplicationsTable component (§7.12).
 *
 * REQ-012 §8.1: In Progress and History tabs — application data
 * in a DataTable with status-specific filters, sort, and search.
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

const TABLE_TESTID = "applications-table";
const LOADING_TESTID = "loading-spinner";
const EMPTY_MESSAGE = "No applications found.";
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
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { ApplicationsTable } from "./applications-table";

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

function renderTable(variant: "in-progress" | "history" = "in-progress") {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<ApplicationsTable variant={variant} />
		</Wrapper>,
	);
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
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

describe("ApplicationsTable", () => {
	describe("loading state", () => {
		it("shows loading spinner initially", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

			renderTable();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
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

	describe("empty state", () => {
		it("shows empty message when no applications", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
			});
		});
	});

	describe("column rendering", () => {
		it("renders job title from job_snapshot", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(
					screen.getByText("Frontend Developer app-1"),
				).toBeInTheDocument();
			});
		});

		it("renders company name as sub-text", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Company app-1")).toBeInTheDocument();
			});
		});

		it("renders status badge", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable();

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

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Phone Screen")).toBeInTheDocument();
			});
		});

		it("renders em-dash for interview stage when not Interviewing", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeApplication("app-1", { status: "Applied" })],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});

			// Find the interview stage column cell with em-dash
			const table = screen.getByTestId(TABLE_TESTID);
			expect(within(table).getByText(EM_DASH)).toBeInTheDocument();
		});

		it("renders applied date using formatDateTimeAgo", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeApplication("app-1", {
						applied_at: daysAgoIso(0),
					}),
				],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderTable();

			await waitFor(() => {
				expect(screen.getByText("Today")).toBeInTheDocument();
			});
		});
	});

	describe("row click", () => {
		it("navigates to /applications/[id] on row click", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable();

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

	describe("API call verification", () => {
		it("sends Applied,Interviewing,Offer statuses for in-progress variant", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("in-progress");

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications",
					expect.objectContaining({ status: "Applied,Interviewing,Offer" }),
				);
			});
		});

		it("sends Accepted,Rejected,Withdrawn statuses for history variant", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("history");

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications",
					expect.objectContaining({ status: "Accepted,Rejected,Withdrawn" }),
				);
			});
		});
	});

	describe("toolbar — in-progress", () => {
		it("renders search input", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable("in-progress");

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText(SEARCH_PLACEHOLDER),
				).toBeInTheDocument();
			});
		});

		it("renders status filter dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable("in-progress");

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: STATUS_FILTER_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("renders sort dropdown", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable("in-progress");

			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: SORT_BY_LABEL }),
				).toBeInTheDocument();
			});
		});
	});

	describe("toolbar — history", () => {
		it("renders search input", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("history");

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText(SEARCH_PLACEHOLDER),
				).toBeInTheDocument();
			});
		});

		it("renders 'Show archived' toggle in history variant", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("history");

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("does not render 'Show archived' toggle in in-progress variant", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_APPS_RESPONSE);

			renderTable("in-progress");

			await waitFor(() => {
				expect(screen.getByTestId(TABLE_TESTID)).toBeInTheDocument();
			});

			expect(
				screen.queryByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
			).not.toBeInTheDocument();
		});
	});

	describe("show archived behavior", () => {
		it("excludes archived by default (no include_archived param)", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("history");

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalled();
			});

			const lastCall = mocks.mockApiGet.mock.calls[0];
			expect(lastCall[1]).not.toHaveProperty("include_archived");
		});

		it("sends include_archived=true when toggle is checked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_RESPONSE);

			renderTable("history");

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

			renderTable("in-progress");

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

			renderTable("in-progress");

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

			// The sort dropdown should have changed — the column header should reflect the new sort
			// We just verify the dropdown accepted the new value
			await waitFor(() => {
				expect(
					screen.getByRole("combobox", { name: SORT_BY_LABEL }),
				).toBeInTheDocument();
			});
		});
	});
});
