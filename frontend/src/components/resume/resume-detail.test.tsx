/**
 * Tests for the ResumeDetail component (§8.2).
 *
 * REQ-012 §9.2: Resume detail page with summary editor
 * and job inclusion checkboxes (hierarchical checkbox tree).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOADING_TESTID = "loading-spinner";
const RESUME_NAME = "Scrum Master";
const ROLE_TYPE = "Scrum Master roles";
const SUMMARY_TEXT =
	"Experienced scrum master with 5 years of agile experience.";
const RESUME_API_PATH = "/base-resumes/r-1";
const WORK_HISTORY_API_PATH = "/personas/p-1/work-history";
const JOB_ID_INCLUDED = "wh-1";
const JOB_ID_EXCLUDED = "wh-2";
const INCLUDED_JOB_LABEL = /Senior Scrum Master.*Acme Corp/i;
const EXCLUDED_JOB_LABEL = /Project Manager.*TechCo/i;
const EDUCATION_API_PATH = "/personas/p-1/education";
const CERTIFICATIONS_API_PATH = "/personas/p-1/certifications";
const SKILLS_API_PATH = "/personas/p-1/skills";
const EDU_ID_INCLUDED = "ed-1";
const EDU_ID_EXCLUDED = "ed-2";
const CERT_ID_INCLUDED = "cert-1";
const CERT_ID_EXCLUDED = "cert-2";
const SKILL_ID_EMPHASIZED = "skill-1";
const SKILL_ID_NOT_EMPHASIZED = "skill-2";
const INCLUDED_EDU_LABEL = /MS Computer Science.*MIT/i;
const EXCLUDED_EDU_LABEL = /BS Mathematics.*Stanford/i;
const INCLUDED_CERT_LABEL = /CSM.*Scrum Alliance/i;
const EXCLUDED_CERT_LABEL = /PMP.*PMI/i;
const INCLUDED_SKILL_LABEL = "Agile";
const EXCLUDED_SKILL_LABEL = "Python";
const BULLET_TEXT_AGILE = "Led agile transformation";
const BULLET_TEXT_VARIANCE = "Reduced sprint velocity variance";
const RENDER_API_PATH = "/base-resumes/r-1/render";
const DOWNLOAD_URL = "http://localhost:8000/api/v1/base-resumes/r-1/download";
const RENDERED_AT_STALE = "2026-02-11T12:00:00Z";
const RENDERED_AT_CURRENT = "2026-02-12T14:00:00Z";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResume(overrides?: Record<string, unknown>) {
	return {
		id: "r-1",
		persona_id: "p-1",
		name: RESUME_NAME,
		role_type: ROLE_TYPE,
		summary: SUMMARY_TEXT,
		included_jobs: [JOB_ID_INCLUDED],
		included_education: [EDU_ID_INCLUDED],
		included_certifications: [CERT_ID_INCLUDED],
		skills_emphasis: [SKILL_ID_EMPHASIZED],
		job_bullet_selections: { [JOB_ID_INCLUDED]: ["b-1", "b-2"] },
		job_bullet_order: { [JOB_ID_INCLUDED]: ["b-1", "b-2", "b-3"] },
		rendered_at: null,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: "2026-02-10T12:00:00Z",
		updated_at: "2026-02-12T12:00:00Z",
		...overrides,
	};
}

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
		persona_id: "p-1",
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
		persona_id: "p-1",
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
		persona_id: "p-1",
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
		persona_id: "p-1",
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

const MOCK_RESUME_RESPONSE = {
	data: makeResume(),
};

const MOCK_WORK_HISTORY_RESPONSE = {
	data: [
		makeWorkHistory(JOB_ID_INCLUDED, {
			company_name: "Acme Corp",
			job_title: "Senior Scrum Master",
			bullets: [
				makeBullet("b-1", JOB_ID_INCLUDED, BULLET_TEXT_AGILE, 0),
				makeBullet("b-2", JOB_ID_INCLUDED, "Coached 3 scrum teams", 1),
				makeBullet("b-3", JOB_ID_INCLUDED, BULLET_TEXT_VARIANCE, 2),
			],
		}),
		makeWorkHistory(JOB_ID_EXCLUDED, {
			company_name: "TechCo",
			job_title: "Project Manager",
			is_current: false,
			end_date: "2020-12-31",
			display_order: 1,
			bullets: [
				makeBullet("b-4", JOB_ID_EXCLUDED, "Managed backlog refinement", 0),
			],
		}),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};

const MOCK_EDUCATION_RESPONSE = {
	data: [
		makeEducation(EDU_ID_INCLUDED, {
			institution: "MIT",
			degree: "MS",
			field_of_study: "Computer Science",
		}),
		makeEducation(EDU_ID_EXCLUDED, {
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
		makeCertification(CERT_ID_INCLUDED, {
			certification_name: "CSM",
			issuing_organization: "Scrum Alliance",
		}),
		makeCertification(CERT_ID_EXCLUDED, {
			certification_name: "PMP",
			issuing_organization: "PMI",
			display_order: 1,
		}),
	],
	meta: { total: 2, page: 1, per_page: 20, total_pages: 1 },
};

const MOCK_SKILLS_RESPONSE = {
	data: [
		makeSkill(SKILL_ID_EMPHASIZED, {
			skill_name: "Agile",
		}),
		makeSkill(SKILL_ID_NOT_EMPHASIZED, {
			skill_name: "Python",
			display_order: 1,
		}),
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
		mockApiPatch: vi.fn(),
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
	apiPatch: mocks.mockApiPatch,
	apiPost: mocks.mockApiPost,
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		label,
	}: {
		items: Array<{ id: string }>;
		renderItem: (item: { id: string }, handle: null) => ReactNode;
		label: string;
	}) => (
		<div data-testid="reorderable-list" aria-label={label}>
			{items.map((item: { id: string }) => (
				<div key={item.id}>{renderItem(item, null)}</div>
			))}
		</div>
	),
}));

vi.mock("@/components/ui/pdf-viewer", () => ({
	PdfViewer: ({ src, fileName }: { src: string | Blob; fileName: string }) => (
		<div
			data-testid="pdf-viewer"
			data-src={typeof src === "string" ? src : "blob"}
			data-filename={fileName}
		/>
	),
}));

import { ResumeDetail } from "./resume-detail";

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

function renderDetail(resumeId = "r-1", personaId = "p-1") {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<ResumeDetail resumeId={resumeId} personaId={personaId} />
		</Wrapper>,
	);
}

/**
 * Configure mockApiGet to return different responses based on path.
 * GET /base-resumes/r-1 → resume response,
 * GET /personas/p-1/work-history → work history response.
 */
