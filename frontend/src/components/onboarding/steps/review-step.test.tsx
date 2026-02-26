/**
 * Tests for the review step component (onboarding Step 11 — final step).
 *
 * REQ-019 §7.1: Structured summary with collapsible sections for all
 * persona areas. Each section has an "Edit" link back to the relevant step.
 * "Complete Onboarding" finalizes the persona and triggers job discovery.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewStep } from "./review-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const LOADING_TESTID = "loading-review";
const CONFIRM_BUTTON_TESTID = "confirm-button";
const BACK_BUTTON_TESTID = "back-button";

const MOCK_PERSONA = {
	id: DEFAULT_PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000002",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "555-0100",
	home_city: "Seattle",
	home_state: "WA",
	home_country: "US",
	linkedin_url: "https://linkedin.com/in/janedoe",
	portfolio_url: null,
	professional_summary: "Senior software engineer with 8 years experience",
	years_experience: 8,
	current_role: "Staff Engineer",
	current_company: "TechCorp",
	target_roles: ["Engineering Manager", "Tech Lead"],
	target_skills: ["Leadership", "System Design"],
	stretch_appetite: "Medium" as const,
	commutable_cities: ["Seattle", "Bellevue"],
	max_commute_minutes: 30,
	remote_preference: "Hybrid OK" as const,
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: 180000,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: ["Gambling"],
	company_size_preference: "Mid-size" as const,
	max_travel_percent: "<25%" as const,
	minimum_fit_threshold: 70,
	auto_draft_threshold: 85,
	polling_frequency: "Daily" as const,
	onboarding_complete: false,
	onboarding_step: "review",
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_WORK_HISTORIES = [
	{
		id: "wh-001",
		persona_id: DEFAULT_PERSONA_ID,
		company_name: "TechCorp",
		company_industry: "Technology",
		job_title: "Staff Engineer",
		start_date: "2022-01-01",
		end_date: null,
		is_current: true,
		location: "Seattle, WA",
		work_model: "Hybrid" as const,
		description: null,
		display_order: 0,
		bullets: [],
	},
	{
		id: "wh-002",
		persona_id: DEFAULT_PERSONA_ID,
		company_name: "StartupCo",
		company_industry: "SaaS",
		job_title: "Senior Engineer",
		start_date: "2019-03-01",
		end_date: "2021-12-31",
		is_current: false,
		location: "San Francisco, CA",
		work_model: "Remote" as const,
		description: null,
		display_order: 1,
		bullets: [],
	},
];

const MOCK_EDUCATIONS = [
	{
		id: "edu-001",
		persona_id: DEFAULT_PERSONA_ID,
		institution: "MIT",
		degree: "B.S.",
		field_of_study: "Computer Science",
		graduation_year: 2016,
		gpa: 3.8,
		honors: "Magna Cum Laude",
		display_order: 0,
	},
];

const MOCK_SKILLS = [
	{
		id: "sk-001",
		persona_id: DEFAULT_PERSONA_ID,
		skill_name: "TypeScript",
		skill_type: "Hard" as const,
		category: "Programming",
		proficiency: "Expert" as const,
		years_used: 5,
		last_used: "Current",
		display_order: 0,
	},
	{
		id: "sk-002",
		persona_id: DEFAULT_PERSONA_ID,
		skill_name: "React",
		skill_type: "Hard" as const,
		category: "Frontend",
		proficiency: "Expert" as const,
		years_used: 6,
		last_used: "Current",
		display_order: 1,
	},
	{
		id: "sk-003",
		persona_id: DEFAULT_PERSONA_ID,
		skill_name: "Leadership",
		skill_type: "Soft" as const,
		category: "Management",
		proficiency: "Proficient" as const,
		years_used: 3,
		last_used: "Current",
		display_order: 2,
	},
];

const MOCK_CERTIFICATIONS = [
	{
		id: "cert-001",
		persona_id: DEFAULT_PERSONA_ID,
		certification_name: "AWS Solutions Architect",
		issuing_organization: "Amazon Web Services",
		date_obtained: "2023-06-15",
		expiration_date: "2026-06-15",
		credential_id: "ABC123",
		verification_url: null,
		display_order: 0,
	},
];

const MOCK_STORIES = [
	{
		id: "story-001",
		persona_id: DEFAULT_PERSONA_ID,
		title: "Led Platform Migration",
		context: "Legacy monolith needed modernization",
		action: "Designed microservices architecture",
		outcome: "50% reduction in deploy time",
		skills_demonstrated: ["sk-001"],
		related_job_id: "wh-001",
		display_order: 0,
	},
	{
		id: "story-002",
		persona_id: DEFAULT_PERSONA_ID,
		title: "Built ML Pipeline",
		context: "No automated data processing",
		action: "Implemented end-to-end pipeline",
		outcome: "Processed 10x more data",
		skills_demonstrated: [],
		related_job_id: null,
		display_order: 1,
	},
];

const MOCK_VOICE_PROFILE = {
	id: "vp-001",
	persona_id: DEFAULT_PERSONA_ID,
	tone: "Direct, confident",
	sentence_style: "Short sentences, active voice",
	vocabulary_level: "Technical when relevant",
	personality_markers: "Occasional dry humor",
	sample_phrases: [],
	things_to_avoid: [],
	writing_sample_text: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

/** Builds a paginated list response envelope. */
const MOCK_LIST_META = { total: 0, page: 1, per_page: 20, total_pages: 1 };

