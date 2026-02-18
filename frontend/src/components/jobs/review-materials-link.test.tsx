/**
 * Tests for the ReviewMaterialsLink component.
 *
 * REQ-012 §10.7, §15.8: Shows "Review Materials" link on job detail page
 * when both a non-archived variant and cover letter exist for the job,
 * linking to the unified ghostwriter review at /jobs/[id]/review.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewMaterialsLink } from "./review-materials-link";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARD_TESTID = "review-materials-link";
const LOADING_TESTID = "review-materials-loading";
const LINK_TESTID = "review-materials-anchor";

const MOCK_JOB_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const MOCK_VARIANT_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901";
const MOCK_COVER_LETTER_ID = "c3d4e5f6-a7b8-9012-cdef-123456789012";
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
		base_resume_id: "base-resume-1",
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
		persona_id: "p-1",
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
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: vi.fn(),
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VARIANTS_EMPTY = { data: [], meta: makeMeta(0) };
const COVER_LETTERS_EMPTY = { data: [], meta: makeMeta(0) };

const VARIANTS_WITH_DRAFT = {
	data: [makeVariant({ status: "Draft" })],
	meta: makeMeta(1),
};

const VARIANTS_WITH_APPROVED = {
	data: [makeVariant({ status: "Approved" })],
	meta: makeMeta(1),
};

const COVER_LETTERS_WITH_DRAFT = {
	data: [makeCoverLetter({ status: "Draft" })],
	meta: makeMeta(1),
};

const COVER_LETTERS_WITH_APPROVED = {
	data: [makeCoverLetter({ status: "Approved" })],
	meta: makeMeta(1),
};

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
	const variants = options?.variants ?? VARIANTS_EMPTY;
	const coverLetters = options?.coverLetters ?? COVER_LETTERS_EMPTY;

	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === "/variants") return Promise.resolve(variants);
		if (path === "/cover-letters") return Promise.resolve(coverLetters);
		return Promise.reject(new Error(`Unexpected GET: ${path}`));
	});
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
	setupApiGet();
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReviewMaterialsLink", () => {
	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	it("shows loading spinner while queries are fetching", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// UUID validation
	// -----------------------------------------------------------------------

	it("renders nothing when jobId is not a valid UUID", () => {
		const { container } = render(<ReviewMaterialsLink jobId="not-a-uuid" />, {
			wrapper: createWrapper(),
		});
		expect(container.innerHTML).toBe("");
	});

	it("does not query API when jobId is invalid", () => {
		mocks.mockApiGet.mockClear();
		render(<ReviewMaterialsLink jobId="not-a-uuid" />, {
			wrapper: createWrapper(),
		});
		expect(mocks.mockApiGet).not.toHaveBeenCalled();
	});

	// -----------------------------------------------------------------------
	// Hidden states
	// -----------------------------------------------------------------------

	describe("hidden when materials are incomplete", () => {
		it("renders nothing when no materials exist", async () => {
			setupApiGet();
			const { container } = render(
				<ReviewMaterialsLink jobId={MOCK_JOB_ID} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when only variant exists (no cover letter)", async () => {
			setupApiGet({ variants: VARIANTS_WITH_DRAFT });
			const { container } = render(
				<ReviewMaterialsLink jobId={MOCK_JOB_ID} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when only cover letter exists (no variant)", async () => {
			setupApiGet({ coverLetters: COVER_LETTERS_WITH_DRAFT });
			const { container } = render(
				<ReviewMaterialsLink jobId={MOCK_JOB_ID} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when both are Approved (review complete)", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_APPROVED,
				coverLetters: COVER_LETTERS_WITH_APPROVED,
			});
			const { container } = render(
				<ReviewMaterialsLink jobId={MOCK_JOB_ID} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when only archived materials exist", async () => {
			setupApiGet({
				variants: VARIANTS_ONLY_ARCHIVED,
				coverLetters: COVER_LETTERS_ONLY_ARCHIVED,
			});
			const { container } = render(
				<ReviewMaterialsLink jobId={MOCK_JOB_ID} />,
				{ wrapper: createWrapper() },
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});
	});

	// -----------------------------------------------------------------------
	// Visible states
	// -----------------------------------------------------------------------

	describe("shown when materials need review", () => {
		it("shows link when both Draft variant and Draft cover letter exist", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_DRAFT,
				coverLetters: COVER_LETTERS_WITH_DRAFT,
			});
			render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
		});

		it("shows link when variant is Approved and cover letter is Draft", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_APPROVED,
				coverLetters: COVER_LETTERS_WITH_DRAFT,
			});
			render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
		});

		it("shows link when variant is Draft and cover letter is Approved", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_DRAFT,
				coverLetters: COVER_LETTERS_WITH_APPROVED,
			});
			render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
		});

		it("link has correct href to review page", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_DRAFT,
				coverLetters: COVER_LETTERS_WITH_DRAFT,
			});
			render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(LINK_TESTID)).toHaveAttribute(
					"href",
					`/jobs/${MOCK_JOB_ID}/review`,
				);
			});
		});

		it("link text contains 'Review Materials'", async () => {
			setupApiGet({
				variants: VARIANTS_WITH_DRAFT,
				coverLetters: COVER_LETTERS_WITH_DRAFT,
			});
			render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(LINK_TESTID)).toHaveTextContent(
					/review materials/i,
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Query parameters
	// -----------------------------------------------------------------------

	it("passes job_posting_id to variant query", async () => {
		setupApiGet({
			variants: VARIANTS_WITH_DRAFT,
			coverLetters: COVER_LETTERS_WITH_DRAFT,
		});
		render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/variants", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});

	it("passes job_posting_id to cover letter query", async () => {
		setupApiGet({
			variants: VARIANTS_WITH_DRAFT,
			coverLetters: COVER_LETTERS_WITH_DRAFT,
		});
		render(<ReviewMaterialsLink jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/cover-letters", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});
});
