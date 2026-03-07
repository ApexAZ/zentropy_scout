/**
 * Tests for JobRequirementsPanel component.
 *
 * REQ-027 §4.4: Job requirements panel showing key skills, fit score,
 * and job context when editing a job variant.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JobRequirementsPanel } from "./job-requirements-panel";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const JOB_POSTING_ID = "00000000-0000-4000-a000-000000000010";
const PERSONA_JOB_ID = "00000000-0000-4000-a000-000000000020";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makePersonaJobResponse(overrides?: Record<string, unknown>) {
	return {
		id: PERSONA_JOB_ID,
		job: {
			id: JOB_POSTING_ID,
			source_id: null,
			external_id: null,
			job_title: "Scrum Master",
			company_name: "Acme Corp",
			company_url: null,
			source_url: null,
			apply_url: null,
			location: "Seattle, WA",
			work_model: "Hybrid",
			seniority_level: "Senior",
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			description: "We are looking for a Scrum Master...",
			culture_text: null,
			requirements: "SAFe certification required. 5+ years experience.",
			years_experience_min: 5,
			years_experience_max: null,
			posted_date: "2026-02-01",
			application_deadline: null,
			first_seen_date: "2026-02-01",
			last_verified_at: null,
			expired_at: null,
			ghost_signals: null,
			ghost_score: 0,
			description_hash: "abc123",
			repost_count: 0,
			previous_posting_ids: null,
			is_active: true,
		},
		status: "Discovered",
		is_favorite: false,
		discovery_method: "manual",
		discovered_at: "2026-02-01T00:00:00Z",
		fit_score: 87,
		stretch_score: 45,
		score_details: null,
		failed_non_negotiables: null,
		scored_at: "2026-02-01T00:00:00Z",
		dismissed_at: null,
		...overrides,
	};
}

function makeExtractedSkills() {
	return [
		{
			id: "sk-001",
			job_posting_id: JOB_POSTING_ID,
			skill_name: "SAFe Certification",
			skill_type: "Hard" as const,
			is_required: true,
			years_requested: null,
		},
		{
			id: "sk-002",
			job_posting_id: JOB_POSTING_ID,
			skill_name: "CI/CD Pipelines",
			skill_type: "Hard" as const,
			is_required: true,
			years_requested: 3,
		},
		{
			id: "sk-003",
			job_posting_id: JOB_POSTING_ID,
			skill_name: "Team Leadership",
			skill_type: "Soft" as const,
			is_required: false,
			years_requested: null,
		},
	];
}

const EMPTY_SKILLS_RESPONSE = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
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
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: vi.fn(),
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
	ApiError: mocks.MockApiError,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupApiMocks(options?: {
	personaJob?: ReturnType<typeof makePersonaJobResponse>;
	skills?: ReturnType<typeof makeExtractedSkills>;
}) {
	mocks.mockApiGet.mockImplementation((url: string) => {
		if (url.includes("/extracted-skills")) {
			return Promise.resolve(
				options?.skills
					? {
							data: options.skills,
							meta: { total: options.skills.length, page: 1, per_page: 20 },
						}
					: EMPTY_SKILLS_RESPONSE,
			);
		}
		return Promise.resolve({
			data: options?.personaJob ?? makePersonaJobResponse(),
		});
	});
}

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

describe("JobRequirementsPanel", () => {
	it("renders loading state while fetching data", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		expect(screen.getByTestId("job-requirements-loading")).toBeInTheDocument();
	});

	it("renders job title and company name", async () => {
		setupApiMocks();

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByText("Scrum Master")).toBeInTheDocument();
		});
		expect(screen.getByText("at Acme Corp")).toBeInTheDocument();
	});

	it("renders extracted skills grouped by required/preferred", async () => {
		setupApiMocks({ skills: makeExtractedSkills() });

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByText("SAFe Certification")).toBeInTheDocument();
		});
		expect(screen.getByText("CI/CD Pipelines (3+ yr)")).toBeInTheDocument();
		expect(screen.getByText("Team Leadership")).toBeInTheDocument();
		expect(screen.getByText("Required")).toBeInTheDocument();
		expect(screen.getByText("Preferred")).toBeInTheDocument();
	});

	it("renders fit score with tier badge", async () => {
		setupApiMocks({ personaJob: makePersonaJobResponse({ fit_score: 87 }) });

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByLabelText(/fit score.*87/i)).toBeInTheDocument();
		});
	});

	it("renders 'Not scored' when fit_score is null", async () => {
		setupApiMocks({
			personaJob: makePersonaJobResponse({ fit_score: null }),
		});

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(
				screen.getByLabelText(/fit score.*not scored/i),
			).toBeInTheDocument();
		});
	});

	it("renders empty state when no extracted skills", async () => {
		setupApiMocks();

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(screen.getByText("Scrum Master")).toBeInTheDocument();
		});
		expect(screen.getByText("No skills extracted")).toBeInTheDocument();
	});

	it("renders requirements text when available", async () => {
		setupApiMocks();

		render(<JobRequirementsPanel jobPostingId={JOB_POSTING_ID} />, {
			wrapper: Wrapper,
		});

		await waitFor(() => {
			expect(
				screen.getByText(/SAFe certification required/),
			).toBeInTheDocument();
		});
	});
});