function makeListResponse<T>(data: T[]) {
	return { data, meta: { ...MOCK_LIST_META, total: data.length } };
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
		mockCompleteOnboarding: vi.fn().mockResolvedValue(undefined),
		mockBack: vi.fn(),
		mockGoToStep: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		completeOnboarding: mocks.mockCompleteOnboarding,
		isCompleting: false,
		back: mocks.mockBack,
		goToStep: mocks.mockGoToStep,
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Set up mockApiGet to return all mock data based on URL. */
function setupApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === "/personas") {
			return Promise.resolve(makeListResponse([MOCK_PERSONA]));
		}
		if (url.endsWith("/work-history")) {
			return Promise.resolve(makeListResponse(MOCK_WORK_HISTORIES));
		}
		if (url.endsWith("/education")) {
			return Promise.resolve(makeListResponse(MOCK_EDUCATIONS));
		}
		if (url.endsWith("/skills")) {
			return Promise.resolve(makeListResponse(MOCK_SKILLS));
		}
		if (url.endsWith("/certifications")) {
			return Promise.resolve(makeListResponse(MOCK_CERTIFICATIONS));
		}
		if (url.endsWith("/achievement-stories")) {
			return Promise.resolve(makeListResponse(MOCK_STORIES));
		}
		if (url.endsWith("/voice-profile")) {
			return Promise.resolve({ data: MOCK_VOICE_PROFILE });
		}
		return Promise.reject(new Error(`Unexpected URL: ${url}`));
	});
}

/** Set up mockApiGet to return empty data for all sub-entities. */
function setupEmptyApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === "/personas") {
			return Promise.resolve(makeListResponse([MOCK_PERSONA]));
		}
		if (url.endsWith("/voice-profile")) {
			return Promise.resolve({ data: {} });
		}
		// All list endpoints return empty arrays
		return Promise.resolve(makeListResponse([]));
	});
}

