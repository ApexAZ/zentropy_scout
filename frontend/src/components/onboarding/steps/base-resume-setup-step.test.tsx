/**
 * Tests for the base resume setup step component (onboarding Step 12).
 *
 * REQ-012 §6.3.12: Resume creation form with item selection checkboxes.
 * User enters resume name, role type, and summary, then selects which
 * work history entries (with bullets), education, certifications, and
 * skills to include. All items are checked by default. POST creates
 * the base resume and completes onboarding.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BaseResumeSetupStep } from "./base-resume-setup-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const BASE_RESUMES_ENDPOINT = "/base-resumes";
const LOADING_TESTID = "loading-base-resume-setup";
const SUBMIT_BUTTON_TESTID = "submit-button";
const BACK_BUTTON_TESTID = "back-button";
const MOCK_BASE_RESUME_RESPONSE = { data: { id: "br-001" } };

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
		bullets: [
			{
				id: "b-001",
				work_history_id: "wh-001",
				text: "Led platform migration to microservices",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			},
			{
				id: "b-002",
				work_history_id: "wh-001",
				text: "Mentored 3 junior engineers",
				skills_demonstrated: [],
				metrics: null,
				display_order: 1,
			},
		],
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
		bullets: [
			{
				id: "b-003",
				work_history_id: "wh-002",
				text: "Built CI/CD pipeline from scratch",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			},
		],
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
		mockApiPost: vi.fn(),
		MockApiError,
		mockNext: vi.fn(),
		mockBack: vi.fn(),
		mockCompleteOnboarding: vi.fn(),
		mockAddSystemMessage: vi.fn(),
		mockRouterReplace: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		back: mocks.mockBack,
		completeOnboarding: mocks.mockCompleteOnboarding,
	}),
}));

vi.mock("@/lib/chat-provider", () => ({
	useChat: () => ({
		addSystemMessage: mocks.mockAddSystemMessage,
	}),
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({
		replace: mocks.mockRouterReplace,
	}),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Set up mockApiGet to return all mock data based on URL. */
function setupApiMocks() {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url.endsWith("/work-history")) {
			return Promise.resolve(makeListResponse(MOCK_WORK_HISTORIES));
		}
		if (url.endsWith("/education")) {
			return Promise.resolve(makeListResponse(MOCK_EDUCATIONS));
		}
		if (url.endsWith("/certifications")) {
			return Promise.resolve(makeListResponse(MOCK_CERTIFICATIONS));
		}
		if (url.endsWith("/skills")) {
			return Promise.resolve(makeListResponse(MOCK_SKILLS));
		}
		return Promise.reject(new Error(`Unexpected URL: ${url}`));
	});
}

/** Set up mockApiGet to return empty data for all endpoints. */
function setupEmptyApiMocks() {
	mocks.mockApiGet.mockImplementation(() => {
		return Promise.resolve(makeListResponse([]));
	});
}

/** Render step and wait for loading to finish. */
async function renderAndWait() {
	const user = userEvent.setup();
	render(<BaseResumeSetupStep />);
	await waitFor(() => {
		expect(screen.queryByTestId(LOADING_TESTID)).not.toBeInTheDocument();
	});
	return user;
}

