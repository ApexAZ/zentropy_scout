/**
 * Tests for the MarkAsAppliedCard component (§10.4).
 *
 * REQ-012 §11.4: "Mark as Applied" flow — download materials,
 * apply externally, confirm application creation.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MarkAsAppliedCard } from "./mark-as-applied-card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARD_TESTID = "mark-as-applied-card";
const LOADING_TESTID = "mark-as-applied-loading";
const ALREADY_APPLIED_TESTID = "already-applied-notice";
const RESUME_DOWNLOAD_TESTID = "resume-download-link";
const COVER_LETTER_DOWNLOAD_TESTID = "cover-letter-download-link";
const APPLY_EXTERNAL_TESTID = "apply-external-link";
const CONFIRM_BUTTON_TESTID = "confirm-applied-button";

const MOCK_JOB_ID = "job-1";
const MOCK_VARIANT_ID = "variant-1";
const MOCK_BASE_RESUME_ID = "base-resume-1";
const MOCK_COVER_LETTER_ID = "cl-1";
const MOCK_APP_ID = "app-1";
const MOCK_APPLY_URL = "https://example.com/apply";
const MOCK_CREATED_AT = "2026-02-10T12:00:00Z";
const MOCK_APPLIED_AT = "2026-02-12T10:00:00Z";

const SUCCESS_MESSAGE = "Application created!";
const ERROR_MESSAGE = "Failed to create application.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeVariant(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_VARIANT_ID,
		base_resume_id: MOCK_BASE_RESUME_ID,
		job_posting_id: MOCK_JOB_ID,
		summary: "Tailored summary",
		job_bullet_order: {},
		modifications_description: null,
		status: "Approved",
		snapshot_included_jobs: [],
		snapshot_job_bullet_selections: {},
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		agent_reasoning: null,
		guardrail_result: null,
		approved_at: MOCK_CREATED_AT,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
		...overrides,
	};
}

function makeCoverLetter(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_COVER_LETTER_ID,
		persona_id: "p-1",
		job_posting_id: MOCK_JOB_ID,
		application_id: null,
		achievement_stories_used: [],
		agent_reasoning: null,
		draft_text: "Dear Hiring Manager...",
		final_text: "Dear Hiring Manager...",
		status: "Approved",
		validation_result: null,
		approved_at: MOCK_CREATED_AT,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
		...overrides,
	};
}

function makeApplication(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_APP_ID,
		persona_id: "p-1",
		job_posting_id: MOCK_JOB_ID,
		job_variant_id: MOCK_VARIANT_ID,
		cover_letter_id: MOCK_COVER_LETTER_ID,
		submitted_resume_pdf_id: null,
		submitted_cover_letter_pdf_id: null,
		job_snapshot: {
			title: "Senior Engineer",
			company_name: "Acme Corp",
			captured_at: MOCK_CREATED_AT,
			source_url: null,
		},
		status: "Applied",
		current_interview_stage: null,
		offer_details: null,
		rejection_details: null,
		notes: null,
		is_pinned: false,
		applied_at: MOCK_APPLIED_AT,
		status_updated_at: MOCK_APPLIED_AT,
		created_at: MOCK_APPLIED_AT,
		updated_at: MOCK_APPLIED_AT,
		archived_at: null,
		...overrides,
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
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({
		push: mocks.mockPush,
	}),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Variants list response: one approved variant. */
const VARIANTS_WITH_APPROVED = {
	data: [makeVariant()],
	meta: { total: 1, page: 1, per_page: 20 },
};

/** Variants list response: empty (no approved variant). */
const VARIANTS_EMPTY = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
};

/** Cover letters list response: one approved cover letter. */
const COVER_LETTERS_WITH_APPROVED = {
	data: [makeCoverLetter()],
	meta: { total: 1, page: 1, per_page: 20 },
};

/** Cover letters list response: empty (no approved cover letter). */
const COVER_LETTERS_EMPTY = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
};

