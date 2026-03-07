/**
 * Tests for CreateVariantCard component.
 *
 * REQ-027 §4.1–§4.3: Two variant creation paths —
 * "Draft Resume" (AI) and "Create Variant" (manual) with
 * base resume selection.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CreateVariantCard } from "./create-variant-card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_JOB_POSTING_ID = "00000000-0000-4000-a000-000000000010";
const MOCK_BASE_RESUME_ID = "00000000-0000-4000-a000-000000000020";
const MOCK_BASE_RESUME_ID_2 = "00000000-0000-4000-a000-000000000021";
const MOCK_VARIANT_ID = "00000000-0000-4000-a000-000000000030";
const MOCK_CREATED_AT = "2026-02-10T12:00:00Z";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMeta(total: number) {
	return { total, page: 1, per_page: 20 };
}

function makeResumesResponse(resumes: ReturnType<typeof makeBaseResume>[]) {
	return { data: resumes, meta: makeMeta(resumes.length) };
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeBaseResume(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_BASE_RESUME_ID,
		persona_id: "persona-1",
		name: "Software Engineer Resume",
		role_type: "Software Engineer",
		summary: "Experienced software engineer...",
		included_jobs: [],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: {},
		job_bullet_order: {},
		markdown_content: "# Software Engineer\n\nExperienced...",
		template_id: null,
		rendered_at: null,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
		...overrides,
	};
}

function makeVariantResponse() {
	return {
		data: {
			id: MOCK_VARIANT_ID,
			base_resume_id: MOCK_BASE_RESUME_ID,
			job_posting_id: MOCK_JOB_POSTING_ID,
			summary: "Variant of Software Engineer Resume for Scrum Master",
			job_bullet_order: {},
			modifications_description: null,
			status: "Draft",
			markdown_content: "# Software Engineer\n\nExperienced...",
			snapshot_markdown_content: null,
			snapshot_included_jobs: null,
			snapshot_job_bullet_selections: null,
			snapshot_included_education: null,
			snapshot_included_certifications: null,
			snapshot_skills_emphasis: null,
			agent_reasoning: null,
			guardrail_result: null,
			approved_at: null,
			archived_at: null,
			created_at: MOCK_CREATED_AT,
			updated_at: MOCK_CREATED_AT,
		},
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
		mockApiPost: vi.fn(),
		MockApiError,
		mockPush: vi.fn(),
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
	apiPost: mocks.mockApiPost,
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
	useParams: () => ({ id: MOCK_JOB_POSTING_ID }),
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

let queryClient: QueryClient;

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CreateVariantCard", () => {
	it("renders loading state while fetching base resumes", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		expect(screen.getByTestId("create-variant-loading")).toBeInTheDocument();
	});

	it("renders both creation buttons when base resumes exist", async () => {
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([makeBaseResume()]));

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("draft-resume-button")).toBeInTheDocument();
		});
		expect(screen.getByTestId("create-variant-button")).toBeInTheDocument();
	});

	it("shows empty state when no base resumes exist", async () => {
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([]));

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(
				screen.getByText(/create a base resume first/i),
			).toBeInTheDocument();
		});
	});

	it("shows resume selector when multiple resumes exist", async () => {
		mocks.mockApiGet.mockResolvedValue(
			makeResumesResponse([
				makeBaseResume(),
				makeBaseResume({
					id: MOCK_BASE_RESUME_ID_2,
					name: "Project Manager Resume",
					is_primary: false,
				}),
			]),
		);

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("resume-selector")).toBeInTheDocument();
		});
	});

	it("calls create-for-job API with manual method and navigates", async () => {
		const user = userEvent.setup();
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([makeBaseResume()]));
		mocks.mockApiPost.mockResolvedValue(makeVariantResponse());

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("create-variant-button")).toBeInTheDocument();
		});

		await user.click(screen.getByTestId("create-variant-button"));

		await waitFor(() => {
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/job-variants/create-for-job",
				{
					base_resume_id: MOCK_BASE_RESUME_ID,
					job_posting_id: MOCK_JOB_POSTING_ID,
					method: "manual",
				},
			);
		});

		await waitFor(() => {
			expect(mocks.mockPush).toHaveBeenCalledWith(
				`/resumes/${MOCK_BASE_RESUME_ID}/variants/${MOCK_VARIANT_ID}/edit`,
			);
		});
	});

	it("calls create-for-job API with ai method and navigates", async () => {
		const user = userEvent.setup();
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([makeBaseResume()]));
		mocks.mockApiPost.mockResolvedValue(makeVariantResponse());

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("draft-resume-button")).toBeInTheDocument();
		});

		await user.click(screen.getByTestId("draft-resume-button"));

		await waitFor(() => {
			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/job-variants/create-for-job",
				{
					base_resume_id: MOCK_BASE_RESUME_ID,
					job_posting_id: MOCK_JOB_POSTING_ID,
					method: "ai",
				},
			);
		});

		await waitFor(() => {
			expect(mocks.mockPush).toHaveBeenCalledWith(
				`/resumes/${MOCK_BASE_RESUME_ID}/variants/${MOCK_VARIANT_ID}/edit`,
			);
		});
	});

	it("shows error toast on API failure", async () => {
		const user = userEvent.setup();
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([makeBaseResume()]));
		mocks.mockApiPost.mockRejectedValue(new Error("Server error"));

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("create-variant-button")).toBeInTheDocument();
		});

		await user.click(screen.getByTestId("create-variant-button"));

		await waitFor(() => {
			expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
				"Failed to create variant.",
			);
		});
	});

	it("disables buttons while creating", async () => {
		const user = userEvent.setup();
		mocks.mockApiGet.mockResolvedValue(makeResumesResponse([makeBaseResume()]));
		mocks.mockApiPost.mockReturnValue(new Promise(() => {}));

		render(<CreateVariantCard jobPostingId={MOCK_JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByTestId("create-variant-button")).toBeInTheDocument();
		});

		await user.click(screen.getByTestId("create-variant-button"));

		await waitFor(() => {
			expect(screen.getByTestId("create-variant-button")).toBeDisabled();
			expect(screen.getByTestId("draft-resume-button")).toBeDisabled();
		});
	});
});