/** Fill required form fields with defaults or overrides. */
async function fillRequiredFields(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		name: string;
		roleType: string;
		summary: string;
	}>,
) {
	const values = {
		name: "Scrum Master Resume",
		roleType: "Scrum Master",
		summary: "Experienced agile leader with 8 years of experience",
		...overrides,
	};
	await user.type(screen.getByLabelText(/^resume name$/i), values.name);
	await user.type(screen.getByLabelText(/^role type$/i), values.roleType);
	await user.type(screen.getByLabelText(/^summary$/i), values.summary);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BaseResumeSetupStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		mocks.mockCompleteOnboarding.mockReset();
		mocks.mockAddSystemMessage.mockReset();
		mocks.mockRouterReplace.mockReset();
		mocks.mockCompleteOnboarding.mockResolvedValue(undefined);
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
			render(<BaseResumeSetupStep />);

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("renders title after loading", async () => {
			await renderAndWait();

			expect(
				screen.getByRole("heading", { name: /base resume setup/i }),
			).toBeInTheDocument();
		});

		it("fetches all required endpoints", async () => {
			await renderAndWait();

			const calls = mocks.mockApiGet.mock.calls.map((c: string[]) => c[0]);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/work-history`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/education`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/certifications`);
			expect(calls).toContain(`/personas/${DEFAULT_PERSONA_ID}/skills`);
		});
	});

	// -----------------------------------------------------------------------
	// Form fields
	// -----------------------------------------------------------------------

	describe("form fields", () => {
		it("renders name, role type, and summary inputs", async () => {
			await renderAndWait();

			expect(screen.getByLabelText(/^resume name$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^role type$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^summary$/i)).toBeInTheDocument();
		});

		it("shows validation errors for empty required fields on submit", async () => {
			const user = await renderAndWait();

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});

			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Work history checkboxes
	// -----------------------------------------------------------------------

	describe("work history selection", () => {
		it("renders a section for each work history entry", async () => {
			await renderAndWait();

			expect(
				screen.getByText("Staff Engineer at TechCorp"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Senior Engineer at StartupCo"),
			).toBeInTheDocument();
		});

		it("all jobs are checked by default", async () => {
			await renderAndWait();

			const jobCheckboxes = screen.getAllByTestId(/^job-checkbox-/);
			for (const checkbox of jobCheckboxes) {
				expect(checkbox).toHaveAttribute("data-state", "checked");
			}
		});

		it("renders bullets under each job", async () => {
			await renderAndWait();

			expect(
				screen.getByText("Led platform migration to microservices"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Mentored 3 junior engineers"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Built CI/CD pipeline from scratch"),
			).toBeInTheDocument();
		});

		it("all bullets are checked by default", async () => {
			await renderAndWait();

			const bulletCheckboxes = screen.getAllByTestId(/^bullet-checkbox-/);
			for (const checkbox of bulletCheckboxes) {
				expect(checkbox).toHaveAttribute("data-state", "checked");
			}
		});

		it("unchecking a job unchecks all its bullets", async () => {
			const user = await renderAndWait();

			const jobCheckbox = screen.getByTestId("job-checkbox-wh-001");
			await user.click(jobCheckbox);

			expect(jobCheckbox).toHaveAttribute("data-state", "unchecked");
			expect(screen.getByTestId("bullet-checkbox-b-001")).toHaveAttribute(
				"data-state",
				"unchecked",
			);
			expect(screen.getByTestId("bullet-checkbox-b-002")).toHaveAttribute(
				"data-state",
				"unchecked",
			);
		});

		it("re-checking a job does not re-check previously unchecked bullets", async () => {
			const user = await renderAndWait();

			const jobCheckbox = screen.getByTestId("job-checkbox-wh-001");

			// Uncheck then re-check
			await user.click(jobCheckbox);
			await user.click(jobCheckbox);

			expect(jobCheckbox).toHaveAttribute("data-state", "checked");
			// Bullets should still be unchecked (cascade only on uncheck)
			expect(screen.getByTestId("bullet-checkbox-b-001")).toHaveAttribute(
				"data-state",
				"unchecked",
			);
			expect(screen.getByTestId("bullet-checkbox-b-002")).toHaveAttribute(
				"data-state",
				"unchecked",
			);
		});

		it("toggling a bullet does not uncheck the parent job", async () => {
			const user = await renderAndWait();

			const bulletCheckbox = screen.getByTestId("bullet-checkbox-b-001");
			await user.click(bulletCheckbox);

			expect(bulletCheckbox).toHaveAttribute("data-state", "unchecked");
			// Parent job stays checked
			expect(screen.getByTestId("job-checkbox-wh-001")).toHaveAttribute(
				"data-state",
				"checked",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Education checkboxes
	// -----------------------------------------------------------------------

	describe("education selection", () => {
		it("renders a checkbox for each education entry", async () => {
			await renderAndWait();

			expect(
				screen.getByTestId("education-checkbox-edu-001"),
			).toBeInTheDocument();
			expect(
				screen.getByText("B.S. Computer Science — MIT"),
			).toBeInTheDocument();
		});

		it("all education entries are checked by default", async () => {
			await renderAndWait();

			expect(screen.getByTestId("education-checkbox-edu-001")).toHaveAttribute(
				"data-state",
				"checked",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Certification checkboxes
	// -----------------------------------------------------------------------

	describe("certification selection", () => {
		it("renders a checkbox for each certification", async () => {
			await renderAndWait();

			expect(
				screen.getByTestId("certification-checkbox-cert-001"),
			).toBeInTheDocument();
			expect(screen.getByText("AWS Solutions Architect")).toBeInTheDocument();
		});

		it("all certifications are checked by default", async () => {
			await renderAndWait();

			expect(
				screen.getByTestId("certification-checkbox-cert-001"),
			).toHaveAttribute("data-state", "checked");
		});
	});

	// -----------------------------------------------------------------------
	// Skills checkboxes
	// -----------------------------------------------------------------------

	describe("skills selection", () => {
		it("renders a checkbox for each skill", async () => {
			await renderAndWait();

			expect(screen.getByTestId("skill-checkbox-sk-001")).toBeInTheDocument();
			expect(screen.getByTestId("skill-checkbox-sk-002")).toBeInTheDocument();
			expect(screen.getByTestId("skill-checkbox-sk-003")).toBeInTheDocument();
		});

		it("all skills are checked by default", async () => {
			await renderAndWait();

			const skillCheckboxes = screen.getAllByTestId(/^skill-checkbox-/);
			for (const checkbox of skillCheckboxes) {
				expect(checkbox).toHaveAttribute("data-state", "checked");
			}
		});

		it("displays skill name and proficiency", async () => {
			await renderAndWait();

			expect(screen.getByText("TypeScript")).toBeInTheDocument();
			expect(screen.getByText("React")).toBeInTheDocument();
			expect(screen.getByText("Leadership")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Form submission
	// -----------------------------------------------------------------------

	describe("submission", () => {
		it("POSTs to /base-resumes with correct payload and completes onboarding", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					BASE_RESUMES_ENDPOINT,
					expect.objectContaining({
						persona_id: DEFAULT_PERSONA_ID,
						name: "Scrum Master Resume",
						role_type: "Scrum Master",
						summary: "Experienced agile leader with 8 years of experience",
						included_jobs: ["wh-001", "wh-002"],
						included_education: ["edu-001"],
						included_certifications: ["cert-001"],
						skills_emphasis: ["sk-001", "sk-002", "sk-003"],
					}),
				);
			});

			expect(mocks.mockCompleteOnboarding).toHaveBeenCalledTimes(1);
			expect(mocks.mockNext).not.toHaveBeenCalled();
		});

		it("includes job_bullet_selections in POST body", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					BASE_RESUMES_ENDPOINT,
					expect.objectContaining({
						job_bullet_selections: {
							"wh-001": ["b-001", "b-002"],
							"wh-002": ["b-003"],
						},
					}),
				);
			});
		});

		it("excludes unchecked items from POST body", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);

			const user = await renderAndWait();
			await fillRequiredFields(user);

			// Uncheck second job
			await user.click(screen.getByTestId("job-checkbox-wh-002"));
			// Uncheck first education
			await user.click(screen.getByTestId("education-checkbox-edu-001"));
			// Uncheck one skill
			await user.click(screen.getByTestId("skill-checkbox-sk-003"));

			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					BASE_RESUMES_ENDPOINT,
					expect.objectContaining({
						included_jobs: ["wh-001"],
						included_education: [],
						skills_emphasis: ["sk-001", "sk-002"],
					}),
				);
			});
		});

		it("shows error on failed POST", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/failed to save/i)).toBeInTheDocument();
			});

			expect(mocks.mockCompleteOnboarding).not.toHaveBeenCalled();
		});

		it("shows friendly error for duplicate name", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"DUPLICATE_NAME",
					"A base resume with this name already exists",
					409,
				),
			);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toHaveTextContent(
					/already exists/i,
				);
			});
		});

		it("disables submit button and shows Creating text while submitting", async () => {
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).toBeDisabled();
				expect(btn).toHaveTextContent("Creating...");
			});
		});

		it("re-enables submit button after failed submission", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("fail"));

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
				expect(btn).not.toBeDisabled();
				expect(btn).toHaveTextContent(/create resume/i);
			});
		});

		it("adds welcome system message after completion", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockAddSystemMessage).toHaveBeenCalledWith(
					"You're all set! I'm scanning for jobs now — I'll let you know what I find.",
				);
			});
		});

		it("redirects to dashboard after completion", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(mocks.mockRouterReplace).toHaveBeenCalledWith("/");
			});
		});

		it("shows error and re-enables button when completeOnboarding fails", async () => {
			mocks.mockApiPost.mockResolvedValueOnce(MOCK_BASE_RESUME_RESPONSE);
			mocks.mockCompleteOnboarding.mockRejectedValueOnce(
				new Error("Completion failed"),
			);

			const user = await renderAndWait();
			await fillRequiredFields(user);
			await user.click(screen.getByTestId(SUBMIT_BUTTON_TESTID));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});

			const btn = screen.getByTestId(SUBMIT_BUTTON_TESTID);
			expect(btn).not.toBeDisabled();
			expect(mocks.mockRouterReplace).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
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
		it("renders form with empty data when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderAndWait();

			expect(
				screen.getByRole("heading", { name: /base resume setup/i }),
			).toBeInTheDocument();
			expect(screen.getByLabelText(/^resume name$/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Empty persona data
	// -----------------------------------------------------------------------

	describe("empty data", () => {
		it("shows empty messages when no persona data exists", async () => {
			setupEmptyApiMocks();
			await renderAndWait();

			expect(screen.getByText(/no work history entries/i)).toBeInTheDocument();
			expect(screen.getByText(/no education entries/i)).toBeInTheDocument();
			expect(screen.getByText(/no certifications/i)).toBeInTheDocument();
			expect(screen.getByText(/no skills/i)).toBeInTheDocument();
		});
	});
});