/** Applications list response: one existing application. */
const APPLICATIONS_WITH_EXISTING = {
	data: [makeApplication()],
	meta: { total: 1, page: 1, per_page: 20 },
};

/** Applications list response: no existing applications. */
const APPLICATIONS_EMPTY = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
};

/** Successful application creation response. */
const APPLICATION_CREATED = {
	data: makeApplication(),
};

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

/**
 * Route mockApiGet responses based on the requested path.
 *
 * The component makes three GET queries:
 * 1. /variants?job_posting_id=...&status=Approved
 * 2. /cover-letters?job_posting_id=...&status=Approved
 * 3. /applications?job_posting_id=...
 */
interface ApiListFixture {
	data: Record<string, unknown>[];
	meta: { total: number; page: number; per_page: number };
}

function setupApiGet(options?: {
	variants?: ApiListFixture;
	coverLetters?: ApiListFixture;
	applications?: ApiListFixture;
}) {
	const variants = options?.variants ?? VARIANTS_WITH_APPROVED;
	const coverLetters = options?.coverLetters ?? COVER_LETTERS_WITH_APPROVED;
	const applications = options?.applications ?? APPLICATIONS_EMPTY;

	mocks.mockApiGet.mockImplementation(
		(path: string, _params?: Record<string, unknown>) => {
			if (path === "/variants") return Promise.resolve(variants);
			if (path === "/cover-letters") return Promise.resolve(coverLetters);
			if (path === "/applications") return Promise.resolve(applications);
			return Promise.reject(new Error(`Unexpected GET: ${path}`));
		},
	);
}

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	// Override invalidateQueries to track calls
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	}
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
}

