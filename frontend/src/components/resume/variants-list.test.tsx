/**
 * Tests for the VariantsList component (§8.5).
 *
 * REQ-012 §9.2: Job variants list on resume detail page
 * with status badges, metadata, and status-dependent actions
 * (Review & Approve / Archive for Draft, View for Approved).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_RESUME_ID = "br-1";
const OTHER_RESUME_ID = "br-other";
const LOADING_TESTID = "loading-spinner";
const VARIANT_CARD_TESTID = "variant-card";
const EMPTY_MESSAGE = "No job variants yet.";
const JOB_POSTING_ID_1 = "jp-1";
const JOB_POSTING_ID_2 = "jp-2";
const JOB_TITLE_1 = "Scrum Master";
const COMPANY_1 = "Acme Corp";
const JOB_TITLE_2 = "Agile Coach";
const COMPANY_2 = "TechCo";
const DRAFT_TITLE = `${JOB_TITLE_1} at ${COMPANY_1}`;
const APPROVED_TITLE = `${JOB_TITLE_2} at ${COMPANY_2}`;
const REVIEW_APPROVE_LABEL = /review & approve/i;
const ARCHIVE_LABEL = /archive/i;
const VIEW_LABEL = /^view /i;
const CONFIRM_ARCHIVE_LABEL = /^archive$/i;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns an ISO 8601 datetime string for N days before now (UTC). */
function daysAgoIso(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	return d.toISOString();
}

function makeVariant(
	id: string,
	baseResumeId: string,
	overrides?: Record<string, unknown>,
) {
	return {
		id,
		base_resume_id: baseResumeId,
		job_posting_id: JOB_POSTING_ID_1,
		summary: "Variant summary text",
		job_bullet_order: {},
		modifications_description: null,
		agent_reasoning: null,
		guardrail_result: null,
		status: "Draft",
		snapshot_included_jobs: null,
		snapshot_job_bullet_selections: null,
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		approved_at: null,
		archived_at: null,
		created_at: daysAgoIso(1),
		updated_at: daysAgoIso(1),
		...overrides,
	};
}

function makePersonaJob(jobId: string, jobOverrides?: Record<string, unknown>) {
	return {
		id: `pj-${jobId}`,
		job: {
			id: jobId,
			external_id: null,
			source_id: "src-1",
			job_title: `Job ${jobId}`,
			company_name: `Company ${jobId}`,
			company_url: null,
			source_url: null,
			apply_url: null,
			location: null,
			work_model: null,
			seniority_level: null,
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			description: "Job description",
			culture_text: null,
			requirements: null,
			years_experience_min: null,
			years_experience_max: null,
			posted_date: null,
			application_deadline: null,
			first_seen_date: "2026-02-10",
			last_verified_at: null,
			expired_at: null,
			ghost_signals: null,
			ghost_score: 0,
			description_hash: `hash-${jobId}`,
			repost_count: 0,
			previous_posting_ids: null,
			is_active: true,
			...jobOverrides,
		},
		status: "Discovered",
		is_favorite: false,
		discovery_method: "manual" as const,
		discovered_at: "2026-02-10T12:00:00Z",
		fit_score: null,
		stretch_score: null,
		score_details: null,
		failed_non_negotiables: null,
		scored_at: null,
		dismissed_at: null,
	};
}

const MOCK_LIST_META = { total: 2, page: 1, per_page: 20, total_pages: 1 };

const DRAFT_VARIANT = makeVariant("v-1", BASE_RESUME_ID, {
	job_posting_id: JOB_POSTING_ID_1,
	status: "Draft",
	created_at: daysAgoIso(1),
});

const APPROVED_VARIANT = makeVariant("v-2", BASE_RESUME_ID, {
	job_posting_id: JOB_POSTING_ID_2,
	status: "Approved",
	approved_at: daysAgoIso(3),
	created_at: daysAgoIso(5),
});

const OTHER_RESUME_VARIANT = makeVariant("v-3", OTHER_RESUME_ID, {
	status: "Draft",
});

const ARCHIVED_VARIANT = makeVariant("v-4", BASE_RESUME_ID, {
	status: "Archived",
	archived_at: daysAgoIso(2),
});

const MOCK_VARIANTS_RESPONSE = {
	data: [
		DRAFT_VARIANT,
		APPROVED_VARIANT,
		OTHER_RESUME_VARIANT,
		ARCHIVED_VARIANT,
	],
	meta: { ...MOCK_LIST_META, total: 4 },
};

const MOCK_JOBS_RESPONSE = {
	data: [
		makePersonaJob(JOB_POSTING_ID_1, {
			job_title: JOB_TITLE_1,
			company_name: COMPANY_1,
		}),
		makePersonaJob(JOB_POSTING_ID_2, {
			job_title: JOB_TITLE_2,
			company_name: COMPANY_2,
		}),
	],
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
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { VariantsList } from "./variants-list";

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

function renderVariantsList(baseResumeId = BASE_RESUME_ID) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<VariantsList baseResumeId={baseResumeId} />
		</Wrapper>,
	);
}

/**
 * Configure mockApiGet to return different responses based on path.
 * /job-variants → variants response, /job-postings → jobs response.
 */
function setupMockApi(
	variantsResponse: unknown = MOCK_VARIANTS_RESPONSE,
	jobsResponse: unknown = MOCK_JOBS_RESPONSE,
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === "/job-variants") return Promise.resolve(variantsResponse);
		if (path === "/job-postings") return Promise.resolve(jobsResponse);
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

