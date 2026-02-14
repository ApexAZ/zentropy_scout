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
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: { [JOB_ID_INCLUDED]: ["b-1", "b-2"] },
		job_bullet_order: {},
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

const MOCK_RESUME_RESPONSE = {
	data: makeResume(),
};

const MOCK_WORK_HISTORY_RESPONSE = {
	data: [
		makeWorkHistory(JOB_ID_INCLUDED, {
			company_name: "Acme Corp",
			job_title: "Senior Scrum Master",
			bullets: [
				makeBullet("b-1", JOB_ID_INCLUDED, "Led agile transformation", 0),
				makeBullet("b-2", JOB_ID_INCLUDED, "Coached 3 scrum teams", 1),
				makeBullet(
					"b-3",
					JOB_ID_INCLUDED,
					"Reduced sprint velocity variance",
					2,
				),
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
		mockPush: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
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
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === RESUME_API_PATH) return Promise.resolve(resumeResponse);
		if (path === WORK_HISTORY_API_PATH)
			return Promise.resolve(workHistoryResponse);
		return Promise.resolve({ data: [] });
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
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
				expect(
					screen.getByText("Led agile transformation"),
				).toBeInTheDocument();
			});
			expect(screen.getByText("Coached 3 scrum teams")).toBeInTheDocument();
			expect(
				screen.getByText("Reduced sprint velocity variance"),
			).toBeInTheDocument();
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
						name: /Led agile transformation/i,
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
						name: /Reduced sprint velocity variance/i,
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
						name: /Led agile transformation/i,
					}),
				).toBeChecked();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: /Led agile transformation/i,
				}),
			);

			expect(
				screen.getByRole("checkbox", {
					name: /Led agile transformation/i,
				}),
			).not.toBeChecked();
		});

		it("hides bullets when an included job is unchecked", async () => {
			const user = userEvent.setup();
			setupMockApi();
			renderDetail();

			await waitFor(() => {
				expect(
					screen.getByText("Led agile transformation"),
				).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("checkbox", {
					name: INCLUDED_JOB_LABEL,
				}),
			);

			expect(
				screen.queryByText("Led agile transformation"),
			).not.toBeInTheDocument();
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
	});
});
