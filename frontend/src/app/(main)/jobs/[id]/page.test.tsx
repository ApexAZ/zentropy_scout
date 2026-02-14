/**
 * Tests for the JobDetailPage route component (§7.7, §7.8).
 *
 * Verifies guard clause, prop passthrough to JobDetailHeader,
 * and FitScoreBreakdown rendering when job data is available.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FitScoreResult } from "@/types/job";

import JobDetailPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_JOB_ID = "test-job-id";
const HEADER_TESTID = "job-detail-header-stub";
const BREAKDOWN_TESTID = "fit-breakdown-stub";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
	mockUseParams: vi.fn(),
	mockUseQuery: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("next/navigation", () => ({
	useParams: mocks.mockUseParams,
}));

vi.mock("@tanstack/react-query", () => ({
	useQuery: mocks.mockUseQuery,
}));

function MockJobDetailHeader({ jobId }: { jobId: string }) {
	return <div data-testid={HEADER_TESTID}>{jobId}</div>;
}
MockJobDetailHeader.displayName = "MockJobDetailHeader";

vi.mock("@/components/jobs/job-detail-header", () => ({
	JobDetailHeader: MockJobDetailHeader,
}));

function MockFitScoreBreakdown({ fit }: { fit: FitScoreResult | undefined }) {
	return <div data-testid={BREAKDOWN_TESTID}>{fit ? "scored" : "none"}</div>;
}
MockFitScoreBreakdown.displayName = "MockFitScoreBreakdown";

vi.mock("@/components/jobs/fit-score-breakdown", () => ({
	FitScoreBreakdown: MockFitScoreBreakdown,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeJobData(scoreDetails?: { fit: FitScoreResult } | null) {
	return {
		data: {
			data: {
				id: MOCK_JOB_ID,
				score_details: scoreDetails ?? null,
			},
		},
	};
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDetailPage", () => {
	beforeEach(() => {
		mocks.mockUseParams.mockReturnValue({ id: MOCK_JOB_ID });
		mocks.mockUsePersonaStatus.mockReset();
		mocks.mockUseQuery.mockReturnValue({ data: undefined });
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<JobDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<JobDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders JobDetailHeader with jobId from route params", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		render(<JobDetailPage />);

		const header = screen.getByTestId(HEADER_TESTID);
		expect(header).toBeInTheDocument();
		expect(header).toHaveTextContent(MOCK_JOB_ID);
	});

	it("does not render FitScoreBreakdown when data is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue({ data: undefined });
		render(<JobDetailPage />);

		expect(screen.queryByTestId(BREAKDOWN_TESTID)).not.toBeInTheDocument();
	});

	it("renders FitScoreBreakdown when job data is available", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(
			makeJobData({
				fit: {
					total: 85,
					components: {
						hard_skills: 80,
						soft_skills: 75,
						experience_level: 90,
						role_title: 85,
						location_logistics: 100,
					},
					weights: {
						hard_skills: 0.4,
						soft_skills: 0.15,
						experience_level: 0.25,
						role_title: 0.1,
						location_logistics: 0.1,
					},
				},
			}),
		);
		render(<JobDetailPage />);

		expect(screen.getByTestId(BREAKDOWN_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(BREAKDOWN_TESTID)).toHaveTextContent("scored");
	});

	it("renders FitScoreBreakdown with undefined fit when score_details is null", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(makeJobData(null));
		render(<JobDetailPage />);

		expect(screen.getByTestId(BREAKDOWN_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(BREAKDOWN_TESTID)).toHaveTextContent("none");
	});
});
