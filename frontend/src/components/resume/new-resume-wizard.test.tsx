/**
 * Tests for the NewResumeWizard component (§8.8).
 *
 * REQ-012 §9.2, §6.3.12: New resume creation form with persona item
 * selection — name, role type, summary, job/bullet checkboxes,
 * education/certification/skill checkboxes, POST to /base-resumes.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WIZARD_TESTID = "new-resume-wizard";
const LOADING_TESTID = "loading-spinner";
const PERSONA_ID = "p-1";
const WORK_HISTORY_API_PATH = "/personas/p-1/work-history";
const EDUCATION_API_PATH = "/personas/p-1/education";
const CERTIFICATIONS_API_PATH = "/personas/p-1/certifications";
const SKILLS_API_PATH = "/personas/p-1/skills";
const CREATE_API_PATH = "/base-resumes";
const JOB_ID_1 = "wh-1";
const JOB_ID_2 = "wh-2";
const JOB_1_LABEL = /Senior Scrum Master.*Acme Corp/i;
const JOB_2_LABEL = /Project Manager.*TechCo/i;
const EDU_ID_1 = "ed-1";
const EDU_ID_2 = "ed-2";
const EDU_1_LABEL = /MS Computer Science.*MIT/i;
const EDU_2_LABEL = /BS Mathematics.*Stanford/i;
const CERT_ID_1 = "cert-1";
const CERT_ID_2 = "cert-2";
const CERT_1_LABEL = /CSM.*Scrum Alliance/i;
const CERT_2_LABEL = /PMP.*PMI/i;
const SKILL_ID_1 = "skill-1";
const SKILL_ID_2 = "skill-2";
const SKILL_1_LABEL = "Agile";
const SKILL_2_LABEL = "Python";
const BULLET_TEXT_AGILE = "Led agile transformation";
const BULLET_TEXT_BACKLOG = "Managed backlog refinement";
const CREATED_RESUME_ID = "r-new-1";

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeBullet(
	id: string,
	workHistoryId: string,
	text: string,
	order: number,
) {
	return {
		id,
		work_history_id: workHistoryId,
		text,
		skills_demonstrated: [],
		metrics: null,
		display_order: order,
	};
}

function makeWorkHistory(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: PERSONA_ID,
		company_name: `Company ${id}`,
		company_industry: "Tech",
		job_title: `Job Title ${id}`,
		start_date: "2021-01-01",
		end_date: null,
		is_current: true,
		location: "Remote",
		work_model: "Remote" as const,
		description: null,
		display_order: 0,
		bullets: [],
		...overrides,
	};
}

function makeEducation(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: PERSONA_ID,
		institution: `University ${id}`,
		degree: `Degree ${id}`,
		field_of_study: `Field ${id}`,
		graduation_year: 2020,
		gpa: null,
		honors: null,
		display_order: 0,
		...overrides,
	};
}

function makeCertification(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: PERSONA_ID,
		certification_name: `Cert ${id}`,
		issuing_organization: `Org ${id}`,
		date_obtained: "2021-06-01",
		expiration_date: null,
		credential_id: null,
		verification_url: null,
		display_order: 0,
		...overrides,
	};
}

function makeSkill(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		persona_id: PERSONA_ID,
		skill_name: `Skill ${id}`,
		skill_type: "Hard" as const,
		category: "Technical",
		proficiency: "Proficient" as const,
		years_used: 5,
		last_used: "Current",
		display_order: 0,
		...overrides,
	};
}

const MOCK_WORK_HISTORY_RESPONSE = {
	data: [
		makeWorkHistory(JOB_ID_1, {
			company_name: "Acme Corp",
			job_title: "Senior Scrum Master",
			bullets: [
				makeBullet("b-1", JOB_ID_1, BULLET_TEXT_AGILE, 0),
				makeBullet("b-2", JOB_ID_1, "Coached 3 scrum teams", 1),
			],
		}),
		makeWorkHistory(JOB_ID_2, {
			company_name: "TechCo",
			job_title: "Project Manager",
			is_current: false,
			end_date: "2020-12-31",
			display_order: 1,
			bullets: [makeBullet("b-3", JOB_ID_2, BULLET_TEXT_BACKLOG, 0)],
		}),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};

const MOCK_EDUCATION_RESPONSE = {
	data: [
		makeEducation(EDU_ID_1, {
			institution: "MIT",
			degree: "MS",
			field_of_study: "Computer Science",
		}),
		makeEducation(EDU_ID_2, {
			institution: "Stanford",
			degree: "BS",
			field_of_study: "Mathematics",
			display_order: 1,
		}),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};

const MOCK_CERTIFICATIONS_RESPONSE = {
	data: [
		makeCertification(CERT_ID_1, {
			certification_name: "CSM",
			issuing_organization: "Scrum Alliance",
		}),
		makeCertification(CERT_ID_2, {
			certification_name: "PMP",
			issuing_organization: "PMI",
			display_order: 1,
		}),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};

const MOCK_SKILLS_RESPONSE = {
	data: [
		makeSkill(SKILL_ID_1, { skill_name: "Agile" }),
		makeSkill(SKILL_ID_2, { skill_name: "Python", display_order: 1 }),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
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
		mockApiPost: vi.fn(),
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
	apiPost: mocks.mockApiPost,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

import { NewResumeWizard } from "./new-resume-wizard";

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

function renderWizard(personaId = PERSONA_ID) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<NewResumeWizard personaId={personaId} />
		</Wrapper>,
	);
}

function setupMockApi(
	workHistoryResponse: unknown = MOCK_WORK_HISTORY_RESPONSE,
	educationResponse: unknown = MOCK_EDUCATION_RESPONSE,
	certificationsResponse: unknown = MOCK_CERTIFICATIONS_RESPONSE,
	skillsResponse: unknown = MOCK_SKILLS_RESPONSE,
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === WORK_HISTORY_API_PATH)
			return Promise.resolve(workHistoryResponse);
		if (path === EDUCATION_API_PATH) return Promise.resolve(educationResponse);
		if (path === CERTIFICATIONS_API_PATH)
			return Promise.resolve(certificationsResponse);
		if (path === SKILLS_API_PATH) return Promise.resolve(skillsResponse);
		return Promise.resolve({ data: [] });
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPost.mockReset();
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

describe("NewResumeWizard", () => {
	describe("loading state", () => {
		it("shows loading spinner while persona data loads", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderWizard();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderWizard();
			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("header", () => {
		it("renders New Resume heading", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: /new resume/i }),
				).toBeInTheDocument();
			});
		});

		it("renders back link to /resumes", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("link", { name: /back to resumes/i }),
				).toHaveAttribute("href", "/resumes");
			});
		});
	});

	describe("name input", () => {
		it("renders empty name input", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toHaveValue("");
			});
		});

		it("allows typing a resume name", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});
			await user.type(screen.getByLabelText(/name/i), "Scrum Master");
			expect(screen.getByLabelText(/name/i)).toHaveValue("Scrum Master");
		});
	});

	describe("role type input", () => {
		it("renders empty role type input", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/role type/i)).toHaveValue("");
			});
		});
	});

	describe("summary textarea", () => {
		it("renders empty summary textarea", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByRole("textbox", { name: /summary/i })).toHaveValue(
					"",
				);
			});
		});
	});

	describe("job checkboxes", () => {
		it("renders job entries unchecked by default", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: JOB_1_LABEL }),
				).not.toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: JOB_2_LABEL }),
			).not.toBeChecked();
		});

		it("hides bullets when job is unchecked", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByTestId(WIZARD_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByText(BULLET_TEXT_AGILE)).not.toBeInTheDocument();
		});

		it("shows bullets when a job is checked and auto-selects all", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: JOB_1_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("checkbox", { name: JOB_1_LABEL }));
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: new RegExp(BULLET_TEXT_AGILE, "i"),
					}),
				).toBeChecked();
			});
		});

		it("hides bullets when a checked job is unchecked", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: JOB_1_LABEL }),
				).toBeInTheDocument();
			});
			// Check the job
			await user.click(screen.getByRole("checkbox", { name: JOB_1_LABEL }));
			await waitFor(() => {
				expect(screen.getByText(BULLET_TEXT_AGILE)).toBeInTheDocument();
			});
			// Uncheck the job
			await user.click(screen.getByRole("checkbox", { name: JOB_1_LABEL }));
			expect(screen.queryByText(BULLET_TEXT_AGILE)).not.toBeInTheDocument();
		});
	});

	describe("education checkboxes", () => {
		it("defaults all education checked", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: EDU_1_LABEL }),
				).toBeChecked();
			});
			expect(screen.getByRole("checkbox", { name: EDU_2_LABEL })).toBeChecked();
		});

		it("toggles education checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: EDU_1_LABEL }),
				).toBeChecked();
			});
			await user.click(screen.getByRole("checkbox", { name: EDU_1_LABEL }));
			expect(
				screen.getByRole("checkbox", { name: EDU_1_LABEL }),
			).not.toBeChecked();
		});
	});

	describe("certification checkboxes", () => {
		it("defaults all certifications checked", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: CERT_1_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: CERT_2_LABEL }),
			).toBeChecked();
		});

		it("toggles certification checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: CERT_1_LABEL }),
				).toBeChecked();
			});
			await user.click(screen.getByRole("checkbox", { name: CERT_1_LABEL }));
			expect(
				screen.getByRole("checkbox", { name: CERT_1_LABEL }),
			).not.toBeChecked();
		});
	});

	describe("skills emphasis checkboxes", () => {
		it("defaults all skills unchecked", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SKILL_1_LABEL }),
				).not.toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: SKILL_2_LABEL }),
			).not.toBeChecked();
		});

		it("toggles skill checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: SKILL_1_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("checkbox", { name: SKILL_1_LABEL }));
			expect(
				screen.getByRole("checkbox", { name: SKILL_1_LABEL }),
			).toBeChecked();
		});
	});

	describe("form submission", () => {
		async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
			await user.type(screen.getByLabelText(/name/i), "Scrum Master");
			await user.type(
				screen.getByLabelText(/role type/i),
				"Scrum Master roles",
			);
			await user.type(
				screen.getByRole("textbox", { name: /summary/i }),
				"Professional summary.",
			);
			await user.click(screen.getByRole("button", { name: /create resume/i }));
		}

		it("sends POST with form data on submit", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue({
				data: { id: CREATED_RESUME_ID },
			});
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});

			await fillAndSubmit(user);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					CREATE_API_PATH,
					expect.objectContaining({
						persona_id: PERSONA_ID,
						name: "Scrum Master",
						role_type: "Scrum Master roles",
						summary: "Professional summary.",
					}),
				);
			});
		});

		it("includes selected education and certifications in POST", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue({
				data: { id: CREATED_RESUME_ID },
			});
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});

			await fillAndSubmit(user);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					CREATE_API_PATH,
					expect.objectContaining({
						included_education: expect.arrayContaining([EDU_ID_1, EDU_ID_2]),
						included_certifications: expect.arrayContaining([
							CERT_ID_1,
							CERT_ID_2,
						]),
					}),
				);
			});
		});

		it("shows success toast and navigates to new resume on success", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue({
				data: { id: CREATED_RESUME_ID },
			});
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});

			await fillAndSubmit(user);

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
			expect(mocks.mockPush).toHaveBeenCalledWith(
				`/resumes/${CREATED_RESUME_ID}`,
			);
		});

		it("shows error toast on submit failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("DUPLICATE_NAME", "Name taken", 409),
			);
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});

			await fillAndSubmit(user);

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});

		it("disables submit button while creating", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
			});

			await fillAndSubmit(user);

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /creating/i }),
				).toBeDisabled();
			});
		});

		it("disables submit when required fields are empty", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /create resume/i }),
				).toBeInTheDocument();
			});
			expect(
				screen.getByRole("button", { name: /create resume/i }),
			).toBeDisabled();
		});
	});

	describe("API calls", () => {
		it("fetches work history from /personas/{personaId}/work-history", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(WORK_HISTORY_API_PATH);
			});
		});

		it("fetches education from /personas/{personaId}/education", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(EDUCATION_API_PATH);
			});
		});

		it("fetches certifications from /personas/{personaId}/certifications", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(CERTIFICATIONS_API_PATH);
			});
		});

		it("fetches skills from /personas/{personaId}/skills", async () => {
			setupMockApi();
			renderWizard();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(SKILLS_API_PATH);
			});
		});
	});
});
