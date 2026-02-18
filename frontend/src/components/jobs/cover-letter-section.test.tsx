/**
 * Tests for the CoverLetterSection component.
 *
 * REQ-012 §10.1, §15.9: Cover letter section on job detail page —
 * shows status badge (None/Draft/Approved), embeds CoverLetterReview
 * when draft exists, shows download link when approved.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CoverLetterSection } from "./cover-letter-section";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "cover-letter-section";
const LOADING_TESTID = "cover-letter-section-loading";
const NONE_PROMPT_TESTID = "cover-letter-none-prompt";
const DOWNLOAD_TESTID = "cover-letter-section-download";
const REVIEW_TESTID = "cover-letter-review";

const MOCK_JOB_ID = "job-1";
const MOCK_COVER_LETTER_ID = "cl-1";
const MOCK_PERSONA_ID = "p-1";
const MOCK_CREATED_AT = "2026-02-10T12:00:00Z";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: vi.fn(),
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeMeta(total: number) {
	return { total, page: 1, per_page: 20 };
}

const COVER_LETTERS_EMPTY = {
	data: [],
	meta: makeMeta(0),
};

const COVER_LETTERS_WITH_DRAFT = {
	data: [makeCoverLetter({ status: "Draft" })],
	meta: makeMeta(1),
};

const COVER_LETTERS_WITH_APPROVED = {
	data: [
		makeCoverLetter({
			status: "Approved",
			final_text: "Dear Hiring Manager...",
			approved_at: MOCK_CREATED_AT,
		}),
	],
	meta: makeMeta(1),
};

const COVER_LETTERS_ONLY_ARCHIVED = {
	data: [makeCoverLetter({ status: "Archived", archived_at: MOCK_CREATED_AT })],
	meta: makeMeta(1),
};

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

/**
 * Route mockApiGet responses. The component queries:
 * 1. /cover-letters?job_posting_id=... (list, unfiltered by status)
 *
 * When a Draft cover letter is found, CoverLetterReview is embedded
 * which makes additional queries (cover letter detail, job posting, etc.)
 * — we stub those as well.
 */
function setupApiGet(coverLetters = COVER_LETTERS_WITH_DRAFT) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === "/cover-letters") return Promise.resolve(coverLetters);
		// CoverLetterReview sub-queries when draft is embedded
		if (path.startsWith("/cover-letters/"))
			return Promise.resolve({ data: coverLetters.data[0] });
		if (path.startsWith("/job-postings/"))
			return Promise.resolve({
				data: {
					id: MOCK_JOB_ID,
					job_title: "Senior Engineer",
					company_name: "Acme Corp",
				},
			});
		if (path.includes("/achievement-stories"))
			return Promise.resolve({ data: [], meta: { total: 0 } });
		if (path.includes("/skills"))
			return Promise.resolve({ data: [], meta: { total: 0 } });
		if (path.includes("/voice-profile"))
			return Promise.resolve({ data: { tone: "Direct, confident" } });
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

describe("CoverLetterSection", () => {
	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	it("shows loading spinner while query is fetching", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// None state — no cover letter exists
	// -----------------------------------------------------------------------

	describe("no cover letter", () => {
		beforeEach(() => {
			setupApiGet(COVER_LETTERS_EMPTY);
		});

		it("renders the section card", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
		});

		it("shows 'Cover Letter' title", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByText("Cover Letter")).toBeInTheDocument();
			});
		});

		it("shows 'None' status badge", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			const badge = screen.getByLabelText("Status: None");
			expect(badge).toBeInTheDocument();
		});

		it("shows draft materials prompt", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(NONE_PROMPT_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(NONE_PROMPT_TESTID)).toHaveTextContent(
				/draft materials/i,
			);
		});

		it("does not render CoverLetterReview", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(REVIEW_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Only archived cover letters — treat as "none"
	// -----------------------------------------------------------------------

	describe("only archived cover letters", () => {
		beforeEach(() => {
			setupApiGet(COVER_LETTERS_ONLY_ARCHIVED);
		});

		it("treats archived-only as 'None' state", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(NONE_PROMPT_TESTID)).toBeInTheDocument();
			});
			const badge = screen.getByLabelText("Status: None");
			expect(badge).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Draft state — embed CoverLetterReview inline
	// -----------------------------------------------------------------------

	describe("draft cover letter", () => {
		beforeEach(() => {
			setupApiGet(COVER_LETTERS_WITH_DRAFT);
		});

		it("shows 'Draft' status badge", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			const badge = screen.getByLabelText("Status: Draft");
			expect(badge).toBeInTheDocument();
		});

		it("embeds CoverLetterReview component inline", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
		});

		it("does not show draft materials prompt", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			// Wait for queries to settle
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(NONE_PROMPT_TESTID)).not.toBeInTheDocument();
		});

		it("does not show download link", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(DOWNLOAD_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Approved state — show download link
	// -----------------------------------------------------------------------

	describe("approved cover letter", () => {
		beforeEach(() => {
			setupApiGet(COVER_LETTERS_WITH_APPROVED);
		});

		it("shows 'Approved' status badge", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			const badge = screen.getByLabelText("Status: Approved");
			expect(badge).toBeInTheDocument();
		});

		it("shows download PDF link", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(DOWNLOAD_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(DOWNLOAD_TESTID);
			expect(link).toHaveAttribute(
				"href",
				`http://localhost:8000/api/v1/submitted-cover-letter-pdfs/${MOCK_COVER_LETTER_ID}/download`,
			);
			expect(link).toHaveAttribute("target", "_blank");
			expect(link).toHaveAttribute("rel", "noopener noreferrer");
		});

		it("does not render inline CoverLetterReview", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
			await waitFor(() => {
				expect(screen.getByTestId(DOWNLOAD_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(REVIEW_TESTID)).not.toBeInTheDocument();
		});

		it("does not show draft materials prompt", async () => {
			render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(DOWNLOAD_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(NONE_PROMPT_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Query parameters
	// -----------------------------------------------------------------------

	it("passes job_posting_id to cover letter query", async () => {
		render(<CoverLetterSection jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/cover-letters", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});
});