describe("VariantsList", () => {
	describe("loading state", () => {
		it("shows spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderVariantsList();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows FailedState when API fails", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderVariantsList();
			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("empty state", () => {
		it("shows empty message when no variants for this resume", async () => {
			setupMockApi(MOCK_EMPTY_RESPONSE, MOCK_JOBS_RESPONSE);
			renderVariantsList();
			await waitFor(() => {
				expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
			});
		});
	});

	describe("draft variant card", () => {
		it("shows job title, company, Draft badge, and created time", async () => {
			setupMockApi();
			renderVariantsList();
			await waitFor(() => {
				expect(screen.getByText(DRAFT_TITLE)).toBeInTheDocument();
			});
			expect(screen.getByText("Draft")).toBeInTheDocument();
			expect(screen.getByText(/Created:/)).toBeInTheDocument();
		});

		it("shows Review & Approve and Archive buttons", async () => {
			setupMockApi();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: REVIEW_APPROVE_LABEL }),
				).toBeInTheDocument();
			});
			expect(
				screen.getAllByRole("button", { name: ARCHIVE_LABEL }).length,
			).toBeGreaterThanOrEqual(1);
		});
	});

	describe("approved variant card", () => {
		it("shows job title, company, Approved badge, and approved time", async () => {
			setupMockApi();
			renderVariantsList();
			await waitFor(() => {
				expect(screen.getByText(APPROVED_TITLE)).toBeInTheDocument();
			});
			expect(screen.getByText("Approved")).toBeInTheDocument();
			expect(screen.getByText(/Approved:/)).toBeInTheDocument();
		});

		it("shows View button but not Review & Approve", async () => {
			setupMockApi();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: VIEW_LABEL }),
				).toBeInTheDocument();
			});
			// Only one "Review & Approve" button (the Draft one)
			const reviewButtons = screen.getAllByRole("button", {
				name: REVIEW_APPROVE_LABEL,
			});
			expect(reviewButtons).toHaveLength(1);
		});
	});

	describe("filtering", () => {
		it("only shows variants for the given baseResumeId", async () => {
			setupMockApi();
			renderVariantsList();
			await waitFor(() => {
				const cards = screen.getAllByTestId(VARIANT_CARD_TESTID);
				expect(cards).toHaveLength(2); // v-1 (Draft) + v-2 (Approved), excludes v-3 (other) and v-4 (Archived)
			});
		});

		it("excludes Archived variants", async () => {
			const onlyArchived = {
				data: [ARCHIVED_VARIANT],
				meta: { ...MOCK_LIST_META, total: 1 },
			};
			setupMockApi(onlyArchived, MOCK_JOBS_RESPONSE);
			renderVariantsList();
			await waitFor(() => {
				expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
			});
		});
	});

	describe("navigation", () => {
		it("Review & Approve navigates to variant review page", async () => {
			setupMockApi();
			const user = userEvent.setup();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: REVIEW_APPROVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("button", { name: REVIEW_APPROVE_LABEL }),
			);
			expect(mocks.mockPush).toHaveBeenCalledWith(
				`/resumes/${BASE_RESUME_ID}/variants/v-1/review`,
			);
		});

		it("View navigates to variant detail page", async () => {
			setupMockApi();
			const user = userEvent.setup();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: VIEW_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: VIEW_LABEL }));
			expect(mocks.mockPush).toHaveBeenCalledWith(
				`/resumes/${BASE_RESUME_ID}/variants/v-2`,
			);
		});
	});

	describe("archive action", () => {
		it("opens confirmation dialog, then calls DELETE and shows success toast", async () => {
			setupMockApi();
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: ARCHIVE_LABEL }),
				).toBeInTheDocument();
			});
			// Click archive — opens confirmation dialog
			await user.click(screen.getByRole("button", { name: ARCHIVE_LABEL }));
			// Confirm in the dialog
			await waitFor(() => {
				expect(screen.getByText("Archive Variant")).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("button", { name: CONFIRM_ARCHIVE_LABEL }),
			);
			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith("/job-variants/v-1");
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Variant archived.",
			);
		});

		it("shows error toast on failure", async () => {
			setupMockApi();
			mocks.mockApiDelete.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderVariantsList();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: ARCHIVE_LABEL }),
				).toBeInTheDocument();
			});
			// Click archive — opens confirmation dialog
			await user.click(screen.getByRole("button", { name: ARCHIVE_LABEL }));
			await waitFor(() => {
				expect(screen.getByText("Archive Variant")).toBeInTheDocument();
			});
			// Confirm in the dialog
			await user.click(
				screen.getByRole("button", { name: CONFIRM_ARCHIVE_LABEL }),
			);
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to archive variant.",
				);
			});
		});
	});

	describe("fallback display", () => {
		it("shows fallback title when job posting not found", async () => {
			setupMockApi(MOCK_VARIANTS_RESPONSE, MOCK_EMPTY_RESPONSE);
			renderVariantsList();
			await waitFor(() => {
				const cards = screen.getAllByTestId(VARIANT_CARD_TESTID);
				expect(cards).toHaveLength(2);
			});
			expect(screen.getAllByText(/Unknown position/)).toHaveLength(2);
		});
	});
});
