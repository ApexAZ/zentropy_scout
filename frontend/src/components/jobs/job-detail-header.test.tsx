/**
 * Tests for the JobDetailHeader component (§7.7).
 *
 * REQ-012 §8.3: Job detail page header — metadata,
 * repost history, ghost detection breakdown, favorite toggle,
 * and external links (View Original / Apply).
 * REQ-015 §8.2: Privacy — also_found_on excluded from UI.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JobDetailHeader } from "./job-detail-header";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const HEADER_TESTID = "job-detail-header";
const LOADING_TESTID = "loading-spinner";
const BACK_LINK_TESTID = "back-to-jobs";
const FAVORITE_TOGGLE_TESTID = "favorite-toggle";
const METADATA_LINE_TESTID = "job-metadata";
const SALARY_TESTID = "job-salary";
const DATES_TESTID = "job-dates";
const VIEW_ORIGINAL_TESTID = "view-original-link";
const APPLY_LINK_TESTID = "apply-link";
const GHOST_SECTION_TESTID = "ghost-risk-section";
const GHOST_SIGNALS_TESTID = "ghost-signals";
const REPOST_HISTORY_TESTID = "repost-history";
const STATUS_BADGE_TESTID = "job-status-badge";

const MOCK_JOB_ID = "job-1";
const FAVORITE_ERROR_MESSAGE = "Failed to update favorite.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns a YYYY-MM-DD date string for N UTC days before today. */
function daysAgoDate(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	const y = d.getUTCFullYear();
	const m = String(d.getUTCMonth() + 1).padStart(2, "0");
	const dd = String(d.getUTCDate()).padStart(2, "0");
	return `${y}-${m}-${dd}`;
}

/** Returns an ISO 8601 datetime string for N days before now (UTC). */
function daysAgoIso(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	return d.toISOString();
}

function makePersonaJob(
	jobOverrides?: Record<string, unknown>,
	personaOverrides?: Record<string, unknown>,
) {
	return {
		id: MOCK_JOB_ID,
		job: {
			id: "jp-1",
			external_id: null,
			source_id: "src-1",
			job_title: "Senior Software Engineer",
			company_name: "Acme Corp",
			company_url: null,
			source_url: "https://example.com/job/123",
			apply_url: "https://example.com/apply/123",
			location: "Austin, TX",
			work_model: "Remote",
			seniority_level: "Senior",
			salary_min: 140000,
			salary_max: 160000,
			salary_currency: "USD",
			description: "Job description text",
			culture_text: null,
			requirements: null,
			years_experience_min: null,
			years_experience_max: null,
			posted_date: daysAgoDate(3),
			application_deadline: null,
			first_seen_date: daysAgoDate(2),
			last_verified_at: null,
			expired_at: null,
			ghost_signals: {
				days_open: 45,
				days_open_score: 40,
				repost_count: 1,
				repost_score: 20,
				vagueness_score: 30,
				missing_fields: ["salary", "deadline"],
				missing_fields_score: 15,
				requirement_mismatch: false,
				requirement_mismatch_score: 0,
				calculated_at: "2026-02-10T12:00:00Z",
				ghost_score: 35,
			},
			ghost_score: 35,
			description_hash: "abc123",
			repost_count: 1,
			previous_posting_ids: ["prev-job-1"],
			is_active: true,
			...jobOverrides,
		},
		status: "Discovered",
		is_favorite: false,
		discovery_method: "manual" as const,
		discovered_at: daysAgoIso(2),
		fit_score: 85,
		stretch_score: 65,
		score_details: null,
		failed_non_negotiables: null,
		scored_at: null,
		dismissed_at: null,
		...personaOverrides,
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
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockRouterBack: vi.fn(),
		MockApiError,
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
	useRouter: () => ({
		push: vi.fn(),
		back: mocks.mockRouterBack,
	}),
}));

function MockLink({
	href,
	children,
	...props
}: {
	href: string;
	children: ReactNode;
	[key: string]: unknown;
}) {
	return (
		<a href={href} {...props}>
			{children}
		</a>
	);
}
MockLink.displayName = "MockLink";

