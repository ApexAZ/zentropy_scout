/**
 * Tests for the ResumeList component (§8.1).
 *
 * REQ-012 §9.1: Resume list page with base resume cards
 * showing name, role type, status, primary badge, variant count,
 * last updated, and actions (View & Edit, Download PDF, Archive).
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

const LIST_TESTID = "resume-list";
const LOADING_TESTID = "loading-spinner";
const EMPTY_TITLE = "No resumes yet";
const SHOW_ARCHIVED_LABEL = "Show archived";
const RESUME_NAME_PRIMARY = "Scrum Master";
const RESUME_NAME_SECONDARY = "Product Owner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns an ISO 8601 datetime string for N days before now (UTC). */
function daysAgoIso(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	return d.toISOString();
}

function makeResume(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: "p-1",
		name: `Resume ${id}`,
		role_type: `Role ${id}`,
		summary: "Professional summary text",
		included_jobs: [],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: {},
		job_bullet_order: {},
		rendered_at: null,
		is_primary: false,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: "2026-02-10T12:00:00Z",
		updated_at: daysAgoIso(2),
		...overrides,
	};
}

function makeVariant(
	id: string,
	baseResumeId: string,
	overrides?: Record<string, unknown>,
) {
	return {
		id,
		base_resume_id: baseResumeId,
		job_posting_id: "jp-1",
		summary: "Variant summary",
		job_bullet_order: {},
		modifications_description: null,
		status: "Approved",
		snapshot_included_jobs: null,
		snapshot_job_bullet_selections: null,
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		approved_at: null,
		archived_at: null,
		created_at: "2026-02-10T12:00:00Z",
		updated_at: "2026-02-10T12:00:00Z",
		...overrides,
	};
}

const MOCK_LIST_META = { total: 2, page: 1, per_page: 20, total_pages: 1 };

const MOCK_RESUMES_RESPONSE = {
	data: [
		makeResume("r-1", { is_primary: true, name: RESUME_NAME_PRIMARY }),
		makeResume("r-2", { name: RESUME_NAME_SECONDARY }),
	],
	meta: MOCK_LIST_META,
};

const MOCK_VARIANTS_RESPONSE = {
	data: [
		makeVariant("v-1", "r-1", { status: "Approved" }),
		makeVariant("v-2", "r-1", { status: "Draft" }),
		makeVariant("v-3", "r-1", { status: "Approved" }),
	],
	meta: { total: 3, page: 1, per_page: 20, total_pages: 1 },
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
		mockApiDelete: vi.fn(),
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
	apiDelete: mocks.mockApiDelete,
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { ResumeList } from "./resume-list";

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

function renderList() {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<ResumeList />
		</Wrapper>,
	);
}

/**
 * Configure mockApiGet to return different responses based on path.
 * Calls to /base-resumes get the resumes response, calls to /job-variants
 * get the variants response.
 */
function setupMockApi(
	resumesResponse: unknown = MOCK_RESUMES_RESPONSE,
	variantsResponse: unknown = MOCK_VARIANTS_RESPONSE,
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === "/base-resumes") return Promise.resolve(resumesResponse);
		if (path === "/job-variants") return Promise.resolve(variantsResponse);
		return Promise.resolve(MOCK_EMPTY_RESPONSE);
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiDelete.mockReset();
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

