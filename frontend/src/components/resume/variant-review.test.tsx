/**
 * Tests for the VariantReview component (§8.6, §8.7).
 *
 * REQ-012 §9.3: Side-by-side comparison of base resume and
 * tailored variant with diff highlighting, move indicators,
 * and Approve/Regenerate/Archive actions.
 * REQ-012 §9.3-9.4: Agent reasoning display and guardrail
 * violation banners with blocking behavior.
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
const VARIANT_ID = "v-1";
const PERSONA_ID = "p-1";
const JOB_POSTING_ID = "jp-1";
const JOB_ID = "job-1";
const LOADING_TESTID = "loading-spinner";
const BACK_LINK_TESTID = "back-link";
const BASE_PANEL_TESTID = "base-panel";
const VARIANT_PANEL_TESTID = "variant-panel";
const APPROVE_LABEL = /approve/i;
const ARCHIVE_LABEL = /archive/i;
const REGENERATE_LABEL = /regenerate/i;
const CONFIRM_ARCHIVE_LABEL = /^archive$/i;
const VARIANT_REVIEW_TESTID = "variant-review";
const REASONING_TESTID = "agent-reasoning";
const REASONING_TOGGLE_TESTID = "agent-reasoning-toggle";
const GUARDRAIL_BANNER_TESTID = "guardrail-violations";
const GO_TO_PERSONA_TESTID = "go-to-persona-link";

const MOCK_TIMESTAMP = "2024-01-15T10:00:00Z";
const MOCK_VARIANT_TIMESTAMP = "2024-02-01T14:30:00Z";

const MOCK_REASONING =
	'Added emphasis on "SAFe" and "scaled Agile" — mentioned 3x in posting. Moved SAFe implementation bullet to position 1.';

const MOCK_GUARDRAIL_PASSED = {
	passed: true,
	violations: [],
};

const MOCK_GUARDRAIL_ERROR = {
	passed: false,
	violations: [
		{
			severity: "error" as const,
			rule: "unknown_skills_referenced",
			message: 'Summary mentions skills not in your profile: "Go", "Rust"',
		},
	],
};

const MOCK_GUARDRAIL_WARNING = {
	passed: true,
	violations: [
		{
			severity: "warning" as const,
			rule: "summary_length_change",
			message: "Summary length changed by more than 20%.",
		},
	],
};

const MOCK_GUARDRAIL_MIXED = {
	passed: false,
	violations: [
		{
			severity: "error" as const,
			rule: "unknown_skills_referenced",
			message: 'Summary mentions skills not in your profile: "Go", "Rust"',
		},
		{
			severity: "warning" as const,
			rule: "summary_length_change",
			message: "Summary length changed by more than 20%.",
		},
	],
};

const BASE_SUMMARY =
	"Experienced Scrum Master with 8 years of project management";
const VARIANT_SUMMARY =
	"Experienced Scrum Master with 8 years of scaled Agile leadership";

// ---------------------------------------------------------------------------
// Mock data factories
// ---------------------------------------------------------------------------

function makeBaseResume(overrides?: Record<string, unknown>) {
	return {
		id: BASE_RESUME_ID,
		persona_id: PERSONA_ID,
		name: "My Resume",
		role_type: "Scrum Master",
		summary: BASE_SUMMARY,
		included_jobs: [JOB_ID],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: { [JOB_ID]: ["b-1", "b-2", "b-3"] },
		job_bullet_order: { [JOB_ID]: ["b-1", "b-2", "b-3"] },
		rendered_at: null,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		...overrides,
	};
}

function makeVariant(overrides?: Record<string, unknown>) {
	return {
		id: VARIANT_ID,
		base_resume_id: BASE_RESUME_ID,
		job_posting_id: JOB_POSTING_ID,
		summary: VARIANT_SUMMARY,
		job_bullet_order: { [JOB_ID]: ["b-3", "b-1", "b-2"] },
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
		created_at: MOCK_VARIANT_TIMESTAMP,
		updated_at: MOCK_VARIANT_TIMESTAMP,
		...overrides,
	};
}

function makeWorkHistory() {
	return {
		id: JOB_ID,
		persona_id: PERSONA_ID,
		company_name: "TechCorp",
		company_industry: null,
		job_title: "Scrum Master",
		start_date: "2020-01-01",
		end_date: null,
		is_current: true,
		location: "Remote",
		work_model: "Remote",
		description: null,
		display_order: 0,
		bullets: [
			{
				id: "b-1",
				work_history_id: JOB_ID,
				text: "Led team of 12 engineers",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			},
			{
				id: "b-2",
				work_history_id: JOB_ID,
				text: "Reduced cycle time by 40%",
				skills_demonstrated: [],
				metrics: null,
				display_order: 1,
			},
			{
				id: "b-3",
				work_history_id: JOB_ID,
				text: "Implemented SAFe framework",
				skills_demonstrated: [],
				metrics: null,
				display_order: 2,
			},
		],
	};
}

function makePersonaJob(overrides?: Record<string, unknown>) {
	return {
		id: "pj-1",
		job: {
			id: JOB_POSTING_ID,
			external_id: null,
			source_id: "src-1",
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
			requirements: null,
			years_experience_min: null,
			years_experience_max: null,
			posted_date: null,
			application_deadline: null,
			first_seen_date: MOCK_TIMESTAMP,
			last_verified_at: null,
			expired_at: null,
			ghost_signals: null,
			ghost_score: 0,
			description_hash: "hash-1",
			repost_count: 0,
			previous_posting_ids: null,
			is_active: true,
		},
		status: "Discovered",
		is_favorite: false,
		discovery_method: "manual",
		discovered_at: MOCK_TIMESTAMP,
		fit_score: null,
		stretch_score: null,
		score_details: null,
		failed_non_negotiables: null,
		scored_at: null,
		dismissed_at: null,
		...overrides,
	};
}

const MOCK_BASE_RESUME_RESPONSE = { data: makeBaseResume() };
const MOCK_VARIANT_RESPONSE = { data: makeVariant() };
const MOCK_WORK_HISTORY_RESPONSE = {
	data: [makeWorkHistory()],
	meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
};
const MOCK_JOB_POSTING_RESPONSE = { data: makePersonaJob() };

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
	apiPost: mocks.mockApiPost,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { VariantReview } from "./variant-review";

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

function renderVariantReview(
	baseResumeId = BASE_RESUME_ID,
	variantId = VARIANT_ID,
	personaId = PERSONA_ID,
) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<VariantReview
				baseResumeId={baseResumeId}
				variantId={variantId}
				personaId={personaId}
			/>
		</Wrapper>,
	);
}

/**
 * Configure mockApiGet to return different responses based on path.
 */
