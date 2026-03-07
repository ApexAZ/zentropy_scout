/**
 * Tests for VariantEditPage route.
 *
 * REQ-027 §3.5, §4.3–§4.4: Variant editor with TipTap and
 * job requirements panel. Navigated to after variant creation.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import VariantEditPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_BASE_RESUME_ID = "00000000-0000-4000-a000-000000000020";
const MOCK_VARIANT_ID = "00000000-0000-4000-a000-000000000030";
const MOCK_JOB_POSTING_ID = "00000000-0000-4000-a000-000000000010";
const MOCK_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const MOCK_CREATED_AT = "2026-02-10T12:00:00Z";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeVariant(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_VARIANT_ID,
		base_resume_id: MOCK_BASE_RESUME_ID,
		job_posting_id: MOCK_JOB_POSTING_ID,
		summary: "Variant of SE Resume for Scrum Master",
		job_bullet_order: {},
		modifications_description: null,
		status: "Draft",
		markdown_content: "# Software Engineer\n\nExperienced developer...",
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
		...overrides,
	};
}

function makeBaseResume() {
	return {
		id: MOCK_BASE_RESUME_ID,
		persona_id: MOCK_PERSONA_ID,
		name: "SE Resume",
		role_type: "Software Engineer",
		summary: "Experienced developer...",
		included_jobs: [],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: {},
		job_bullet_order: {},
		markdown_content: "# Software Engineer\n\nBase content...",
		template_id: null,
		rendered_at: null,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: MOCK_CREATED_AT,
		updated_at: MOCK_CREATED_AT,
	};
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupApiMocks(variantOverrides?: Record<string, unknown>) {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url.includes("/job-variants/")) {
			return Promise.resolve({ data: makeVariant(variantOverrides) });
		}
		if (url.includes("/base-resumes/")) {
			return Promise.resolve({ data: makeBaseResume() });
		}
		return Promise.resolve({
			data: [],
			meta: { total: 0, page: 1, per_page: 20 },
		});
	});
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
		mockApiPatch: vi.fn(),
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
	apiPost: vi.fn(),
	apiPatch: mocks.mockApiPatch,
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
	useParams: () => ({
		id: MOCK_BASE_RESUME_ID,
		variantId: MOCK_VARIANT_ID,
	}),
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: () => ({
		status: "onboarded",
		persona: { id: MOCK_PERSONA_ID },
	}),
}));

vi.mock("@/components/editor/resume-editor", () => ({
	ResumeEditor: ({
		initialContent,
		editable,
	}: {
		initialContent?: string;
		editable?: boolean;
	}) => (
		<div
			data-testid="resume-editor"
			data-editable={editable}
			data-content={initialContent}
		/>
	),
}));

vi.mock("@/components/editor/job-requirements-panel", () => ({
	JobRequirementsPanel: ({ jobPostingId }: { jobPostingId: string }) => (
		<div
			data-testid="job-requirements-panel"
			data-job-posting-id={jobPostingId}
		/>
	),
}));

vi.mock("@/components/editor/persona-reference-panel", () => ({
	PersonaReferencePanel: ({ personaId }: { personaId: string }) => (
		<div data-testid="persona-reference-panel" data-persona-id={personaId} />
	),
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

describe("VariantEditPage", () => {
	it("renders loading state while fetching variant", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		render(<VariantEditPage />, { wrapper: Wrapper });

		expect(screen.getByTestId("variant-edit-loading")).toBeInTheDocument();
	});

	it("renders editor with variant markdown content", async () => {
		setupApiMocks();

		render(<VariantEditPage />, { wrapper: Wrapper });

		await waitFor(() => {
			expect(screen.getByTestId("resume-editor")).toBeInTheDocument();
		});

		const editor = screen.getByTestId("resume-editor");
		expect(editor).toHaveAttribute("data-editable", "true");
		expect(editor).toHaveAttribute(
			"data-content",
			"# Software Engineer\n\nExperienced developer...",
		);
	});

	it("renders job requirements panel with correct job posting ID", async () => {
		setupApiMocks();

		render(<VariantEditPage />, { wrapper: Wrapper });

		await waitFor(() => {
			expect(screen.getByTestId("job-requirements-panel")).toBeInTheDocument();
		});

		expect(screen.getByTestId("job-requirements-panel")).toHaveAttribute(
			"data-job-posting-id",
			MOCK_JOB_POSTING_ID,
		);
	});

	it("renders persona reference panel with correct persona ID", async () => {
		setupApiMocks();

		render(<VariantEditPage />, { wrapper: Wrapper });

		await waitFor(() => {
			expect(screen.getByTestId("persona-reference-panel")).toBeInTheDocument();
		});

		expect(screen.getByTestId("persona-reference-panel")).toHaveAttribute(
			"data-persona-id",
			MOCK_PERSONA_ID,
		);
	});

	it("renders read-only editor for approved variants", async () => {
		setupApiMocks({ status: "Approved" });

		render(<VariantEditPage />, { wrapper: Wrapper });

		await waitFor(() => {
			expect(screen.getByTestId("resume-editor")).toBeInTheDocument();
		});

		expect(screen.getByTestId("resume-editor")).toHaveAttribute(
			"data-editable",
			"false",
		);
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockApiGet.mockRejectedValue(new Error("Network error"));

		render(<VariantEditPage />, { wrapper: Wrapper });

		await waitFor(() => {
			expect(screen.getByRole("alert")).toBeInTheDocument();
		});
	});
});