describe("ResumeList", () => {
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
		it("shows empty message with 'New Resume' action when no resumes", async () => {
			setupMockApi(MOCK_EMPTY_RESPONSE, MOCK_EMPTY_RESPONSE);

			renderList();

			await waitFor(() => {
				expect(screen.getByText(EMPTY_TITLE)).toBeInTheDocument();
			});
			expect(screen.getByRole("status")).toBeInTheDocument();
		});
	});

	describe("page header", () => {
		it("renders 'Your Resumes' heading", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: "Your Resumes" }),
				).toBeInTheDocument();
			});
		});

		it("renders '+ New Resume' button", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /New Resume/i }),
				).toBeInTheDocument();
			});
		});
	});

	describe("resume cards", () => {
		it("renders resume name", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});
			expect(screen.getByText(RESUME_NAME_SECONDARY)).toBeInTheDocument();
		});

		it("renders role type as sub-text", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(/Role r-1/)).toBeInTheDocument();
			});
		});

		it("shows primary badge for primary resume", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText("Primary")).toBeInTheDocument();
			});
		});

		it("does not show primary badge for non-primary resume", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});

			// Only one "Primary" badge should exist (for Scrum Master)
			const badges = screen.getAllByText("Primary");
			expect(badges).toHaveLength(1);
		});

		it("renders status badge", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(
					screen.getAllByLabelText("Status: Active").length,
				).toBeGreaterThan(0);
			});
		});

		it("renders last updated relative date", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getAllByText(/2 days ago/).length).toBeGreaterThan(0);
			});
		});

		it("renders variant count for resume with variants", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(/3 variants/)).toBeInTheDocument();
			});
		});

		it("renders pending review count when draft variants exist", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(/1 pending review/)).toBeInTheDocument();
			});
		});
	});

	describe("card actions", () => {
		it("navigates to /resumes/[id] on 'View & Edit' click", async () => {
			const user = userEvent.setup();
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});

			const cards = screen.getAllByTestId("resume-card");
			const viewButton = within(cards[0]).getByRole("link", {
				name: /View & Edit/i,
			});
			await user.click(viewButton);

			expect(mocks.mockPush).toHaveBeenCalledWith("/resumes/r-1");
		});

		it("renders download PDF link with correct href", async () => {
			setupMockApi(
				{
					data: [
						makeResume("r-1", {
							name: RESUME_NAME_PRIMARY,
							rendered_at: "2026-02-10T12:00:00Z",
						}),
					],
					meta: { ...MOCK_LIST_META, total: 1 },
				},
				MOCK_EMPTY_RESPONSE,
			);

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});

			const downloadLink = screen.getByRole("link", {
				name: /Download PDF/i,
			});
			expect(downloadLink).toHaveAttribute(
				"href",
				"http://localhost:8000/api/v1/base-resumes/r-1/download",
			);
		});

		it("does not render download link when no rendered PDF exists", async () => {
			setupMockApi(
				{
					data: [makeResume("r-1", { rendered_at: null })],
					meta: { ...MOCK_LIST_META, total: 1 },
				},
				MOCK_EMPTY_RESPONSE,
			);

			renderList();

			await waitFor(() => {
				expect(screen.getByTestId(LIST_TESTID)).toBeInTheDocument();
			});

			expect(
				screen.queryByRole("link", { name: /Download PDF/i }),
			).not.toBeInTheDocument();
		});

		it("calls archive endpoint on 'Archive' button click", async () => {
			const user = userEvent.setup();
			mocks.mockApiDelete.mockResolvedValue(undefined);
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});

			const cards = screen.getAllByTestId("resume-card");
			const archiveButton = within(cards[0]).getByRole("button", {
				name: /Archive/i,
			});
			await user.click(archiveButton);

			expect(mocks.mockApiDelete).toHaveBeenCalledWith("/base-resumes/r-1");
		});
	});

	describe("show archived toggle", () => {
		it("renders 'Show archived' checkbox", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("shows archived resumes when toggle is checked", async () => {
			const user = userEvent.setup();
			const archivedResume = makeResume("r-3", {
				name: "Archived Resume",
				status: "Archived",
				archived_at: "2026-02-08T12:00:00Z",
			});

			// First call: active only; second call: includes archived
			let callCount = 0;
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path === "/base-resumes") {
					callCount++;
					if (callCount <= 1) {
						return Promise.resolve(MOCK_RESUMES_RESPONSE);
					}
					return Promise.resolve({
						data: [...MOCK_RESUMES_RESPONSE.data, archivedResume],
						meta: { ...MOCK_LIST_META, total: 3 },
					});
				}
				if (path === "/job-variants") {
					return Promise.resolve(MOCK_EMPTY_RESPONSE);
				}
				return Promise.resolve(MOCK_EMPTY_RESPONSE);
			});

			renderList();

			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME_PRIMARY)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", { name: SHOW_ARCHIVED_LABEL }),
			);

			await waitFor(() => {
				expect(screen.getByText("Archived Resume")).toBeInTheDocument();
			});
		});
	});

	describe("API calls", () => {
		it("fetches base resumes from /base-resumes", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/base-resumes",
					expect.any(Object),
				);
			});
		});

		it("fetches variants from /job-variants", async () => {
			setupMockApi();

			renderList();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith("/job-variants");
			});
		});
	});
});