vi.mock("next/link", () => ({
	default: MockLink,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_JOB_RESPONSE = { data: makePersonaJob() };

const MOCK_JOB_NO_SALARY = {
	data: makePersonaJob({
		salary_min: null,
		salary_max: null,
		salary_currency: null,
	}),
};

const MOCK_JOB_FAVORITED = {
	data: makePersonaJob(undefined, { is_favorite: true }),
};

const MOCK_JOB_NO_GHOST = {
	data: makePersonaJob({
		ghost_score: 0,
		ghost_signals: null,
	}),
};

const MOCK_JOB_NO_LINKS = {
	data: makePersonaJob({
		source_url: null,
		apply_url: null,
	}),
};

const MOCK_JOB_NO_REPOST = {
	data: makePersonaJob({
		repost_count: 0,
		previous_posting_ids: null,
		ghost_signals: {
			days_open: 10,
			days_open_score: 10,
			repost_count: 0,
			repost_score: 0,
			vagueness_score: 20,
			missing_fields: [],
			missing_fields_score: 0,
			requirement_mismatch: false,
			requirement_mismatch_score: 0,
			calculated_at: "2026-02-10T12:00:00Z",
			ghost_score: 15,
		},
		ghost_score: 15,
	}),
};

const MOCK_JOB_NO_METADATA = {
	data: makePersonaJob({
		location: null,
		work_model: null,
		seniority_level: null,
		posted_date: null,
	}),
};

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	}
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
}

beforeEach(() => {
	mocks.mockApiGet.mockResolvedValue(MOCK_JOB_RESPONSE);
	mocks.mockApiPatch.mockResolvedValue({ data: makePersonaJob() });
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDetailHeader", () => {
	// -----------------------------------------------------------------------
	// Loading & error states
	// -----------------------------------------------------------------------

	describe("loading and error states", () => {
		it("shows loading spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
			expect(screen.getByText("Failed to load.")).toBeInTheDocument();
		});

		it("shows not found state on 404", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NOT_FOUND", "Not found", 404),
			);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByText(/doesn\u2019t exist/)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Header content
	// -----------------------------------------------------------------------

	describe("header content", () => {
		it("renders back link to dashboard", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BACK_LINK_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(BACK_LINK_TESTID)).toHaveAttribute("href", "/");
		});

		it("renders job title", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(
					screen.getByText("Senior Software Engineer"),
				).toBeInTheDocument();
			});
		});

		it("renders status badge", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(STATUS_BADGE_TESTID)).toBeInTheDocument();
			});
		});

		it("renders metadata line with company, location, work model, and seniority", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(METADATA_LINE_TESTID)).toBeInTheDocument();
			});
			const metadata = screen.getByTestId(METADATA_LINE_TESTID);
			expect(metadata).toHaveTextContent("Acme Corp");
			expect(metadata).toHaveTextContent("Austin, TX");
			expect(metadata).toHaveTextContent("Remote");
			expect(metadata).toHaveTextContent("Senior");
		});

		it("renders salary range", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SALARY_TESTID)).toBeInTheDocument();
			});
			const salary = screen.getByTestId(SALARY_TESTID);
			expect(salary).toHaveTextContent("$140k");
			expect(salary).toHaveTextContent("$160k");
			expect(salary).toHaveTextContent("USD");
		});

		it("renders 'Not disclosed' when no salary", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_SALARY);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SALARY_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(SALARY_TESTID)).toHaveTextContent(
				"Not disclosed",
			);
		});

		it("renders posted and discovered dates", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(DATES_TESTID)).toBeInTheDocument();
			});
			const dates = screen.getByTestId(DATES_TESTID);
			expect(dates).toHaveTextContent("Posted 3 days ago");
			expect(dates).toHaveTextContent("Discovered 2 days ago");
		});

		it("omits posted date when null", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_METADATA);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(DATES_TESTID)).toBeInTheDocument();
			});
			const dates = screen.getByTestId(DATES_TESTID);
			expect(dates).not.toHaveTextContent("Posted");
			expect(dates).toHaveTextContent("Discovered");
		});

		it("renders metadata gracefully when optional fields are null", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_METADATA);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(METADATA_LINE_TESTID)).toBeInTheDocument();
			});
			const metadata = screen.getByTestId(METADATA_LINE_TESTID);
			expect(metadata).toHaveTextContent("Acme Corp");
		});
	});

	// -----------------------------------------------------------------------
	// External links
	// -----------------------------------------------------------------------

	describe("external links", () => {
		it("renders View Original link with source_url", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(VIEW_ORIGINAL_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(VIEW_ORIGINAL_TESTID);
			expect(link).toHaveAttribute("href", "https://example.com/job/123");
			expect(link).toHaveAttribute("target", "_blank");
		});

		it("renders Apply link with apply_url", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(APPLY_LINK_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(APPLY_LINK_TESTID);
			expect(link).toHaveAttribute("href", "https://example.com/apply/123");
			expect(link).toHaveAttribute("target", "_blank");
		});

		it("hides external links when URLs are null", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_LINKS);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(VIEW_ORIGINAL_TESTID),
			).not.toBeInTheDocument();
			expect(screen.queryByTestId(APPLY_LINK_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Favorite toggle
	// -----------------------------------------------------------------------

	describe("favorite toggle", () => {
		it("renders unfilled heart when not favorited", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toHaveTextContent(
				"Favorite",
			);
		});

		it("renders filled heart when favorited", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_FAVORITED);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toHaveTextContent(
				"Unfavorite",
			);
		});

		it("calls apiPatch to toggle favorite", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: makePersonaJob() });
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(FAVORITE_TOGGLE_TESTID));
			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/job-postings/${MOCK_JOB_ID}`,
					{ is_favorite: true },
				);
			});
		});

		it("shows error toast on favorite toggle failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockRejectedValue(new Error("fail"));
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(FAVORITE_TOGGLE_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(FAVORITE_TOGGLE_TESTID));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					FAVORITE_ERROR_MESSAGE,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Ghost risk section
	// -----------------------------------------------------------------------

	describe("ghost risk section", () => {
		it("renders ghost risk score and tier", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(GHOST_SECTION_TESTID)).toBeInTheDocument();
			});
			const section = screen.getByTestId(GHOST_SECTION_TESTID);
			expect(section).toHaveTextContent("35");
			expect(section).toHaveTextContent("Moderate");
		});

		it("renders ghost signal breakdown", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(GHOST_SIGNALS_TESTID)).toBeInTheDocument();
			});
			const signals = screen.getByTestId(GHOST_SIGNALS_TESTID);
			expect(signals).toHaveTextContent("Open 45 days");
			expect(signals).toHaveTextContent("Reposted 1 time");
		});

		it("hides ghost section when ghost_score is 0", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_GHOST);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(GHOST_SECTION_TESTID),
			).not.toBeInTheDocument();
		});

		it("renders repost history when repost_count > 0", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(REPOST_HISTORY_TESTID)).toBeInTheDocument();
			});
			const repost = screen.getByTestId(REPOST_HISTORY_TESTID);
			expect(repost).toHaveTextContent("Repost History");
			expect(repost).toHaveTextContent("1 previous posting");
		});

		it("hides repost history when repost_count is 0", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_JOB_NO_REPOST);
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(GHOST_SECTION_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(REPOST_HISTORY_TESTID),
			).not.toBeInTheDocument();
		});

		it("renders missing fields in ghost signals", async () => {
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(GHOST_SIGNALS_TESTID)).toBeInTheDocument();
			});
			const signals = screen.getByTestId(GHOST_SIGNALS_TESTID);
			expect(signals).toHaveTextContent("salary");
			expect(signals).toHaveTextContent("deadline");
		});
	});

	// -----------------------------------------------------------------------
	// URL scheme security
	// -----------------------------------------------------------------------

	describe("URL scheme security", () => {
		it("suppresses source_url link with javascript: scheme", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makePersonaJob({ source_url: "javascript:alert(1)" }),
			});
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(VIEW_ORIGINAL_TESTID),
			).not.toBeInTheDocument();
		});

		it("suppresses apply_url link with data: scheme", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makePersonaJob({
					apply_url: "data:text/html,<script>alert(1)</script>",
				}),
			});
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(APPLY_LINK_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Salary edge cases
	// -----------------------------------------------------------------------

	describe("salary edge cases", () => {
		it("renders salary_min only as open-ended range", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makePersonaJob({ salary_max: null }),
			});
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SALARY_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(SALARY_TESTID)).toHaveTextContent("$140k+ USD");
		});

		it("renders salary_max only as upper bound", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makePersonaJob({ salary_min: null }),
			});
			render(<JobDetailHeader jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SALARY_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(SALARY_TESTID)).toHaveTextContent(
				"Up to $160k USD",
			);
		});
	});
});
