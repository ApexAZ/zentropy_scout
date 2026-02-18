/**
 * Tests for the DraftMaterialsCard component.
 *
 * REQ-012 §8.3, §15.7: "Draft Materials" button on job detail page —
 * sends chat message to trigger ghostwriter agent, shows pending state
 * while generating, hidden when materials already exist.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DraftMaterialsCard } from "./draft-materials-card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CARD_TESTID = "draft-materials-card";
const LOADING_TESTID = "draft-materials-loading";
const BUTTON_TESTID = "draft-materials-button";

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
		mockSendMessage: vi.fn().mockResolvedValue(undefined),
		mockIsStreaming: false,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: vi.fn(),
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/chat-provider", () => ({
	useChat: () => ({
		sendMessage: mocks.mockSendMessage,
		isStreaming: mocks.mockIsStreaming,
		messages: [],
		isLoadingHistory: false,
		addSystemMessage: vi.fn(),
		clearMessages: vi.fn(),
		loadHistory: vi.fn(),
	}),
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VARIANTS_EMPTY = {
	data: [],
	meta: makeMeta(0),
};

const VARIANTS_WITH_DRAFT = {
	data: [makeVariant({ status: "Draft" })],
	meta: makeMeta(1),
};

const VARIANTS_WITH_APPROVED = {
	data: [makeVariant({ status: "Approved" })],
	meta: makeMeta(1),
};

const VARIANTS_ONLY_ARCHIVED = {
	data: [makeVariant({ status: "Archived", archived_at: MOCK_CREATED_AT })],
	meta: makeMeta(1),
};

const COVER_LETTERS_EMPTY = {
	data: [],
	meta: makeMeta(0),
};

const COVER_LETTERS_WITH_DRAFT = {
	data: [makeCoverLetter({ status: "Draft" })],
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
 * 1. /variants?job_posting_id=... (all statuses)
 * 2. /cover-letters?job_posting_id=... (all statuses)
 */
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
	mocks.mockIsStreaming = false;
	mocks.mockSendMessage.mockResolvedValue(undefined);
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DraftMaterialsCard", () => {
	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	it("shows loading spinner while queries are fetching", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Hidden when materials exist
	// -----------------------------------------------------------------------

	describe("hidden when materials exist", () => {
		it("renders nothing when a draft variant exists", async () => {
			setupApiGet({ variants: VARIANTS_WITH_DRAFT });
			const { container } = render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalled();
			});
			await waitFor(() => {
				expect(screen.queryByTestId(CARD_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when an approved variant exists", async () => {
			setupApiGet({ variants: VARIANTS_WITH_APPROVED });
			const { container } = render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("renders nothing when a draft cover letter exists", async () => {
			setupApiGet({ coverLetters: COVER_LETTERS_WITH_DRAFT });
			const { container } = render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});
			expect(container.innerHTML).toBe("");
		});

		it("shows card when only archived materials exist", async () => {
			setupApiGet({
				variants: VARIANTS_ONLY_ARCHIVED,
				coverLetters: COVER_LETTERS_ONLY_ARCHIVED,
			});
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Card rendering — no materials
	// -----------------------------------------------------------------------

	describe("no materials state", () => {
		it("shows the card with Draft Materials button", async () => {
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			expect(screen.getByTestId(BUTTON_TESTID)).toHaveTextContent(
				"Draft Materials",
			);
		});

		it("shows description text about generating materials", async () => {
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(CARD_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText(/tailored resume/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Button click — sends chat message
	// -----------------------------------------------------------------------

	describe("draft button click", () => {
		it("sends chat message with job ID when clicked", async () => {
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockSendMessage).toHaveBeenCalledWith(
					expect.stringContaining(MOCK_JOB_ID),
				);
			});
		});

		it("sends message matching ghostwriter trigger pattern", async () => {
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockSendMessage).toHaveBeenCalledWith(
					expect.stringMatching(/draft materials/i),
				);
			});
		});

		it("shows info toast after sending message", async () => {
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockShowToast.info).toHaveBeenCalledWith(
					expect.stringContaining("chat"),
				);
			});
		});

		it("disables button while drafting", async () => {
			mocks.mockSendMessage.mockReturnValue(new Promise(() => {}));
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeDisabled();
			});
		});

		it("shows error toast when sendMessage fails", async () => {
			mocks.mockSendMessage.mockRejectedValue(new Error("Network error"));
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					expect.stringContaining("Failed"),
				);
			});
		});

		it("re-enables button after sendMessage error", async () => {
			mocks.mockSendMessage.mockRejectedValue(new Error("Network error"));
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(BUTTON_TESTID));
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).not.toBeDisabled();
			});
		});

		it("does not send message when jobId is not a valid UUID", async () => {
			const user = userEvent.setup();
			render(<DraftMaterialsCard jobId="not-a-uuid" />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			mocks.mockSendMessage.mockClear();
			await user.click(screen.getByTestId(BUTTON_TESTID));
			expect(mocks.mockSendMessage).not.toHaveBeenCalled();
		});

		it("disables button when chat is already streaming", async () => {
			mocks.mockIsStreaming = true;
			render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
				wrapper: createWrapper(),
			});
			await waitFor(() => {
				expect(screen.getByTestId(BUTTON_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(BUTTON_TESTID)).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Query parameters
	// -----------------------------------------------------------------------

	it("passes job_posting_id to variant query", async () => {
		render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/variants", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});

	it("passes job_posting_id to cover letter query", async () => {
		render(<DraftMaterialsCard jobId={MOCK_JOB_ID} />, {
			wrapper: createWrapper(),
		});
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/cover-letters", {
				job_posting_id: MOCK_JOB_ID,
			});
		});
	});
});
