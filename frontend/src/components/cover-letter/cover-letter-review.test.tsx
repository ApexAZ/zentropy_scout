/**
 * Tests for the CoverLetterReview component (§9.1).
 *
 * REQ-012 §10.2: Cover letter review with agent reasoning,
 * stories used, editable textarea, and word count indicator.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COVER_LETTER_ID = "cl-1";
const PERSONA_ID = "p-1";
const JOB_POSTING_ID = "jp-1";
const STORY_1_ID = "story-1";
const STORY_2_ID = "story-2";
const SKILL_1_ID = "skill-1";
const SKILL_2_ID = "skill-2";
const SKILL_3_ID = "skill-3";
const LOADING_TESTID = "loading-spinner";
const REVIEW_TESTID = "cover-letter-review";
const REASONING_TESTID = "agent-reasoning";
const REASONING_TOGGLE_TESTID = "agent-reasoning-toggle";
const STORIES_TESTID = "stories-used";
const WORD_COUNT_TESTID = "word-count";

const MOCK_TIMESTAMP = "2024-01-15T10:00:00Z";

const MOCK_DRAFT_TEXT =
	"Dear Hiring Manager,\n\nI'm excited to apply for the Scrum Master role at Acme Corp. In my current role at TechCorp, I recently turned around a failing project by reorganizing sprint cadences and implementing SAFe practices across three teams.";

const MOCK_REASONING =
	'Selected "Turned around failing project" because it demonstrates leadership under pressure, aligning with the job\'s emphasis on "driving results in ambiguity".';

// ---------------------------------------------------------------------------
// Mock data factories
// ---------------------------------------------------------------------------

function makeCoverLetter(overrides?: Record<string, unknown>) {
	return {
		id: COVER_LETTER_ID,
		persona_id: PERSONA_ID,
		application_id: null,
		job_posting_id: JOB_POSTING_ID,
		achievement_stories_used: [STORY_1_ID, STORY_2_ID],
		draft_text: MOCK_DRAFT_TEXT,
		final_text: null,
		status: "Draft",
		agent_reasoning: MOCK_REASONING,
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

function makeAchievementStories() {
	return [
		{
			id: STORY_1_ID,
			persona_id: PERSONA_ID,
			title: "Turned around failing project",
			context: "Project was behind schedule",
			action: "Reorganized sprint cadences",
			outcome: "Delivered on time",
			skills_demonstrated: [SKILL_1_ID, SKILL_2_ID],
			related_job_id: null,
			display_order: 0,
		},
		{
			id: STORY_2_ID,
			persona_id: PERSONA_ID,
			title: "Scaled Agile adoption",
			context: "Organization needed Agile scaling",
			action: "Implemented SAFe",
			outcome: "3 teams onboarded",
			skills_demonstrated: [SKILL_2_ID, SKILL_3_ID],
			related_job_id: null,
			display_order: 1,
		},
	];
}

function makeSkills() {
	return [
		{
			id: SKILL_1_ID,
			persona_id: PERSONA_ID,
			skill_name: "Leadership",
			category: "Soft Skills",
			proficiency_level: "Expert",
			years_experience: 8,
			display_order: 0,
		},
		{
			id: SKILL_2_ID,
			persona_id: PERSONA_ID,
			skill_name: "Agile",
			category: "Methodologies",
			proficiency_level: "Expert",
			years_experience: 6,
			display_order: 1,
		},
		{
			id: SKILL_3_ID,
			persona_id: PERSONA_ID,
			skill_name: "SAFe",
			category: "Methodologies",
			proficiency_level: "Advanced",
			years_experience: 4,
			display_order: 2,
		},
	];
}

const MOCK_COVER_LETTER_RESPONSE = { data: makeCoverLetter() };
const MOCK_JOB_POSTING_RESPONSE = { data: makeJobPosting() };
const MOCK_STORIES_RESPONSE = {
	data: makeAchievementStories(),
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};
const MOCK_SKILLS_RESPONSE = {
	data: makeSkills(),
	meta: { total: 3, page: 1, per_page: 20, total_pages: 1 },
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
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { CoverLetterReview } from "./cover-letter-review";

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

function renderReview(coverLetterId = COVER_LETTER_ID) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<CoverLetterReview coverLetterId={coverLetterId} />
		</Wrapper>,
	);
}

function setupMockApi(overrides?: {
	coverLetter?: unknown;
	jobPosting?: unknown;
	stories?: unknown;
	skills?: unknown;
}) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === `/cover-letters/${COVER_LETTER_ID}`)
			return Promise.resolve(
				overrides?.coverLetter ?? MOCK_COVER_LETTER_RESPONSE,
			);
		if (path === `/job-postings/${JOB_POSTING_ID}`)
			return Promise.resolve(
				overrides?.jobPosting ?? MOCK_JOB_POSTING_RESPONSE,
			);
		if (path.includes("/achievement-stories"))
			return Promise.resolve(overrides?.stories ?? MOCK_STORIES_RESPONSE);
		if (path.includes("/skills"))
			return Promise.resolve(overrides?.skills ?? MOCK_SKILLS_RESPONSE);
		return Promise.reject(new Error(`Unexpected API call: ${path}`));
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
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

describe("CoverLetterReview", () => {
	// Loading / Error
	// -----------------------------------------------------------------------

	it("shows loading spinner while data loads", () => {
		mocks.mockApiGet.mockImplementation(() => new Promise(() => {}));
		renderReview();
		expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
	});

	it("shows FailedState on API error", async () => {
		mocks.mockApiGet.mockRejectedValue(
			new mocks.MockApiError("NOT_FOUND", "Not found", 404),
		);
		renderReview();
		await waitFor(() => {
			expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
		});
	});

	// Header
	// -----------------------------------------------------------------------

	it("renders header with job title and company name", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(
			screen.getByText(/Senior Scrum Master at Acme Corp/),
		).toBeInTheDocument();
	});

	it("renders status badge with Draft status", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByText("Draft")).toBeInTheDocument();
	});

	it("renders status badge with Approved status", async () => {
		setupMockApi({
			coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByText("Approved")).toBeInTheDocument();
	});

	// Agent Reasoning
	// -----------------------------------------------------------------------

	it("renders agent reasoning when present", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REASONING_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByText(MOCK_REASONING)).toBeInTheDocument();
	});

	it("collapses reasoning when toggle clicked", async () => {
		setupMockApi();
		const user = userEvent.setup();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REASONING_TESTID)).toBeInTheDocument();
		});

		// Initially expanded
		expect(screen.getByText(MOCK_REASONING)).toBeInTheDocument();

		// Click toggle to collapse
		await user.click(screen.getByTestId(REASONING_TOGGLE_TESTID));
		expect(screen.queryByText(MOCK_REASONING)).not.toBeInTheDocument();

		// Click again to expand
		await user.click(screen.getByTestId(REASONING_TOGGLE_TESTID));
		expect(screen.getByText(MOCK_REASONING)).toBeInTheDocument();
	});

	it("hides agent reasoning section when null", async () => {
		setupMockApi({
			coverLetter: { data: makeCoverLetter({ agent_reasoning: null }) },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(screen.queryByTestId(REASONING_TESTID)).not.toBeInTheDocument();
	});

	// Stories Used
	// -----------------------------------------------------------------------

	it("renders story titles with associated skill names", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(STORIES_TESTID)).toBeInTheDocument();
		});
		expect(
			screen.getByText("Turned around failing project"),
		).toBeInTheDocument();
		expect(screen.getByText("Scaled Agile adoption")).toBeInTheDocument();
		// Skill tags
		expect(screen.getByText("Leadership")).toBeInTheDocument();
		expect(screen.getByText("SAFe")).toBeInTheDocument();
	});

	it("hides stories section when no stories used", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({ achievement_stories_used: [] }),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(screen.queryByTestId(STORIES_TESTID)).not.toBeInTheDocument();
	});

	it("renders story without skills gracefully", async () => {
		setupMockApi({
			stories: {
				data: [
					{
						id: STORY_1_ID,
						persona_id: PERSONA_ID,
						title: "Solo story",
						context: "Context",
						action: "Action",
						outcome: "Outcome",
						skills_demonstrated: [],
						related_job_id: null,
						display_order: 0,
					},
				],
				meta: { total: 1, page: 1, per_page: 20, total_pages: 1 },
			},
			coverLetter: {
				data: makeCoverLetter({ achievement_stories_used: [STORY_1_ID] }),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(STORIES_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByText("Solo story")).toBeInTheDocument();
	});

	// Editable Textarea
	// -----------------------------------------------------------------------

	it("renders draft text in textarea", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		const textarea = screen.getByRole("textbox", { name: /cover letter/i });
		expect(textarea).toHaveValue(MOCK_DRAFT_TEXT);
	});

	it("textarea is editable when status is Draft", async () => {
		setupMockApi();
		const user = userEvent.setup();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		const textarea = screen.getByRole("textbox", {
			name: /cover letter/i,
		}) as HTMLTextAreaElement;

		await user.clear(textarea);
		await user.type(textarea, "New content");
		expect(textarea).toHaveValue("New content");
	});

	it("textarea is read-only when status is Approved", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					status: "Approved",
					final_text: MOCK_DRAFT_TEXT,
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		const textarea = screen.getByRole("textbox", { name: /cover letter/i });
		expect(textarea).toHaveAttribute("readonly");
	});

	// Word Count
	// -----------------------------------------------------------------------

	it("shows word count with target range", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});
		// MOCK_DRAFT_TEXT has a specific word count
		const wordCount = MOCK_DRAFT_TEXT.split(/\s+/).filter(Boolean).length;
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveTextContent(
			`${wordCount}`,
		);
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveTextContent(
			/250[–-]350/,
		);
	});

	it("shows green indicator when word count within 250-350", async () => {
		// Generate text with exactly 300 words
		const words = Array.from({ length: 300 }, (_, i) => `word${i}`).join(" ");
		setupMockApi({
			coverLetter: { data: makeCoverLetter({ draft_text: words }) },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveAttribute(
			"data-in-range",
			"true",
		);
	});

	it("shows amber indicator when word count below 250", async () => {
		// Short text (well under 250 words)
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({ draft_text: "Just a few words here" }),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveAttribute(
			"data-in-range",
			"false",
		);
	});

	it("shows amber indicator when word count above 350", async () => {
		const words = Array.from({ length: 400 }, (_, i) => `word${i}`).join(" ");
		setupMockApi({
			coverLetter: { data: makeCoverLetter({ draft_text: words }) },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveAttribute(
			"data-in-range",
			"false",
		);
	});

	it("updates word count as user edits text", async () => {
		const user = userEvent.setup();
		// Start with text within range
		const words = Array.from({ length: 300 }, (_, i) => `word${i}`).join(" ");
		setupMockApi({
			coverLetter: { data: makeCoverLetter({ draft_text: words }) },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});

		// Verify initially in range
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveAttribute(
			"data-in-range",
			"true",
		);
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveTextContent("300");

		// Clear textarea — word count should drop
		const textarea = screen.getByRole("textbox", { name: /cover letter/i });
		await user.clear(textarea);
		await user.type(textarea, "Short");

		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveTextContent("1");
		expect(screen.getByTestId(WORD_COUNT_TESTID)).toHaveAttribute(
			"data-in-range",
			"false",
		);
	});

	// API Calls
	// -----------------------------------------------------------------------

	it("fetches cover letter, job posting, stories, and skills", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});

		expect(mocks.mockApiGet).toHaveBeenCalledWith(
			`/cover-letters/${COVER_LETTER_ID}`,
		);
		expect(mocks.mockApiGet).toHaveBeenCalledWith(
			`/job-postings/${JOB_POSTING_ID}`,
		);
		expect(mocks.mockApiGet).toHaveBeenCalledWith(
			`/personas/${PERSONA_ID}/achievement-stories`,
		);
		expect(mocks.mockApiGet).toHaveBeenCalledWith(
			`/personas/${PERSONA_ID}/skills`,
		);
	});
});
