/**
 * Tests for the PersonaOverview component (§6.1).
 *
 * REQ-012 §7.1: Persona overview page with two-column header,
 * 8-card section grid with counts and edit links, and a
 * Discovery Preferences block.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PersonaOverview } from "./persona-overview";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const LOADING_TESTID = "loading-persona-overview";

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
	portfolio_url: "https://janedoe.dev",
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
	onboarding_complete: true,
	onboarding_step: null,
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

const MOCK_CUSTOM_NON_NEGOTIABLES = [
	{
		id: "cnn-001",
		persona_id: DEFAULT_PERSONA_ID,
		filter_name: "No consulting",
		filter_type: "Exclude" as const,
		filter_value: "consulting",
		filter_field: "description",
	},
	{
		id: "cnn-002",
		persona_id: DEFAULT_PERSONA_ID,
		filter_name: "Requires Python",
		filter_type: "Require" as const,
		filter_value: "Python",
		filter_field: "description",
	},
];

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
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	ApiError: mocks.MockApiError,
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...props
	}: {
		href: string;
		children: ReactNode;
		[key: string]: unknown;
	}) => (
		<a href={href} {...props}>
			{children}
		</a>
	),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

/** Set up mockApiGet to return all mock data based on URL. */
function setupApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
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
		if (url.endsWith("/custom-non-negotiables")) {
			return Promise.resolve(makeListResponse(MOCK_CUSTOM_NON_NEGOTIABLES));
		}
		return Promise.reject(new Error(`Unexpected URL: ${url}`));
	});
}

/** Set up mockApiGet to return empty data for all sub-entities. */
function setupEmptyApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url.endsWith("/voice-profile")) {
			return Promise.resolve({ data: {} });
		}
		// All list endpoints return empty arrays
		return Promise.resolve(makeListResponse([]));
	});
}