beforeEach(() => {
	setupApiGet();
	mocks.mockApiPost.mockResolvedValue(APPLICATION_CREATED);
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MarkAsAppliedCard", () => {
	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	it("shows loading spinner while queries are fetching", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		render(
			<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
			{ wrapper: createWrapper() },
		);
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Hidden when no approved materials
	// -----------------------------------------------------------------------

	it("renders nothing when no approved variant exists", async () => {
		setupApiGet({ variants: VARIANTS_EMPTY });
		const { container } = render(
			<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
			{ wrapper: createWrapper() },
		);
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalled();
		});
		// Let queries settle
		await waitFor(() => {
			expect(screen.queryByTestId(CARD_TESTID)).not.toBeInTheDocument();
		});
		expect(container.innerHTML).toBe("");
	});

	// -----------------------------------------------------------------------
	// Already applied state
	// -----------------------------------------------------------------------

	describe("already applied", () => {
		it("shows 'Already applied' notice when application exists", async () => {
			setupApiGet({ applications: APPLICATIONS_WITH_EXISTING });
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(ALREADY_APPLIED_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(ALREADY_APPLIED_TESTID)).toHaveTextContent(
				"Already applied",
			);
		});

		it("shows link to existing application", async () => {
			setupApiGet({ applications: APPLICATIONS_WITH_EXISTING });
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(ALREADY_APPLIED_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByRole("link", { name: /view application/i });
			expect(link).toHaveAttribute("href", `/applications/${MOCK_APP_ID}`);
		});
	});

	// -----------------------------------------------------------------------
	// Card rendering — Ready to Apply
	// -----------------------------------------------------------------------

	describe("ready to apply card", () => {
		it("shows 'Ready to Apply' title", async () => {
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("Ready to Apply")).toBeInTheDocument();
		});

		it("shows resume download link pointing to base resume PDF", async () => {
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(RESUME_DOWNLOAD_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(RESUME_DOWNLOAD_TESTID);
			expect(link).toHaveAttribute(
				"href",
				`http://localhost:8000/api/v1/base-resumes/${MOCK_BASE_RESUME_ID}/download`,
			);
			expect(link).toHaveAttribute("target", "_blank");
			expect(link).toHaveAttribute("rel", "noopener noreferrer");
		});

		it("shows cover letter download link when approved cover letter exists", async () => {
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(
					screen.getByTestId(COVER_LETTER_DOWNLOAD_TESTID),
				).toBeInTheDocument();
			});
			const link = screen.getByTestId(COVER_LETTER_DOWNLOAD_TESTID);
			expect(link).toHaveAttribute(
				"href",
				`http://localhost:8000/api/v1/cover-letters/${MOCK_COVER_LETTER_ID}/download`,
			);
			expect(link).toHaveAttribute("target", "_blank");
			expect(link).toHaveAttribute("rel", "noopener noreferrer");
		});

		it("hides cover letter download when no approved cover letter", async () => {
			setupApiGet({ coverLetters: COVER_LETTERS_EMPTY });
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(COVER_LETTER_DOWNLOAD_TESTID),
			).not.toBeInTheDocument();
		});

		it("shows external apply link with hostname", async () => {
			render(
				<MarkAsAppliedCard
					jobId={MOCK_JOB_ID}
					applyUrl="https://linkedin.com/jobs/apply/123"
				/>,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(APPLY_EXTERNAL_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(APPLY_EXTERNAL_TESTID);
			expect(link).toHaveAttribute(
				"href",
				"https://linkedin.com/jobs/apply/123",
			);
			expect(link).toHaveAttribute("target", "_blank");
			expect(link).toHaveAttribute("rel", "noopener noreferrer");
			expect(link).toHaveTextContent("linkedin.com");
		});

		it("hides external apply link when applyUrl is null", async () => {
			render(<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={null} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(APPLY_EXTERNAL_TESTID),
			).not.toBeInTheDocument();
		});

		it("suppresses apply link with javascript: scheme", async () => {
			render(
				<MarkAsAppliedCard
					jobId={MOCK_JOB_ID}
					applyUrl="javascript:alert(1)"
				/>,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(APPLY_EXTERNAL_TESTID),
			).not.toBeInTheDocument();
		});

		it("suppresses apply link with data: scheme", async () => {
			render(
				<MarkAsAppliedCard
					jobId={MOCK_JOB_ID}
					applyUrl="data:text/html,<script>alert(1)</script>"
				/>,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(APPLY_EXTERNAL_TESTID),
			).not.toBeInTheDocument();
		});

		it("shows 'I've Applied' confirm button", async () => {
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toHaveTextContent(
				"I've Applied",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Confirm application creation
	// -----------------------------------------------------------------------

	describe("confirm application", () => {
		it("calls POST /applications with correct body on confirm", async () => {
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/applications", {
					job_posting_id: MOCK_JOB_ID,
					job_variant_id: MOCK_VARIANT_ID,
					cover_letter_id: MOCK_COVER_LETTER_ID,
				});
			});
		});

		it("sends null cover_letter_id when no cover letter", async () => {
			setupApiGet({ coverLetters: COVER_LETTERS_EMPTY });
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/applications", {
					job_posting_id: MOCK_JOB_ID,
					job_variant_id: MOCK_VARIANT_ID,
					cover_letter_id: null,
				});
			});
		});

		it("shows success toast after creating application", async () => {
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					SUCCESS_MESSAGE,
				);
			});
		});

		it("navigates to new application after creation", async () => {
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
				);
			});
		});

		it("invalidates queries after successful creation", async () => {
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});

		it("shows error toast on creation failure", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(ERROR_MESSAGE);
			});
		});

		it("disables button while submitting", async () => {
			// Make POST hang to test loading state
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			const user = userEvent.setup();
			render(
				<MarkAsAppliedCard jobId={MOCK_JOB_ID} applyUrl={MOCK_APPLY_URL} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));
			await waitFor(() => {
				expect(screen.getByTestId(CONFIRM_BUTTON_TESTID)).toBeDisabled();
			});
		});
	});
});