/** Render step and wait for loading to finish. */
async function renderAndWait() {
	const user = userEvent.setup();
	render(<ReviewStep />);
	await waitFor(() => {
		expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
	});
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReviewStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockCompleteOnboarding.mockReset().mockResolvedValue(undefined);
		mocks.mockBack.mockReset();
		mocks.mockGoToStep.mockReset();
		setupApiMocks();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching data", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<ReviewStep />);

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("renders title after loading", async () => {
			await renderAndWait();

			expect(
				screen.getByRole("heading", { name: /review/i }),
			).toBeInTheDocument();
		});

		it("fetches all persona data endpoints", async () => {
			await renderAndWait();

			const calls = mocks.mockApiGet.mock.calls.map((c: string[]) => c[0]);
			expect(calls).toContain("/personas");
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/work-history`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/education`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/skills`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/certifications`);
			expect(calls).toContain(
				`/personas/${DEFAULT_PERSONA_ID}/achievement-stories`,
			);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/voice-profile`);
		});
	});

	// -----------------------------------------------------------------------
	// Section content
	// -----------------------------------------------------------------------

	describe("sections", () => {
		it("displays basic info with name and contact details", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-basic-info");
			expect(within(section).getByText("Jane Doe")).toBeInTheDocument();
			expect(within(section).getByText("jane@example.com")).toBeInTheDocument();
			expect(within(section).getByText(/Seattle/)).toBeInTheDocument();
		});

		it("displays professional overview", async () => {
			await renderAndWait();

			const section = screen.getByTestId(
				"review-section-professional-overview",
			);
			expect(within(section).getByText("Staff Engineer")).toBeInTheDocument();
			expect(within(section).getByText("TechCorp")).toBeInTheDocument();
			expect(within(section).getByText("8 years")).toBeInTheDocument();
		});

		it("displays work history with job count", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-work-history");
			expect(within(section).getByText(/2 positions/i)).toBeInTheDocument();
		});

		it("displays education with entry count", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-education");
			expect(within(section).getByText(/1 entry/i)).toBeInTheDocument();
		});

		it("displays skills with count by type", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-skills");
			expect(within(section).getByText(/2 Hard/)).toBeInTheDocument();
			expect(within(section).getByText(/1 Soft/)).toBeInTheDocument();
		});

		it("displays certifications with count", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-certifications");
			expect(within(section).getByText(/1 certification/i)).toBeInTheDocument();
		});

		it("displays achievement stories with count", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-achievement-stories");
			expect(within(section).getByText(/2 stories/i)).toBeInTheDocument();
		});

		it("displays non-negotiables summary", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-non-negotiables");
			expect(within(section).getByText(/Hybrid OK/)).toBeInTheDocument();
			expect(within(section).getByText(/\$180,000/)).toBeInTheDocument();
		});

		it("displays growth targets", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-growth-targets");
			expect(
				within(section).getByText("Engineering Manager"),
			).toBeInTheDocument();
			expect(within(section).getByText("Medium")).toBeInTheDocument();
		});

		it("displays voice profile summary", async () => {
			await renderAndWait();

			const section = screen.getByTestId("review-section-voice-profile");
			expect(
				within(section).getByText("Direct, confident"),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Collapsible behavior
	// -----------------------------------------------------------------------

	describe("collapsible behavior", () => {
		it("sections start expanded by default", async () => {
			await renderAndWait();

			// Content inside a section should be visible
			expect(screen.getByText("Jane Doe")).toBeInTheDocument();
		});

		it("clicking a section header toggles its content", async () => {
			const user = await renderAndWait();

			const header = screen.getByTestId("review-header-basic-info");
			await user.click(header);

			// Content should be hidden after collapse
			expect(screen.queryByText("Jane Doe")).not.toBeInTheDocument();

			// Click again to expand
			await user.click(header);
			expect(screen.getByText("Jane Doe")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edit navigation
	// -----------------------------------------------------------------------

	describe("edit navigation", () => {
		it("Edit on Basic Info navigates to step 2", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-basic-info"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(2);
		});

		it("Edit on Professional Overview navigates to step 2", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-professional-overview"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(2);
		});

		it("Edit on Work History navigates to step 3", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-work-history"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(3);
		});

		it("Edit on Education navigates to step 4", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-education"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(4);
		});

		it("Edit on Skills navigates to step 5", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-skills"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(5);
		});

		it("Edit on Certifications navigates to step 6", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-certifications"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(6);
		});

		it("Edit on Achievement Stories navigates to step 7", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-achievement-stories"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(7);
		});

		it("Edit on Non-negotiables navigates to step 8", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-non-negotiables"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(8);
		});

		it("Edit on Growth Targets navigates to step 9", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-growth-targets"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(9);
		});

		it("Edit on Voice Profile navigates to step 10", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId("edit-voice-profile"));

			expect(mocks.mockGoToStep).toHaveBeenCalledWith(10);
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls completeOnboarding() when 'Complete Onboarding' is clicked", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId(CONFIRM_BUTTON_TESTID));

			expect(mocks.mockCompleteOnboarding).toHaveBeenCalledTimes(1);
		});

		it("calls back() when Back is clicked", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId(BACK_BUTTON_TESTID));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("does not render a Skip button", async () => {
			await renderAndWait();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fetch failure
	// -----------------------------------------------------------------------

	describe("fetch failure", () => {
		it("renders with empty data when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderAndWait();

			// Should still render the review heading
			expect(
				screen.getByRole("heading", { name: /review/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Empty sub-entity data
	// -----------------------------------------------------------------------

	describe("empty data", () => {
		it("shows 0 counts for sections with no sub-entity data", async () => {
			setupEmptyApiMocks();
			await renderAndWait();

			const whSection = screen.getByTestId("review-section-work-history");
			expect(within(whSection).getByText(/0 positions/i)).toBeInTheDocument();

			const eduSection = screen.getByTestId("review-section-education");
			expect(within(eduSection).getByText(/0 entries/i)).toBeInTheDocument();

			const skillSection = screen.getByTestId("review-section-skills");
			expect(within(skillSection).getByText(/0 Hard/)).toBeInTheDocument();

			const certSection = screen.getByTestId("review-section-certifications");
			expect(
				within(certSection).getByText(/0 certifications/i),
			).toBeInTheDocument();

			const storySection = screen.getByTestId(
				"review-section-achievement-stories",
			);
			expect(within(storySection).getByText(/0 stories/i)).toBeInTheDocument();
		});
	});
});