/** Render component and wait for loading to finish. */
async function renderAndWait() {
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<PersonaOverview persona={MOCK_PERSONA} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PersonaOverview", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		setupApiMocks();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	describe("loading", () => {
		it("shows skeleton while sub-entity queries load", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<PersonaOverview persona={MOCK_PERSONA} />
				</Wrapper>,
			);

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("renders heading after loading", async () => {
			await renderAndWait();

			expect(
				screen.getByRole("heading", { name: /your professional profile/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	describe("API calls", () => {
		it("makes GET requests for all 7 sub-entity endpoints", async () => {
			await renderAndWait();

			const calls = mocks.mockApiGet.mock.calls.map((c: string[]) => c[0]);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/work-history`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/education`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/skills`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/certifications`);
			expect(calls).toContain(
				`/personas/${DEFAULT_PERSONA_ID}/achievement-stories`,
			);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/voice-profile`);
			expect(calls).toContain(
				`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables`,
			);
		});
	});

	// -----------------------------------------------------------------------
	// Header
	// -----------------------------------------------------------------------

	describe("header", () => {
		it("displays name, email, phone, and formatted location", async () => {
			await renderAndWait();

			const header = screen.getByTestId("persona-header");
			expect(within(header).getByText("Jane Doe")).toBeInTheDocument();
			expect(within(header).getByText("jane@example.com")).toBeInTheDocument();
			expect(within(header).getByText("555-0100")).toBeInTheDocument();
			expect(within(header).getByText(/Seattle, WA, US/)).toBeInTheDocument();
		});

		it("shows LinkedIn and portfolio links when present", async () => {
			await renderAndWait();

			const header = screen.getByTestId("persona-header");
			const linkedinLink = within(header).getByRole("link", {
				name: /linkedin/i,
			});
			expect(linkedinLink).toHaveAttribute(
				"href",
				"https://linkedin.com/in/janedoe",
			);
			const portfolioLink = within(header).getByRole("link", {
				name: /portfolio/i,
			});
			expect(portfolioLink).toHaveAttribute("href", "https://janedoe.dev");
		});

		it("hides LinkedIn and portfolio links when null", async () => {
			const personaNoLinks = {
				...MOCK_PERSONA,
				linkedin_url: null,
				portfolio_url: null,
			};
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<PersonaOverview persona={personaNoLinks} />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});

			const header = screen.getByTestId("persona-header");
			expect(
				within(header).queryByRole("link", { name: /linkedin/i }),
			).not.toBeInTheDocument();
			expect(
				within(header).queryByRole("link", { name: /portfolio/i }),
			).not.toBeInTheDocument();
		});

		it("displays current role, company, years of experience, and summary", async () => {
			await renderAndWait();

			const header = screen.getByTestId("persona-header");
			expect(within(header).getByText("Staff Engineer")).toBeInTheDocument();
			expect(within(header).getByText("TechCorp")).toBeInTheDocument();
			// Use exact match to avoid collision with summary text
			expect(within(header).getByText("8 years")).toBeInTheDocument();
			expect(
				within(header).getByText(
					"Senior software engineer with 8 years experience",
				),
			).toBeInTheDocument();
		});

		it("shows fallback when professional fields are null", async () => {
			const personaNoProf = {
				...MOCK_PERSONA,
				current_role: null,
				current_company: null,
				years_experience: null,
				professional_summary: null,
			};
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<PersonaOverview persona={personaNoProf} />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});

			// Should still render the header without errors
			expect(screen.getByTestId("persona-header")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Section cards — populated
	// -----------------------------------------------------------------------

	describe("section cards — populated", () => {
		it("shows correct count for work history", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-work-history");
			expect(within(card).getByText(/2 positions/i)).toBeInTheDocument();
		});

		it("shows correct count for skills", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-skills");
			expect(within(card).getByText(/2 Hard, 1 Soft/)).toBeInTheDocument();
		});

		it("shows correct count for education", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-education");
			expect(within(card).getByText(/1 entry/i)).toBeInTheDocument();
		});

		it("shows correct count for certifications", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-certifications");
			expect(within(card).getByText(/1 certification/i)).toBeInTheDocument();
		});

		it("shows correct count for achievement stories", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-achievement-stories");
			expect(within(card).getByText(/2 stories/i)).toBeInTheDocument();
		});

		it("shows configured for voice profile", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-voice");
			expect(within(card).getByText(/Configured/i)).toBeInTheDocument();
		});

		it("shows correct count for custom non-negotiables", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-non-negotiables");
			expect(within(card).getByText(/2 custom filters/i)).toBeInTheDocument();
		});

		it("shows correct count for growth targets from persona prop", async () => {
			await renderAndWait();

			const card = screen.getByTestId("section-card-growth");
			expect(within(card).getByText(/2 target roles/i)).toBeInTheDocument();
			expect(within(card).getByText(/2 target skills/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Section cards — empty
	// -----------------------------------------------------------------------

	describe("section cards — empty", () => {
		it("shows 0 counts when no data returned", async () => {
			setupEmptyApiMocks();
			await renderAndWait();

			const whCard = screen.getByTestId("section-card-work-history");
			expect(within(whCard).getByText(/0 positions/i)).toBeInTheDocument();

			const eduCard = screen.getByTestId("section-card-education");
			expect(within(eduCard).getByText(/0 entries/i)).toBeInTheDocument();

			const certCard = screen.getByTestId("section-card-certifications");
			expect(
				within(certCard).getByText(/0 certifications/i),
			).toBeInTheDocument();
		});

		it("shows 'Not set' for voice profile when empty", async () => {
			setupEmptyApiMocks();
			await renderAndWait();

			const card = screen.getByTestId("section-card-voice");
			expect(within(card).getByText(/Not set/i)).toBeInTheDocument();
		});

		it("shows 0 targets for growth when persona arrays are empty", async () => {
			const emptyPersona = {
				...MOCK_PERSONA,
				target_roles: [],
				target_skills: [],
			};
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<PersonaOverview persona={emptyPersona} />
				</Wrapper>,
			);
			await waitFor(() => {
				expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
			});

			const card = screen.getByTestId("section-card-growth");
			expect(within(card).getByText(/0 target roles/i)).toBeInTheDocument();
			expect(within(card).getByText(/0 target skills/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edit links
	// -----------------------------------------------------------------------

	describe("edit links", () => {
		it("each section card has a link with correct href", async () => {
			await renderAndWait();

			const expectedLinks: Record<string, string> = {
				"section-card-work-history": "/persona/work-history",
				"section-card-skills": "/persona/skills",
				"section-card-achievement-stories": "/persona/achievement-stories",
				"section-card-certifications": "/persona/certifications",
				"section-card-education": "/persona/education",
				"section-card-voice": "/persona/voice",
				"section-card-non-negotiables": "/persona/non-negotiables",
				"section-card-growth": "/persona/growth",
			};

			for (const [testId, href] of Object.entries(expectedLinks)) {
				const card = screen.getByTestId(testId);
				const link = within(card).getByRole("link", { name: /edit/i });
				expect(link).toHaveAttribute("href", href);
			}
		});

		it("discovery preferences has edit link to /persona/discovery", async () => {
			await renderAndWait();

			const discovery = screen.getByTestId("discovery-preferences");
			const link = within(discovery).getByRole("link", { name: /edit/i });
			expect(link).toHaveAttribute("href", "/persona/discovery");
		});
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	describe("error handling", () => {
		it("shows fallback for failed sub-entity fetch without crashing", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderAndWait();

			expect(
				screen.getByRole("heading", {
					name: /your professional profile/i,
				}),
			).toBeInTheDocument();
		});

		it("renders cards with fallback text when API errors occur", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderAndWait();

			const whCard = screen.getByTestId("section-card-work-history");
			expect(within(whCard).getByText("—")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Discovery preferences
	// -----------------------------------------------------------------------

	describe("discovery preferences", () => {
		it("displays fit threshold, auto-draft threshold, and polling frequency", async () => {
			await renderAndWait();

			const discovery = screen.getByTestId("discovery-preferences");
			expect(within(discovery).getByText(/70/)).toBeInTheDocument();
			expect(within(discovery).getByText(/85/)).toBeInTheDocument();
			expect(within(discovery).getByText(/Daily/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("page has h1 heading", async () => {
			await renderAndWait();

			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
		});
	});
});
