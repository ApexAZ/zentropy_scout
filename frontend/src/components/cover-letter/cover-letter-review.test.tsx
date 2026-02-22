/**
 * Tests for the CoverLetterReview component (§9.1, §9.2).
 *
 * REQ-012 §10.2: Cover letter review with agent reasoning,
 * stories used, editable textarea, and word count indicator.
 * REQ-012 §10.3: Validation display with error/warning banners
 * and voice check badge.
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
const VALIDATION_ERRORS_TESTID = "validation-errors";
const VALIDATION_WARNINGS_TESTID = "validation-warnings";
const VOICE_CHECK_TESTID = "voice-check";
const APPROVE_SPINNER_TESTID = "approve-spinner";
const DOWNLOAD_PDF_TESTID = "download-pdf";

const APPROVE_BUTTON = "Approve";

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
		validation_result: null,
		approved_at: null,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		archived_at: null,
		...overrides,
	};
}

function makeVoiceProfile(overrides?: Record<string, unknown>) {
	return {
		id: "vp-1",
		persona_id: PERSONA_ID,
		tone: "Direct, confident",
		sentence_style: "Short, active voice",
		vocabulary_level: "Professional",
		personality_markers: null,
		sample_phrases: [],
		things_to_avoid: [],
		writing_sample_text: null,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
		...overrides,
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
const MOCK_JOB_POSTING_RESPONSE = { data: makePersonaJob() };
const MOCK_STORIES_RESPONSE = {
	data: makeAchievementStories(),
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};
const MOCK_SKILLS_RESPONSE = {
	data: makeSkills(),
	meta: { total: 3, page: 1, per_page: 20, total_pages: 1 },
};
const MOCK_VOICE_PROFILE_RESPONSE = { data: makeVoiceProfile() };

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
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

import { CoverLetterReview } from "./cover-letter-review";

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
	voiceProfile?: unknown;
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
		if (path.includes("/voice-profile"))
			return Promise.resolve(
				overrides?.voiceProfile ?? MOCK_VOICE_PROFILE_RESPONSE,
			);
		return Promise.reject(new Error(`Unexpected API call: ${path}`));
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
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

	// Validation Display (§9.2)
	// -----------------------------------------------------------------------

	it("shows error banner with red styling for error-severity issues", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					validation_result: {
						passed: false,
						issues: [
							{
								severity: "error",
								rule: "length_min",
								message: "Cover letter is too short (minimum 250 words).",
							},
						],
						word_count: 150,
					},
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(VALIDATION_ERRORS_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(VALIDATION_ERRORS_TESTID)).toHaveAttribute(
			"role",
			"alert",
		);
		expect(
			screen.getByText("Cover letter is too short (minimum 250 words)."),
		).toBeInTheDocument();
	});

	it("shows warning notice with amber styling for warning-severity issues", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					validation_result: {
						passed: true,
						issues: [
							{
								severity: "warning",
								rule: "company_specificity",
								message: "Company name not mentioned in opening paragraph.",
							},
						],
						word_count: 300,
					},
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(
				screen.getByTestId(VALIDATION_WARNINGS_TESTID),
			).toBeInTheDocument();
		});
		// <output> provides implicit role="status" — verify semantic element
		expect(screen.getByTestId(VALIDATION_WARNINGS_TESTID).tagName).toBe(
			"OUTPUT",
		);
		expect(
			screen.getByText("Company name not mentioned in opening paragraph."),
		).toBeInTheDocument();
	});

	it("shows both error and warning banners when mixed severities", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					validation_result: {
						passed: false,
						issues: [
							{
								severity: "error",
								rule: "blacklist_violation",
								message: "Contains blacklisted phrase.",
							},
							{
								severity: "warning",
								rule: "company_specificity",
								message: "Company name not mentioned.",
							},
						],
						word_count: 300,
					},
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(VALIDATION_ERRORS_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(VALIDATION_WARNINGS_TESTID)).toBeInTheDocument();
		expect(
			screen.getByText("Contains blacklisted phrase."),
		).toBeInTheDocument();
		expect(screen.getByText("Company name not mentioned.")).toBeInTheDocument();
	});

	it("hides validation section when no issues", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					validation_result: {
						passed: true,
						issues: [],
						word_count: 300,
					},
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(
			screen.queryByTestId(VALIDATION_ERRORS_TESTID),
		).not.toBeInTheDocument();
		expect(
			screen.queryByTestId(VALIDATION_WARNINGS_TESTID),
		).not.toBeInTheDocument();
	});

	it("hides validation section when validation_result is null", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({ validation_result: null }),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(
			screen.queryByTestId(VALIDATION_ERRORS_TESTID),
		).not.toBeInTheDocument();
		expect(
			screen.queryByTestId(VALIDATION_WARNINGS_TESTID),
		).not.toBeInTheDocument();
	});

	it("shows multiple error messages in error banner", async () => {
		setupMockApi({
			coverLetter: {
				data: makeCoverLetter({
					validation_result: {
						passed: false,
						issues: [
							{
								severity: "error",
								rule: "length_min",
								message: "Too short.",
							},
							{
								severity: "error",
								rule: "metric_accuracy",
								message: "Metric not verifiable.",
							},
						],
						word_count: 100,
					},
				}),
			},
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(VALIDATION_ERRORS_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByText("Too short.")).toBeInTheDocument();
		expect(screen.getByText("Metric not verifiable.")).toBeInTheDocument();
	});

	// Voice Check Badge (§9.2)
	// -----------------------------------------------------------------------

	it("shows voice check badge with persona tone", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(VOICE_CHECK_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(VOICE_CHECK_TESTID)).toHaveTextContent(
			/Direct, confident/,
		);
	});

	it("shows checkmark on voice badge", async () => {
		setupMockApi();
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(VOICE_CHECK_TESTID)).toBeInTheDocument();
		});
		expect(screen.getByTestId(VOICE_CHECK_TESTID)).toHaveTextContent("✓");
	});

	it("hides voice badge when voice profile not available", async () => {
		setupMockApi({
			voiceProfile: { data: null },
		});
		renderReview();
		await waitFor(() => {
			expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
		});
		expect(screen.queryByTestId(VOICE_CHECK_TESTID)).not.toBeInTheDocument();
	});

	// API Calls
	// -----------------------------------------------------------------------

	it("fetches cover letter, job posting, stories, skills, and voice profile", async () => {
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
		expect(mocks.mockApiGet).toHaveBeenCalledWith(
			`/personas/${PERSONA_ID}/voice-profile`,
		);
	});

	// Approval Flow (§9.5)
	// -----------------------------------------------------------------------

	describe("approval flow", () => {
		it("shows approve button when status is Draft", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: APPROVE_BUTTON }),
			).toBeInTheDocument();
		});

		it("hides approve button when status is Approved", async () => {
			setupMockApi({
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: APPROVE_BUTTON }),
			).not.toBeInTheDocument();
		});

		it("calls PATCH with status Approved when clicked", async () => {
			const user = userEvent.setup();
			setupMockApi();
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: APPROVE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/cover-letters/${COVER_LETTER_ID}`,
					{ status: "Approved" },
				);
			});
		});

		it("shows loading state during approval", async () => {
			const user = userEvent.setup();
			setupMockApi();
			mocks.mockApiPatch.mockReturnValue(new Promise(() => {}));
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: APPROVE_BUTTON }));

			await waitFor(() => {
				expect(screen.getByTestId(APPROVE_SPINNER_TESTID)).toBeInTheDocument();
			});
			const approveButton = screen.getByRole("button", {
				name: /approv/i,
			});
			expect(approveButton).toBeDisabled();
		});

		it("shows success toast and invalidates cache on approval", async () => {
			const user = userEvent.setup();
			setupMockApi();
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: makeCoverLetter({ status: "Approved" }),
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: APPROVE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Cover letter approved.",
				);
			});
			expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
		});

		it("shows error toast on approval failure", async () => {
			const user = userEvent.setup();
			setupMockApi();
			mocks.mockApiPatch.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: APPROVE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});

		it("shows final_text in textarea when status is Approved", async () => {
			setupMockApi({
				coverLetter: {
					data: makeCoverLetter({
						status: "Approved",
						draft_text: "Draft version",
						final_text: "Final approved version",
					}),
				},
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			const textarea = screen.getByRole("textbox", {
				name: /cover letter/i,
			});
			expect(textarea).toHaveValue("Final approved version");
		});
	});

	// PDF Download (§9.5)
	// -----------------------------------------------------------------------

	describe("PDF download", () => {
		it("shows download link when status is Approved", async () => {
			setupMockApi({
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(DOWNLOAD_PDF_TESTID)).toBeInTheDocument();
		});

		it("hides download link when status is Draft", async () => {
			setupMockApi();
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(DOWNLOAD_PDF_TESTID)).not.toBeInTheDocument();
		});

		it("download link points to submitted cover letter PDF endpoint", async () => {
			setupMockApi({
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			renderReview();
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			const link = screen.getByTestId(DOWNLOAD_PDF_TESTID);
			expect(link).toHaveAttribute(
				"href",
				expect.stringContaining(
					`/submitted-cover-letter-pdfs/${COVER_LETTER_ID}/download`,
				),
			);
		});
	});

	// hideActions mode (§9.6)
	// -----------------------------------------------------------------------

	describe("hideActions mode", () => {
		it("hides header and action buttons when hideActions is true", async () => {
			setupMockApi();
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<CoverLetterReview coverLetterId={COVER_LETTER_ID} hideActions />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			// Header hidden
			expect(
				screen.queryByText(/Senior Scrum Master at Acme Corp/),
			).not.toBeInTheDocument();
			expect(screen.queryByText("Draft")).not.toBeInTheDocument();
			// Approve button hidden
			expect(
				screen.queryByRole("button", { name: APPROVE_BUTTON }),
			).not.toBeInTheDocument();
		});

		it("hides PDF download when hideActions is true", async () => {
			setupMockApi({
				coverLetter: { data: makeCoverLetter({ status: "Approved" }) },
			});
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<CoverLetterReview coverLetterId={COVER_LETTER_ID} hideActions />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId(DOWNLOAD_PDF_TESTID)).not.toBeInTheDocument();
		});

		it("still shows letter body and word count when hideActions is true", async () => {
			setupMockApi();
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<CoverLetterReview coverLetterId={COVER_LETTER_ID} hideActions />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.getByTestId(REVIEW_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByRole("textbox", { name: /cover letter/i }),
			).toBeInTheDocument();
			expect(screen.getByTestId(WORD_COUNT_TESTID)).toBeInTheDocument();
		});
	});
});
