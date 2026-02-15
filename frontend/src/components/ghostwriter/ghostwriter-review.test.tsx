/**
 * Tests for the GhostwriterReview component (§9.6).
 *
 * REQ-012 §10.7: Unified Ghostwriter review with tabbed
 * resume variant + cover letter and "Approve Both" action.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VARIANT_ID = "v-1";
const COVER_LETTER_ID = "cl-1";
const BASE_RESUME_ID = "br-1";
const PERSONA_ID = "p-1";
const JOB_POSTING_ID = "jp-1";

const LOADING_TESTID = "loading-spinner";
const REVIEW_TESTID = "ghostwriter-review";
const VARIANT_TAB = "Resume Variant";
const COVER_LETTER_TAB = "Cover Letter";
const APPROVE_BOTH_LABEL = "Approve Both";
const APPROVE_RESUME_LABEL = "Approve Resume Only";
const APPROVE_LETTER_LABEL = "Approve Letter Only";
const APPROVE_SPINNER_TESTID = "approve-both-spinner";

const MOCK_TIMESTAMP = "2024-01-15T10:00:00Z";

// ---------------------------------------------------------------------------
// Mock data factories
// ---------------------------------------------------------------------------

function makeVariant(overrides?: Record<string, unknown>) {
	return {
		id: VARIANT_ID,
		base_resume_id: BASE_RESUME_ID,
		job_posting_id: JOB_POSTING_ID,
		summary: "Variant summary",
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
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		...overrides,
	};
}

function makeCoverLetter(overrides?: Record<string, unknown>) {
	return {
		id: COVER_LETTER_ID,
		persona_id: PERSONA_ID,
		application_id: null,
		job_posting_id: JOB_POSTING_ID,
		achievement_stories_used: [],
		draft_text: "Dear Hiring Manager...",
		final_text: null,
		status: "Draft",
		agent_reasoning: null,
		validation_result: null,
		approved_at: null,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		archived_at: null,
		...overrides,
	};
}

function makeJobPosting(overrides?: Record<string, unknown>) {
	return {
		id: JOB_POSTING_ID,
		persona_id: PERSONA_ID,
		external_id: null,
		source_id: "src-1",
		also_found_on: [],
		job_title: "Senior Scrum Master",
		company_name: "Acme Corp",
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
		extracted_skills: [],
		first_seen_at: MOCK_TIMESTAMP,
		last_seen_at: MOCK_TIMESTAMP,
		fit_score: null,
		stretch_score: null,
		score_details: null,
		ghost_score: null,
		ghost_signals: null,
		status: "Discovered",
		dismissed_reason: null,
		repost_history: [],
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		...overrides,
	};
}

const MOCK_VARIANT_RESPONSE = { data: makeVariant() };
const MOCK_COVER_LETTER_RESPONSE = { data: makeCoverLetter() };
const MOCK_JOB_POSTING_RESPONSE = { data: makeJobPosting() };

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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
		mockVariantReview: vi.fn(),
		mockCoverLetterReview: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("@/components/resume/variant-review", () => ({
	VariantReview: mocks.mockVariantReview,
}));

vi.mock("@/components/cover-letter/cover-letter-review", () => ({
	CoverLetterReview: mocks.mockCoverLetterReview,
}));

import { GhostwriterReview } from "./ghostwriter-review";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderReview(
	props?: Partial<{
		variantId: string;
		coverLetterId: string;
		baseResumeId: string;
		personaId: string;
	}>,
) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<GhostwriterReview
				variantId={props?.variantId ?? VARIANT_ID}
				coverLetterId={props?.coverLetterId ?? COVER_LETTER_ID}
				baseResumeId={props?.baseResumeId ?? BASE_RESUME_ID}
				personaId={props?.personaId ?? PERSONA_ID}
			/>
		</Wrapper>,
	);
}

function setupMockApi(overrides?: {
	variant?: unknown;
	coverLetter?: unknown;
	jobPosting?: unknown;
}) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === `/job-variants/${VARIANT_ID}`)
			return Promise.resolve(overrides?.variant ?? MOCK_VARIANT_RESPONSE);
		if (path === `/cover-letters/${COVER_LETTER_ID}`)
			return Promise.resolve(
				overrides?.coverLetter ?? MOCK_COVER_LETTER_RESPONSE,
			);
		if (path === `/job-postings/${JOB_POSTING_ID}`)
			return Promise.resolve(
				overrides?.jobPosting ?? MOCK_JOB_POSTING_RESPONSE,
			);
		return Promise.resolve({ data: null });
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPost.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());

	// Mock child components to render identifiable stubs
	mocks.mockVariantReview.mockImplementation(
		(props: Record<string, unknown>) => (
			<div
				data-testid="variant-review-stub"
				data-hide-actions={String(props.hideActions)}
			>
				VariantReview
			</div>
		),
	);
	mocks.mockCoverLetterReview.mockImplementation(
		(props: Record<string, unknown>) => (
			<div
				data-testid="cover-letter-review-stub"
				data-hide-actions={String(props.hideActions)}
			>
				CoverLetterReview
			</div>
		),
	);
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GhostwriterReview", () => {
	// Loading / Error
	// -----------------------------------------------------------------------

	describe("loading state", () => {
		it("shows spinner while fetching data", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderReview();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows FailedState when variant fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderReview();
			await waitFor(() => {
				expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
			});
		});

		it("shows FailedState when cover letter fetch fails", async () => {
			mocks.mockApiGet.mockImplementation((path: string) => {
				if (path === `/cover-letters/${COVER_LETTER_ID}`)
					return Promise.reject(
						new mocks.MockApiError("NOT_FOUND", "Not found", 404),
					);
				if (path === `/job-variants/${VARIANT_ID}`)
					return Promise.resolve(MOCK_VARIANT_RESPONSE);
				if (path === `/job-postings/${JOB_POSTING_ID}`)
					return Promise.resolve(MOCK_JOB_POSTING_RESPONSE);
				return Promise.resolve({ data: null });
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
			});
		});
	});

	// Header
	// -----------------------------------------------------------------------

	describe("header", () => {
		it("shows job title and company in header", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(
					screen.getByText("Materials for: Senior Scrum Master at Acme Corp"),
				).toBeInTheDocument();
			});
		});
	});

	// Tabs
	// -----------------------------------------------------------------------

	describe("tabs", () => {
		it("renders both tab triggers", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("tab", { name: VARIANT_TAB }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("tab", { name: COVER_LETTER_TAB }),
			).toBeInTheDocument();
		});

		it("shows Resume Variant tab active by default", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByRole("tab", { name: VARIANT_TAB })).toHaveAttribute(
				"data-state",
				"active",
			);
		});

		it("shows VariantReview stub in Resume Variant tab", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId("variant-review-stub")).toBeInTheDocument();
			});
		});

		it("switches to Cover Letter tab on click", async () => {
			setupMockApi();
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("tab", { name: COVER_LETTER_TAB }));

			expect(
				screen.getByRole("tab", { name: COVER_LETTER_TAB }),
			).toHaveAttribute("data-state", "active");
			expect(
				screen.getByTestId("cover-letter-review-stub"),
			).toBeInTheDocument();
		});
	});

	// Child component props
	// -----------------------------------------------------------------------

	describe("child component props", () => {
		it("passes hideActions=true to VariantReview", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId("variant-review-stub")).toBeInTheDocument();
			});
			expect(screen.getByTestId("variant-review-stub")).toHaveAttribute(
				"data-hide-actions",
				"true",
			);
		});

		it("passes correct IDs to VariantReview", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId("variant-review-stub")).toBeInTheDocument();
			});
			const calls = mocks.mockVariantReview.mock.calls;
			const lastProps = calls[calls.length - 1][0];
			expect(lastProps).toMatchObject({
				variantId: VARIANT_ID,
				baseResumeId: BASE_RESUME_ID,
				personaId: PERSONA_ID,
				hideActions: true,
			});
		});

		it("passes hideActions=true to CoverLetterReview", async () => {
			setupMockApi();
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("tab", { name: COVER_LETTER_TAB }));

			expect(screen.getByTestId("cover-letter-review-stub")).toHaveAttribute(
				"data-hide-actions",
				"true",
			);
		});

		it("passes correct coverLetterId to CoverLetterReview", async () => {
			setupMockApi();
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("tab", { name: COVER_LETTER_TAB }));

			const calls = mocks.mockCoverLetterReview.mock.calls;
			const lastProps = calls[calls.length - 1][0];
			expect(lastProps).toMatchObject({
				coverLetterId: COVER_LETTER_ID,
				hideActions: true,
			});
		});
	});

	// Approval buttons — visibility
	// -----------------------------------------------------------------------

	describe("approval button visibility", () => {
		it("shows all three buttons when both are Draft", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: APPROVE_RESUME_LABEL }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: APPROVE_LETTER_LABEL }),
			).toBeInTheDocument();
		});

		it("hides all buttons when both are Approved", async () => {
			setupMockApi({
				variant: { data: makeVariant({ status: "Approved" }) },
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: APPROVE_BOTH_LABEL }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: APPROVE_RESUME_LABEL }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: APPROVE_LETTER_LABEL }),
			).not.toBeInTheDocument();
		});

		it("hides Approve Resume Only when variant is already Approved", async () => {
			setupMockApi({
				variant: { data: makeVariant({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: APPROVE_RESUME_LABEL }),
			).not.toBeInTheDocument();
			// Approve Both hidden (variant already approved)
			expect(
				screen.queryByRole("button", { name: APPROVE_BOTH_LABEL }),
			).not.toBeInTheDocument();
			// Approve Letter Only still visible
			expect(
				screen.getByRole("button", { name: APPROVE_LETTER_LABEL }),
			).toBeInTheDocument();
		});

		it("hides Approve Letter Only when cover letter is already Approved", async () => {
			setupMockApi({
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: APPROVE_LETTER_LABEL }),
			).not.toBeInTheDocument();
			// Approve Both hidden (cover letter already approved)
			expect(
				screen.queryByRole("button", { name: APPROVE_BOTH_LABEL }),
			).not.toBeInTheDocument();
			// Approve Resume Only still visible
			expect(
				screen.getByRole("button", { name: APPROVE_RESUME_LABEL }),
			).toBeInTheDocument();
		});
	});

	// Approval buttons — blocking
	// -----------------------------------------------------------------------

	describe("approval blocking", () => {
		it("disables Approve Both when variant has error-severity guardrails", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({
						guardrail_result: {
							passed: false,
							violations: [
								{
									severity: "error",
									rule: "unknown_skills",
									message: "Unknown skills found",
								},
							],
						},
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			).toBeDisabled();
		});

		it("disables Approve Both when cover letter has error-severity validation", async () => {
			setupMockApi({
				coverLetter: {
					data: makeCoverLetter({
						validation_result: {
							passed: false,
							issues: [
								{
									severity: "error",
									rule: "length_min",
									message: "Too short",
								},
							],
							word_count: 50,
						},
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			).toBeDisabled();
		});

		it("disables Approve Resume Only when variant has error-severity guardrails", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({
						guardrail_result: {
							passed: false,
							violations: [
								{
									severity: "error",
									rule: "unknown_skills",
									message: "Unknown skills found",
								},
							],
						},
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_RESUME_LABEL }),
			).toBeDisabled();
		});

		it("disables Approve Letter Only when cover letter has error-severity validation", async () => {
			setupMockApi({
				coverLetter: {
					data: makeCoverLetter({
						validation_result: {
							passed: false,
							issues: [
								{
									severity: "error",
									rule: "length_min",
									message: "Too short",
								},
							],
							word_count: 50,
						},
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_LETTER_LABEL }),
			).toBeDisabled();
		});

		it("keeps Approve Both enabled when only warnings present", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({
						guardrail_result: {
							passed: true,
							violations: [
								{
									severity: "warning",
									rule: "summary_length",
									message: "Summary changed significantly",
								},
							],
						},
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			).toBeEnabled();
		});
	});

	// Approve Both action
	// -----------------------------------------------------------------------

	describe("Approve Both action", () => {
		it("calls both variant approve and cover letter patch", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/job-variants/${VARIANT_ID}/approve`,
				);
			});
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/cover-letters/${COVER_LETTER_ID}`,
				{ status: "Approved" },
			);
		});

		it("shows loading state during approval", async () => {
			setupMockApi();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(screen.getByTestId(APPROVE_SPINNER_TESTID)).toBeInTheDocument();
			});
		});

		it("shows success toast and invalidates caches on success", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Both materials approved.",
				);
			});
			expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
		});

		it("shows error toast when both fail", async () => {
			setupMockApi();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to approve materials.",
				);
			});
		});

		it("shows warning toast on partial failure (resume succeeds, letter fails)", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.warning).toHaveBeenCalledWith(
					"Resume approved, but cover letter failed. Try approving the letter separately.",
				);
			});
		});

		it("shows warning toast on partial failure (letter succeeds, resume fails)", async () => {
			setupMockApi();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_BOTH_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.warning).toHaveBeenCalledWith(
					"Cover letter approved, but resume failed. Try approving the resume separately.",
				);
			});
		});
	});

	// Approve Resume Only action
	// -----------------------------------------------------------------------

	describe("Approve Resume Only action", () => {
		it("calls only variant approve API", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_RESUME_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/job-variants/${VARIANT_ID}/approve`,
				);
			});
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("shows success toast for resume approval", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_RESUME_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Resume variant approved.",
				);
			});
		});
	});

	// Approve Letter Only action
	// -----------------------------------------------------------------------

	describe("Approve Letter Only action", () => {
		it("calls only cover letter patch API", async () => {
			setupMockApi();
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_LETTER_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/cover-letters/${COVER_LETTER_ID}`,
					{ status: "Approved" },
				);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows success toast for cover letter approval", async () => {
			setupMockApi();
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: APPROVE_LETTER_LABEL }),
			);

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Cover letter approved.",
				);
			});
		});
	});
});