function setupMockApi(overrides?: {
	variant?: unknown;
	baseResume?: unknown;
	workHistory?: unknown;
	jobPosting?: unknown;
}) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === `/job-variants/${VARIANT_ID}`)
			return Promise.resolve(overrides?.variant ?? MOCK_VARIANT_RESPONSE);
		if (path === `/base-resumes/${BASE_RESUME_ID}`)
			return Promise.resolve(
				overrides?.baseResume ?? MOCK_BASE_RESUME_RESPONSE,
			);
		if (path.includes("/work-history"))
			return Promise.resolve(
				overrides?.workHistory ?? MOCK_WORK_HISTORY_RESPONSE,
			);
		if (path === `/job-postings/${JOB_POSTING_ID}`)
			return Promise.resolve(
				overrides?.jobPosting ?? MOCK_JOB_POSTING_RESPONSE,
			);
		return Promise.resolve({ data: [] });
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPost.mockReset();
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

describe("VariantReview", () => {
	describe("loading state", () => {
		it("shows spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderVariantReview();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows FailedState when API fails", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("header", () => {
		it("shows job posting title and company", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByText("Senior Scrum Master at Acme Corp"),
				).toBeInTheDocument();
			});
		});

		it("has a back link to the resume detail page", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const backLink = screen.getByTestId(BACK_LINK_TESTID);
				expect(backLink).toBeInTheDocument();
				expect(backLink).toHaveAttribute("href", `/resumes/${BASE_RESUME_ID}`);
			});
		});
	});

	describe("summary diff", () => {
		it("shows base summary in left panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const basePanel = screen.getByTestId(BASE_PANEL_TESTID);
				expect(basePanel).toHaveTextContent("project");
				expect(basePanel).toHaveTextContent("management");
			});
		});

		it("shows variant summary in right panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const variantPanel = screen.getByTestId(VARIANT_PANEL_TESTID);
				expect(variantPanel).toHaveTextContent("scaled");
				expect(variantPanel).toHaveTextContent("Agile");
				expect(variantPanel).toHaveTextContent("leadership");
			});
		});

		it("highlights added words in variant panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const addedTokens = screen
					.getByTestId(VARIANT_PANEL_TESTID)
					.querySelectorAll("[data-diff='added']");
				const addedTexts = Array.from(addedTokens).map((el) => el.textContent);
				expect(addedTexts).toContain("scaled");
				expect(addedTexts).toContain("Agile");
				expect(addedTexts).toContain("leadership");
			});
		});

		it("highlights removed words in base panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const removedTokens = screen
					.getByTestId(BASE_PANEL_TESTID)
					.querySelectorAll("[data-diff='removed']");
				const removedTexts = Array.from(removedTokens).map(
					(el) => el.textContent,
				);
				expect(removedTexts).toContain("project");
				expect(removedTexts).toContain("management");
			});
		});
	});

	describe("bullet diff", () => {
		it("shows job company as section header in both panels", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				// TechCorp appears in both base and variant panels
				expect(screen.getAllByText("TechCorp")).toHaveLength(2);
			});
		});

		it("shows bullets in base order in left panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const basePanel = screen.getByTestId(BASE_PANEL_TESTID);
				expect(basePanel).toHaveTextContent("Led team of 12 engineers");
				expect(basePanel).toHaveTextContent("Reduced cycle time by 40%");
				expect(basePanel).toHaveTextContent("Implemented SAFe framework");
			});
		});

		it("shows bullets in variant order in right panel", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				const variantPanel = screen.getByTestId(VARIANT_PANEL_TESTID);
				// Variant order: b-3, b-1, b-2
				expect(variantPanel).toHaveTextContent("Implemented SAFe framework");
				expect(variantPanel).toHaveTextContent("Led team of 12 engineers");
			});
		});

		it("shows move indicator for reordered bullets", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				// b-3 moved from position 3 to position 1
				expect(screen.getByText(/from #3/)).toBeInTheDocument();
			});
		});
	});

	describe("approve action", () => {
		it("calls POST /approve and shows success toast", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: APPROVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: APPROVE_LABEL }));
			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/job-variants/${VARIANT_ID}/approve`,
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Variant approved.",
			);
		});

		it("shows error toast on approval failure", async () => {
			setupMockApi();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Failed", 500),
			);
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: APPROVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: APPROVE_LABEL }));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to approve variant.",
				);
			});
		});

		it("navigates back to resume page after successful approval", async () => {
			setupMockApi();
			mocks.mockApiPost.mockResolvedValueOnce({
				data: makeVariant({ status: "Approved" }),
			});
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: APPROVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: APPROVE_LABEL }));
			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith(
					`/resumes/${BASE_RESUME_ID}`,
				);
			});
		});
	});

	describe("archive action", () => {
		it("opens confirmation dialog, then calls DELETE and shows success toast", async () => {
			setupMockApi();
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: ARCHIVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: ARCHIVE_LABEL }));
			await waitFor(() => {
				expect(screen.getByText("Archive Variant")).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("button", { name: CONFIRM_ARCHIVE_LABEL }),
			);
			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/job-variants/${VARIANT_ID}`,
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Variant archived.",
			);
		});

		it("navigates back to resume page after successful archive", async () => {
			setupMockApi();
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: ARCHIVE_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: ARCHIVE_LABEL }));
			await waitFor(() => {
				expect(screen.getByText("Archive Variant")).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("button", { name: CONFIRM_ARCHIVE_LABEL }),
			);
			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith(
					`/resumes/${BASE_RESUME_ID}`,
				);
			});
		});
	});

	describe("regenerate button", () => {
		it("renders a regenerate button", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: REGENERATE_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("is disabled when no guardrail violations present", async () => {
			setupMockApi();
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: REGENERATE_LABEL }),
				).toBeDisabled();
			});
		});

		it("is enabled when error-severity guardrail violations exist", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_ERROR }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: REGENERATE_LABEL }),
				).toBeEnabled();
			});
		});
	});

	describe("agent reasoning (§8.7)", () => {
		it("shows reasoning section when agent_reasoning is present", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ agent_reasoning: MOCK_REASONING }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(REASONING_TESTID)).toBeInTheDocument();
			});
		});

		it("hides reasoning section when agent_reasoning is null", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ agent_reasoning: null }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(VARIANT_REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(REASONING_TESTID)).not.toBeInTheDocument();
		});

		it("displays reasoning text content", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ agent_reasoning: MOCK_REASONING }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(REASONING_TESTID)).toHaveTextContent(
					"Added emphasis",
				);
			});
		});

		it("is collapsible via toggle button with aria-expanded", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ agent_reasoning: MOCK_REASONING }),
				},
			});
			const user = userEvent.setup();
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(REASONING_TESTID)).toBeInTheDocument();
			});

			const toggle = screen.getByTestId(REASONING_TOGGLE_TESTID);

			// Initially expanded
			expect(screen.getByText(/Added emphasis/)).toBeInTheDocument();
			expect(toggle).toHaveAttribute("aria-expanded", "true");

			// Click toggle to collapse
			await user.click(toggle);

			// Content hidden, aria-expanded false
			expect(screen.queryByText(/Added emphasis/)).not.toBeInTheDocument();
			expect(toggle).toHaveAttribute("aria-expanded", "false");

			// Click toggle to expand again
			await user.click(toggle);

			// Content visible, aria-expanded true
			expect(screen.getByText(/Added emphasis/)).toBeInTheDocument();
			expect(toggle).toHaveAttribute("aria-expanded", "true");
		});
	});

	describe("guardrail violations (§8.7)", () => {
		it("shows violation banner when guardrail_result has error violations", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_ERROR }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(GUARDRAIL_BANNER_TESTID)).toBeInTheDocument();
			});
		});

		it("hides violation banner when guardrail_result is null", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: null }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(VARIANT_REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(GUARDRAIL_BANNER_TESTID),
			).not.toBeInTheDocument();
		});

		it("hides violation banner when guardrail_result passed with no violations", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_PASSED }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(VARIANT_REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(GUARDRAIL_BANNER_TESTID),
			).not.toBeInTheDocument();
		});

		it("shows warning banner even when guardrail_result passed", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_WARNING }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(screen.getByTestId(GUARDRAIL_BANNER_TESTID)).toBeInTheDocument();
			});
		});

		it("displays each violation message", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_MIXED }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				const banner = screen.getByTestId(GUARDRAIL_BANNER_TESTID);
				expect(banner).toHaveTextContent(
					'Summary mentions skills not in your profile: "Go", "Rust"',
				);
				expect(banner).toHaveTextContent(
					"Summary length changed by more than 20%.",
				);
			});
		});

		it("disables Approve button when error-severity violations exist", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_ERROR }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: APPROVE_LABEL }),
				).toBeDisabled();
			});
		});

		it("keeps Approve button enabled when only warnings present", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_WARNING }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: APPROVE_LABEL }),
				).toBeEnabled();
			});
		});

		it("shows 'Go to Persona' link navigating to persona page", async () => {
			setupMockApi({
				variant: {
					data: makeVariant({ guardrail_result: MOCK_GUARDRAIL_ERROR }),
				},
			});
			renderVariantReview();
			await waitFor(() => {
				const link = screen.getByTestId(GO_TO_PERSONA_TESTID);
				expect(link).toHaveAttribute("href", `/persona`);
			});
		});
	});

	describe("hideActions mode", () => {
		it("hides header and action buttons when hideActions is true", async () => {
			setupMockApi();
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<VariantReview
						baseResumeId={BASE_RESUME_ID}
						variantId={VARIANT_ID}
						personaId={PERSONA_ID}
						hideActions
					/>
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.getByTestId(VARIANT_REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(BACK_LINK_TESTID)).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: APPROVE_LABEL }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: ARCHIVE_LABEL }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: REGENERATE_LABEL }),
			).not.toBeInTheDocument();
		});

		it("still shows diff panels when hideActions is true", async () => {
			setupMockApi();
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<VariantReview
						baseResumeId={BASE_RESUME_ID}
						variantId={VARIANT_ID}
						personaId={PERSONA_ID}
						hideActions
					/>
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.getByTestId(BASE_PANEL_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(VARIANT_PANEL_TESTID)).toBeInTheDocument();
		});
	});
});
