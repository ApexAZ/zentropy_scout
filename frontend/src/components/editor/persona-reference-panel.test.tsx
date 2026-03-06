/**
 * Tests for PersonaReferencePanel component.
 *
 * REQ-026 §5.1–§5.2: Persona reference panel with collapsible sections,
 * click-to-copy, and responsive toggle.
 */

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_ID = "00000000-0000-4000-a000-000000000001";

const MOCK_PERSONA = {
	id: PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000002",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "555-0100",
	home_city: "Seattle",
	home_state: "WA",
	home_country: "US",
	linkedin_url: null,
	portfolio_url: null,
	professional_summary: null,
	years_experience: null,
	current_role: null,
	current_company: null,
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium" as const,
	commutable_cities: [],
	max_commute_minutes: null,
	remote_preference: "No Preference" as const,
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: null,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference" as const,
	max_travel_percent: "None" as const,
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
		persona_id: PERSONA_ID,
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
		bullets: [
			{
				id: "b-001",
				work_history_id: "wh-001",
				text: "Led team of 12 engineers",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			},
			{
				id: "b-002",
				work_history_id: "wh-001",
				text: "Reduced cycle time by 40%",
				skills_demonstrated: [],
				metrics: "40%",
				display_order: 1,
			},
		],
	},
	{
		id: "wh-002",
		persona_id: PERSONA_ID,
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
		persona_id: PERSONA_ID,
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
		persona_id: PERSONA_ID,
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
		persona_id: PERSONA_ID,
		skill_name: "Leadership",
		skill_type: "Soft" as const,
		category: "Management",
		proficiency: "Proficient" as const,
		years_used: 3,
		last_used: "Current",
		display_order: 1,
	},
];

const MOCK_CERTIFICATIONS = [
	{
		id: "cert-001",
		persona_id: PERSONA_ID,
		certification_name: "AWS Solutions Architect",
		issuing_organization: "Amazon Web Services",
		date_obtained: "2023-06-15",
		expiration_date: "2026-06-15",
		credential_id: "ABC123",
		verification_url: null,
		display_order: 0,
	},
];

const MOCK_LIST_META = { total: 0, page: 1, per_page: 20, total_pages: 1 };

function makeListResponse<T>(data: T[]) {
	return { data, meta: { ...MOCK_LIST_META, total: data.length } };
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockApiGet: vi.fn(),
	mockShowToast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
	mockClipboardWriteText: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

import { PersonaReferencePanel } from "./persona-reference-panel";

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

function setupApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === `/personas/${PERSONA_ID}`) {
			return Promise.resolve({ data: MOCK_PERSONA });
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
		return Promise.reject(new Error(`Unexpected URL: ${url}`));
	});
}

function setupEmptyMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url === `/personas/${PERSONA_ID}`) {
			return Promise.resolve({ data: MOCK_PERSONA });
		}
		return Promise.resolve(makeListResponse([]));
	});
}

