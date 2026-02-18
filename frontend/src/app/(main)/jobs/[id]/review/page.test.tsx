/**
 * Tests for the GhostwriterReviewPage route component.
 *
 * REQ-012 §10.7, §15.8: Route /jobs/[id]/review — resolves variant
 * and cover letter for a job, renders unified GhostwriterReview.
 * Guard clause: only renders for onboarded users.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import GhostwriterReviewPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOADING_TESTID = "review-page-loading";
const NO_MATERIALS_TESTID = "review-page-no-materials";
const GHOSTWRITER_REVIEW_TESTID = "ghostwriter-review";

const MOCK_JOB_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const MOCK_VARIANT_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901";
const MOCK_COVER_LETTER_ID = "c3d4e5f6-a7b8-9012-cdef-123456789012";
const MOCK_BASE_RESUME_ID = "d4e5f6a7-b8c9-0123-defa-234567890123";
const MOCK_PERSONA_ID = "e5f6a7b8-c9d0-1234-efab-345678901234";
const MOCK_CREATED_AT = "2026-02-10T12:00:00Z";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMeta(total: number) {
	return { total, page: 1, per_page: 20 };
}

function makeVariant(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_VARIANT_ID,
		base_resume_id: MOCK_BASE_RESUME_ID,
		job_posting_id: MOCK_JOB_ID,
		summary: "Tailored summary",
		job_bullet_order: {},
		modifications_description: null,
		status: "Draft",
		snapshot_included_jobs: [],
		snapshot_job_bullet_selections: {},
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		agent_reasoning: null,
		guardrail_result: null,
		approved_at: null,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
		...overrides,
	};
}

function makeCoverLetter(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_COVER_LETTER_ID,
		persona_id: MOCK_PERSONA_ID,
		job_posting_id: MOCK_JOB_ID,
		application_id: null,
		achievement_stories_used: [],
		agent_reasoning: null,
		draft_text: "Dear Hiring Manager...",
		final_text: null,
		status: "Draft",
		validation_result: null,
		approved_at: null,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
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
		MockApiError,
		mockUsePersonaStatus: vi.fn(),
		mockUseParams: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: vi.fn(),
	apiPatch: vi.fn(),
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("next/navigation", () => ({
	useParams: mocks.mockUseParams,
}));

vi.mock("@/components/ghostwriter/ghostwriter-review", () => ({
	GhostwriterReview: ({
		variantId,
		coverLetterId,
		baseResumeId,
		personaId,
	}: {
		variantId: string;
		coverLetterId: string;
		baseResumeId: string;
		personaId: string;
	}) => (
		<div
			data-testid={GHOSTWRITER_REVIEW_TESTID}
			data-variant-id={variantId}
			data-cover-letter-id={coverLetterId}
			data-base-resume-id={baseResumeId}
			data-persona-id={personaId}
		>
			Ghostwriter Review
		</div>
	),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VARIANTS_WITH_DRAFT = {
	data: [makeVariant()],
	meta: makeMeta(1),
};

const COVER_LETTERS_WITH_DRAFT = {
	data: [makeCoverLetter()],
	meta: makeMeta(1),
};

const VARIANTS_EMPTY = { data: [], meta: makeMeta(0) };
const COVER_LETTERS_EMPTY = { data: [], meta: makeMeta(0) };

const VARIANTS_ONLY_ARCHIVED = {
	data: [makeVariant({ status: "Archived", archived_at: MOCK_CREATED_AT })],
	meta: makeMeta(1),
};

const COVER_LETTERS_ONLY_ARCHIVED = {
	data: [makeCoverLetter({ status: "Archived", archived_at: MOCK_CREATED_AT })],
	meta: makeMeta(1),
};

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

function setupApiGet(options?: {
	variants?: {
		data: Record<string, unknown>[];
		meta: ReturnType<typeof makeMeta>;
	};
	coverLetters?: {
		data: Record<string, unknown>[];
		meta: ReturnType<typeof makeMeta>;
	};
}) {
	const variants = options?.variants ?? VARIANTS_WITH_DRAFT;
	const coverLetters = options?.coverLetters ?? COVER_LETTERS_WITH_DRAFT;

	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === "/variants") return Promise.resolve(variants);
		if (path === "/cover-letters") return Promise.resolve(coverLetters);
		return Promise.reject(new Error(`Unexpected GET: ${path}`));
	});
}

function setupOnboarded() {
	mocks.mockUsePersonaStatus.mockReturnValue({
		status: "onboarded",
		persona: { id: MOCK_PERSONA_ID },
	});
	mocks.mockUseParams.mockReturnValue({ id: MOCK_JOB_ID });
}

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
	setupOnboarded();
	setupApiGet();
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GhostwriterReviewPage", () => {
	// -----------------------------------------------------------------------
	// Guard clause
	// -----------------------------------------------------------------------

	it("renders nothing when persona status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<GhostwriterReviewPage />, {
			wrapper: createWrapper(),
		});
		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when persona status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<GhostwriterReviewPage />, {
			wrapper: createWrapper(),
		});
		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when job ID is not a valid UUID", () => {
		mocks.mockUseParams.mockReturnValue({ id: "not-a-uuid" });
		const { container } = render(<GhostwriterReviewPage />, {
			wrapper: createWrapper(),
		});
		expect(container.innerHTML).toBe("");
	});

	it("does not query API when job ID is invalid", () => {
		mocks.mockUseParams.mockReturnValue({ id: "not-a-uuid" });
		mocks.mockApiGet.mockClear();
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		expect(mocks.mockApiGet).not.toHaveBeenCalled();
	});

	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	it("shows loading spinner while fetching materials", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Empty / error states
	// -----------------------------------------------------------------------

	it("shows empty state when no variant found for job", async () => {
		setupApiGet({ variants: VARIANTS_EMPTY });
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(NO_MATERIALS_TESTID)).toBeInTheDocument();
		});
	});

	it("shows empty state when no cover letter found for job", async () => {
		setupApiGet({ coverLetters: COVER_LETTERS_EMPTY });
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(NO_MATERIALS_TESTID)).toBeInTheDocument();
		});
	});

	it("shows empty state when only archived materials exist", async () => {
		setupApiGet({
			variants: VARIANTS_ONLY_ARCHIVED,
			coverLetters: COVER_LETTERS_ONLY_ARCHIVED,
		});
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(NO_MATERIALS_TESTID)).toBeInTheDocument();
		});
	});

	it("empty state contains helpful message text", async () => {
		setupApiGet({ variants: VARIANTS_EMPTY });
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByText(/no materials/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Successful render
	// -----------------------------------------------------------------------

	it("renders GhostwriterReview when both materials exist", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(GHOSTWRITER_REVIEW_TESTID)).toBeInTheDocument();
		});
	});

	it("passes correct variantId to GhostwriterReview", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(GHOSTWRITER_REVIEW_TESTID)).toHaveAttribute(
				"data-variant-id",
				MOCK_VARIANT_ID,
			);
		});
	});

	it("passes correct coverLetterId to GhostwriterReview", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(GHOSTWRITER_REVIEW_TESTID)).toHaveAttribute(
				"data-cover-letter-id",
				MOCK_COVER_LETTER_ID,
			);
		});
	});

	it("passes variant's baseResumeId to GhostwriterReview", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(GHOSTWRITER_REVIEW_TESTID)).toHaveAttribute(
				"data-base-resume-id",
				MOCK_BASE_RESUME_ID,
			);
		});
	});

	it("passes personaId to GhostwriterReview", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByTestId(GHOSTWRITER_REVIEW_TESTID)).toHaveAttribute(
				"data-persona-id",
				MOCK_PERSONA_ID,
			);
		});
	});

	// -----------------------------------------------------------------------
	// Query parameters
	// -----------------------------------------------------------------------

	it("passes job_posting_id to variant query", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/variants", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});

	it("passes job_posting_id to cover letter query", async () => {
		render(<GhostwriterReviewPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/cover-letters", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});
});
