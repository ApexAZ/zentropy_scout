/**
 * Tests for the JobDetailPage route component (§7.7, §7.8, §7.9).
 *
 * Verifies guard clause, prop passthrough to JobDetailHeader,
 * FitScoreBreakdown, StretchScoreBreakdown, and ScoreExplanation
 * rendering when job data is available.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
	FitScoreResult,
	ScoreExplanation as ScoreExplanationType,
	StretchScoreResult,
} from "@/types/job";

import JobDetailPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_JOB_ID = "test-job-id";
const HEADER_TESTID = "job-detail-header-stub";
const BREAKDOWN_TESTID = "fit-breakdown-stub";
const STRETCH_TESTID = "stretch-breakdown-stub";
const EXPLANATION_TESTID = "explanation-stub";

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

function MockStretchScoreBreakdown({
	stretch,
}: {
	stretch: StretchScoreResult | undefined;
}) {
	return <div data-testid={STRETCH_TESTID}>{stretch ? "scored" : "none"}</div>;
}
MockStretchScoreBreakdown.displayName = "MockStretchScoreBreakdown";

vi.mock("@/components/jobs/stretch-score-breakdown", () => ({
	StretchScoreBreakdown: MockStretchScoreBreakdown,
}));

function MockScoreExplanation({
	explanation,
}: {
	explanation: ScoreExplanationType | undefined;
}) {
	return (
		<div data-testid={EXPLANATION_TESTID}>
			{explanation ? "available" : "none"}
		</div>
	);
}
MockScoreExplanation.displayName = "MockScoreExplanation";

vi.mock("@/components/jobs/score-explanation", () => ({
	ScoreExplanation: MockScoreExplanation,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScoreDetails() {
	return {
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
		} satisfies FitScoreResult,
		stretch: {
			total: 65,
			components: {
				target_role: 60,
				target_skills: 70,
				growth_trajectory: 50,
			},
			weights: {
				target_role: 0.5,
				target_skills: 0.4,
				growth_trajectory: 0.1,
			},
		} satisfies StretchScoreResult,
		explanation: {
			summary: "Good match overall.",
			strengths: ["Python"],
			gaps: ["Kubernetes"],
			stretch_opportunities: ["Cloud skills"],
			warnings: [],
		} satisfies ScoreExplanationType,
	};
}

function makeJobData(
	scoreDetails?: ReturnType<typeof makeScoreDetails> | null,
) {
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
		mocks.mockUseQuery.mockReturnValue(makeJobData(makeScoreDetails()));
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

	// -----------------------------------------------------------------------
	// StretchScoreBreakdown
	// -----------------------------------------------------------------------

	it("does not render StretchScoreBreakdown when data is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue({ data: undefined });
		render(<JobDetailPage />);

		expect(screen.queryByTestId(STRETCH_TESTID)).not.toBeInTheDocument();
	});

	it("renders StretchScoreBreakdown when job data is available", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(makeJobData(makeScoreDetails()));
		render(<JobDetailPage />);

		expect(screen.getByTestId(STRETCH_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(STRETCH_TESTID)).toHaveTextContent("scored");
	});

	it("renders StretchScoreBreakdown with undefined when score_details is null", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(makeJobData(null));
		render(<JobDetailPage />);

		expect(screen.getByTestId(STRETCH_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(STRETCH_TESTID)).toHaveTextContent("none");
	});

	// -----------------------------------------------------------------------
	// ScoreExplanation
	// -----------------------------------------------------------------------

	it("does not render ScoreExplanation when data is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue({ data: undefined });
		render(<JobDetailPage />);

		expect(screen.queryByTestId(EXPLANATION_TESTID)).not.toBeInTheDocument();
	});

	it("renders ScoreExplanation when job data is available", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(makeJobData(makeScoreDetails()));
		render(<JobDetailPage />);

		expect(screen.getByTestId(EXPLANATION_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(EXPLANATION_TESTID)).toHaveTextContent(
			"available",
		);
	});

	it("renders ScoreExplanation with undefined when score_details is null", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		mocks.mockUseQuery.mockReturnValue(makeJobData(null));
		render(<JobDetailPage />);

		expect(screen.getByTestId(EXPLANATION_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(EXPLANATION_TESTID)).toHaveTextContent("none");
	});
});