async function renderAndWait() {
	const Wrapper = createWrapper();
	render(
		<Wrapper>
			<PersonaReferencePanel personaId={PERSONA_ID} />
		</Wrapper>,
	);
	await waitFor(() => {
		expect(
			screen.queryByTestId("persona-panel-loading"),
		).not.toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockShowToast.success.mockReset();
	setupApiMocks();

	mocks.mockClipboardWriteText.mockReset().mockResolvedValue(undefined);
	Object.defineProperty(navigator, "clipboard", {
		value: { writeText: mocks.mockClipboardWriteText },
		writable: true,
		configurable: true,
	});
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PersonaReferencePanel", () => {
	describe("loading", () => {
		it("shows spinner while data loads", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			const Wrapper = createWrapper();
			render(
				<Wrapper>
					<PersonaReferencePanel personaId={PERSONA_ID} />
				</Wrapper>,
			);

			expect(screen.getByTestId("persona-panel-loading")).toBeInTheDocument();
		});

		it("renders panel container after loading", async () => {
			await renderAndWait();
			expect(screen.getByTestId("persona-reference-panel")).toBeInTheDocument();
		});
	});

	describe("section headers", () => {
		it("renders all five section headers", async () => {
			await renderAndWait();

			expect(
				screen.getByRole("button", { name: /contact info/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /work history/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /education/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /skills/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /certifications/i }),
			).toBeInTheDocument();
		});
	});

	describe("contact info section", () => {
		it("displays persona name, email, and phone", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-contact-info");
			expect(within(section).getByText("Jane Doe")).toBeInTheDocument();
			expect(within(section).getByText("jane@example.com")).toBeInTheDocument();
			expect(within(section).getByText("555-0100")).toBeInTheDocument();
		});

		it("displays location", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-contact-info");
			expect(within(section).getByText(/Seattle, WA, US/)).toBeInTheDocument();
		});
	});

	describe("work history section", () => {
		it("displays job entries with company and title", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-work-history");
			expect(within(section).getByText(/Staff Engineer/)).toBeInTheDocument();
			expect(within(section).getByText(/TechCorp/)).toBeInTheDocument();
			expect(within(section).getByText(/Senior Engineer/)).toBeInTheDocument();
			expect(within(section).getByText(/StartupCo/)).toBeInTheDocument();
		});

		it("shows bullets when job is expanded", async () => {
			const user = userEvent.setup();
			await renderAndWait();

			// Expand TechCorp job
			const jobButton = screen.getByRole("button", {
				name: /Staff Engineer.*TechCorp/,
			});
			await user.click(jobButton);

			expect(screen.getByText("Led team of 12 engineers")).toBeInTheDocument();
			expect(screen.getByText("Reduced cycle time by 40%")).toBeInTheDocument();
		});

		it("shows empty message for jobs with no bullets", async () => {
			const user = userEvent.setup();
			await renderAndWait();

			const jobButton = screen.getByRole("button", {
				name: /Senior Engineer.*StartupCo/,
			});
			await user.click(jobButton);

			expect(screen.getByText(/no bullets/i)).toBeInTheDocument();
		});
	});

	describe("education section", () => {
		it("displays education entries", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-education");
			expect(
				within(section).getByText(/B\.S\. Computer Science/),
			).toBeInTheDocument();
			expect(within(section).getByText(/MIT/)).toBeInTheDocument();
			expect(within(section).getByText(/2016/)).toBeInTheDocument();
		});
	});

	describe("skills section", () => {
		it("displays skill names", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-skills");
			expect(within(section).getByText("TypeScript")).toBeInTheDocument();
			expect(within(section).getByText("Leadership")).toBeInTheDocument();
		});
	});

	describe("certifications section", () => {
		it("displays certification names with issuing org", async () => {
			await renderAndWait();

			const section = screen.getByTestId("section-certifications");
			expect(
				within(section).getByText(
					/AWS Solutions Architect.*Amazon Web Services/,
				),
			).toBeInTheDocument();
		});
	});

	describe("collapsible sections", () => {
		it("sections start expanded by default", async () => {
			await renderAndWait();

			const contactButton = screen.getByRole("button", {
				name: /contact info/i,
			});
			expect(contactButton).toHaveAttribute("aria-expanded", "true");
		});

		it("clicking a section header collapses it", async () => {
			const user = userEvent.setup();
			await renderAndWait();

			const contactButton = screen.getByRole("button", {
				name: /contact info/i,
			});
			await user.click(contactButton);

			expect(contactButton).toHaveAttribute("aria-expanded", "false");
		});

		it("clicking a collapsed section expands it", async () => {
			const user = userEvent.setup();
			await renderAndWait();

			const contactButton = screen.getByRole("button", {
				name: /contact info/i,
			});
			// Collapse
			await user.click(contactButton);
			expect(contactButton).toHaveAttribute("aria-expanded", "false");

			// Re-expand
			await user.click(contactButton);
			expect(contactButton).toHaveAttribute("aria-expanded", "true");
		});
	});

	describe("click-to-copy", () => {
		it("copies text to clipboard on click", async () => {
			await renderAndWait();

			const copyButton = screen.getByRole("button", {
				name: /copy.*jane@example\.com/i,
			});
			fireEvent.click(copyButton);

			await waitFor(() => {
				expect(mocks.mockClipboardWriteText).toHaveBeenCalledWith(
					"jane@example.com",
				);
			});
		});

		it("shows success toast after copying", async () => {
			await renderAndWait();

			const copyButton = screen.getByRole("button", {
				name: /copy.*jane@example\.com/i,
			});
			fireEvent.click(copyButton);

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Copied to clipboard",
				);
			});
		});

		it("copies skill name on click", async () => {
			await renderAndWait();

			const copyButton = screen.getByRole("button", {
				name: /copy.*TypeScript/i,
			});
			fireEvent.click(copyButton);

			await waitFor(() => {
				expect(mocks.mockClipboardWriteText).toHaveBeenCalledWith("TypeScript");
			});
		});

		it("shows error toast when clipboard write fails", async () => {
			mocks.mockClipboardWriteText.mockRejectedValueOnce(
				new Error("Permission denied"),
			);
			await renderAndWait();

			const copyButton = screen.getByRole("button", {
				name: /copy.*jane@example\.com/i,
			});
			fireEvent.click(copyButton);

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to copy to clipboard",
				);
			});
		});
	});

	describe("empty data", () => {
		it("shows empty messages when no sub-entity data", async () => {
			setupEmptyMocks();
			await renderAndWait();

			expect(screen.getByText(/no work history/i)).toBeInTheDocument();
			expect(screen.getByText(/no education/i)).toBeInTheDocument();
			expect(screen.getByText(/no skills/i)).toBeInTheDocument();
			expect(screen.getByText(/no certifications/i)).toBeInTheDocument();
		});
	});

	describe("API calls", () => {
		it("fetches persona and 4 sub-entity endpoints", async () => {
			await renderAndWait();

			const calls = mocks.mockApiGet.mock.calls.map((c: string[]) => c[0]);
			expect(calls).toContain(`/personas/${PERSONA_ID}`);
			expect(calls).toContain(`/personas/${PERSONA_ID}/work-history`);
			expect(calls).toContain(`/personas/${PERSONA_ID}/education`);
			expect(calls).toContain(`/personas/${PERSONA_ID}/skills`);
			expect(calls).toContain(`/personas/${PERSONA_ID}/certifications`);
		});
	});
});