function setupMockApi(
	resumeResponse: unknown = MOCK_RESUME_RESPONSE,
	workHistoryResponse: unknown = MOCK_WORK_HISTORY_RESPONSE,
	educationResponse: unknown = MOCK_EDUCATION_RESPONSE,
	certificationsResponse: unknown = MOCK_CERTIFICATIONS_RESPONSE,
	skillsResponse: unknown = MOCK_SKILLS_RESPONSE,
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === RESUME_API_PATH) return Promise.resolve(resumeResponse);
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
	mocks.mockApiPatch.mockReset();
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

describe("ResumeDetail", () => {
	describe("loading state", () => {
		it("shows loading spinner initially", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderDetail();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NOT_FOUND", "Resume not found", 404),
			);
			renderDetail();
			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("header", () => {
		it("renders resume name as heading", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("heading", { name: RESUME_NAME }),
				).toBeInTheDocument();
			});
		});

		it("renders role type", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(ROLE_TYPE)).toBeInTheDocument();
			});
		});

		it("renders back link to /resumes", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("link", { name: /back to resumes/i }),
				).toHaveAttribute("href", "/resumes");
			});
		});
	});

	describe("summary editor", () => {
		it("displays current summary in textarea", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				const textarea = screen.getByRole("textbox", {
					name: /summary/i,
				});
				expect(textarea).toHaveValue(SUMMARY_TEXT);
			});
		});

		it("allows editing the summary", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("textbox", { name: /summary/i }),
				).toBeInTheDocument();
			});

			const textarea = screen.getByRole("textbox", { name: /summary/i });
			await user.clear(textarea);
			await user.type(textarea, "New summary");
			expect(textarea).toHaveValue("New summary");
		});
	});

	describe("job inclusion checkboxes", () => {
		it("renders job entries with title and company", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: INCLUDED_JOB_LABEL,
					}),
				).toBeInTheDocument();
			});
			expect(
				screen.getByRole("checkbox", {
					name: EXCLUDED_JOB_LABEL,
				}),
			).toBeInTheDocument();
		});

		it("shows included job as checked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: INCLUDED_JOB_LABEL,
					}),
				).toBeChecked();
			});
		});

		it("shows excluded job as unchecked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: EXCLUDED_JOB_LABEL,
					}),
				).not.toBeChecked();
			});
		});

		it("shows bullet checkboxes for included job", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(BULLET_TEXT_AGILE)).toBeInTheDocument();
			});
			expect(screen.getByText("Coached 3 scrum teams")).toBeInTheDocument();
			expect(screen.getByText(BULLET_TEXT_VARIANCE)).toBeInTheDocument();
		});

		it("hides bullets for excluded job", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME)).toBeInTheDocument();
			});
			expect(
				screen.queryByText("Managed backlog refinement"),
			).not.toBeInTheDocument();
		});

		it("shows selected bullet as checked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: new RegExp(BULLET_TEXT_AGILE, "i"),
					}),
				).toBeChecked();
			});
		});

		it("shows unselected bullet as unchecked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: new RegExp(BULLET_TEXT_VARIANCE, "i"),
					}),
				).not.toBeChecked();
			});
		});

		it("unchecks a bullet when its checkbox is clicked", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: new RegExp(BULLET_TEXT_AGILE, "i"),
					}),
				).toBeChecked();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: new RegExp(BULLET_TEXT_AGILE, "i"),
				}),
			);

			expect(
				screen.getByRole("checkbox", {
					name: new RegExp(BULLET_TEXT_AGILE, "i"),
				}),
			).not.toBeChecked();
		});

		it("hides bullets when an included job is unchecked", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(screen.getByText(BULLET_TEXT_AGILE)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: INCLUDED_JOB_LABEL,
				}),
			);

			expect(screen.queryByText(BULLET_TEXT_AGILE)).not.toBeInTheDocument();
		});

		it("auto-selects all bullets when a job is included", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({
				data: makeResume({
					included_jobs: [JOB_ID_INCLUDED, JOB_ID_EXCLUDED],
				}),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: EXCLUDED_JOB_LABEL,
					}),
				).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: EXCLUDED_JOB_LABEL,
				}),
			);

			// After toggling on, the excluded job's bullet should appear and be checked
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: /Managed backlog refinement/i,
					}),
				).toBeChecked();
			});
		});
	});

	describe("save", () => {
		it("sends PATCH with updated summary on save", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({
				data: makeResume({ summary: "Updated summary" }),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("textbox", { name: /summary/i }),
				).toBeInTheDocument();
			});

			const textarea = screen.getByRole("textbox", {
				name: /summary/i,
			});
			await user.clear(textarea);
			await user.type(textarea, "Updated summary");
			await user.click(screen.getByRole("button", { name: /save/i }));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				RESUME_API_PATH,
				expect.objectContaining({ summary: "Updated summary" }),
			);
		});

		it("sends PATCH with toggled job inclusion on save", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({
				data: makeResume({
					included_jobs: [JOB_ID_INCLUDED, JOB_ID_EXCLUDED],
				}),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", {
						name: EXCLUDED_JOB_LABEL,
					}),
				).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: EXCLUDED_JOB_LABEL,
				}),
			);
			await user.click(screen.getByRole("button", { name: /save/i }));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				RESUME_API_PATH,
				expect.objectContaining({
					included_jobs: expect.arrayContaining([
						JOB_ID_INCLUDED,
						JOB_ID_EXCLUDED,
					]),
				}),
			);
		});

		it("shows success toast on save", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({
				data: makeResume(),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /save/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("shows error toast on save failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("VALIDATION_ERROR", "Invalid data", 422),
			);
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /save/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	describe("bullet reordering", () => {
		it("renders reorderable list for included job bullets", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("reorderable-list")).toBeInTheDocument();
			});
		});

		it("sends job_bullet_order in PATCH on save", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: makeResume() });
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /save/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				RESUME_API_PATH,
				expect.objectContaining({
					job_bullet_order: {
						[JOB_ID_INCLUDED]: ["b-1", "b-2", "b-3"],
					},
				}),
			);
		});
	});

	describe("education checkboxes", () => {
		it("renders education entries with checkboxes", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_EDU_LABEL }),
				).toBeInTheDocument();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
			).toBeInTheDocument();
		});

		it("shows included education as checked and excluded as unchecked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_EDU_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
			).not.toBeChecked();
		});

		it("toggles education checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
				).not.toBeChecked();
			});

			await user.click(
				screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
			);

			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
			).toBeChecked();
		});

		it("checks all education when included_education is null", async () => {
			setupMockApi({ data: makeResume({ included_education: null }) });
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_EDU_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_EDU_LABEL }),
			).toBeChecked();
		});
	});

	describe("certification checkboxes", () => {
		it("renders certification entries with checkboxes", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_CERT_LABEL }),
				).toBeInTheDocument();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
			).toBeInTheDocument();
		});

		it("shows included certification as checked and excluded as unchecked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_CERT_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
			).not.toBeChecked();
		});

		it("toggles certification checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
				).not.toBeChecked();
			});

			await user.click(
				screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
			);

			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
			).toBeChecked();
		});

		it("checks all certifications when included_certifications is null", async () => {
			setupMockApi({
				data: makeResume({ included_certifications: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_CERT_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_CERT_LABEL }),
			).toBeChecked();
		});
	});

	describe("skills emphasis checkboxes", () => {
		it("renders skill entries with checkboxes", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_SKILL_LABEL }),
				).toBeInTheDocument();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
			).toBeInTheDocument();
		});

		it("shows emphasized skill as checked and non-emphasized as unchecked", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_SKILL_LABEL }),
				).toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
			).not.toBeChecked();
		});

		it("toggles skill checkbox on click", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
				).not.toBeChecked();
			});

			await user.click(
				screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
			);

			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
			).toBeChecked();
		});

		it("checks no skills when skills_emphasis is null", async () => {
			setupMockApi({ data: makeResume({ skills_emphasis: null }) });
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: INCLUDED_SKILL_LABEL }),
				).not.toBeChecked();
			});
			expect(
				screen.getByRole("checkbox", { name: EXCLUDED_SKILL_LABEL }),
			).not.toBeChecked();
		});
	});

	describe("save with all fields", () => {
		it("sends education, certifications, skills, and bullet order in PATCH", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: makeResume() });
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /save/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /save/i }));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				RESUME_API_PATH,
				expect.objectContaining({
					included_education: [EDU_ID_INCLUDED],
					included_certifications: [CERT_ID_INCLUDED],
					skills_emphasis: [SKILL_ID_EMPHASIZED],
					job_bullet_order: {
						[JOB_ID_INCLUDED]: ["b-1", "b-2", "b-3"],
					},
				}),
			);
		});
	});

	describe("API calls", () => {
		it("fetches resume from /base-resumes/{id}", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(RESUME_API_PATH);
			});
		});

		it("fetches work history from /personas/{personaId}/work-history", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(WORK_HISTORY_API_PATH);
			});
		});

		it("fetches education from /personas/{personaId}/education", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(EDUCATION_API_PATH);
			});
		});

		it("fetches certifications from /personas/{personaId}/certifications", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(CERTIFICATIONS_API_PATH);
			});
		});

		it("fetches skills from /personas/{personaId}/skills", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(SKILLS_API_PATH);
			});
		});
	});

	describe("render PDF button", () => {
		it("shows Render PDF button when rendered_at is null", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /render pdf/i }),
				).toBeInTheDocument();
			});
		});

		it("shows Re-render PDF button when content changed after last render", async () => {
			setupMockApi({
				data: makeResume({ rendered_at: RENDERED_AT_STALE }),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /re-render pdf/i }),
				).toBeInTheDocument();
			});
		});

		it("hides render button when PDF is up to date", async () => {
			setupMockApi({
				data: makeResume({ rendered_at: RENDERED_AT_CURRENT }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: /render pdf/i }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: /re-render pdf/i }),
			).not.toBeInTheDocument();
		});

		it("calls POST /base-resumes/{id}/render on click", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue({
				data: makeResume({ rendered_at: RENDERED_AT_CURRENT }),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /render pdf/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /render pdf/i }));

			expect(mocks.mockApiPost).toHaveBeenCalledWith(RENDER_API_PATH);
		});

		it("shows success toast after render completes", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValue({
				data: makeResume({ rendered_at: RENDERED_AT_CURRENT }),
			});
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /render pdf/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /render pdf/i }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					expect.stringMatching(/pdf rendered/i),
				);
			});
		});

		it("shows error toast on render failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Render failed", 500),
			);
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /render pdf/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /render pdf/i }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});

		it("disables button during rendering", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /render pdf/i }),
				).toBeInTheDocument();
			});

			await user.click(screen.getByRole("button", { name: /render pdf/i }));

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /rendering/i }),
				).toBeDisabled();
			});
		});
	});

	describe("status display", () => {
		it("shows Active status badge", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText("Active")).toBeInTheDocument();
			});
		});

		it("shows Archived status badge", async () => {
			setupMockApi({
				data: makeResume({ status: "Archived" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText("Archived")).toBeInTheDocument();
			});
		});
	});

	describe("PDF preview", () => {
		it("shows PDF viewer when rendered_at is not null", async () => {
			setupMockApi({
				data: makeResume({ rendered_at: RENDERED_AT_CURRENT }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pdf-viewer")).toBeInTheDocument();
			});
		});

		it("does not show PDF viewer when rendered_at is null", async () => {
			setupMockApi();
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(RESUME_NAME)).toBeInTheDocument();
			});
			expect(screen.queryByTestId("pdf-viewer")).not.toBeInTheDocument();
		});

		it("passes download URL and file name to PdfViewer", async () => {
			setupMockApi({
				data: makeResume({ rendered_at: RENDERED_AT_CURRENT }),
			});
			renderDetail();
			await waitFor(() => {
				const viewer = screen.getByTestId("pdf-viewer");
				expect(viewer).toHaveAttribute("data-src", DOWNLOAD_URL);
				expect(viewer).toHaveAttribute("data-filename", "Scrum Master.pdf");
			});
		});
	});
});
