/**
 * Tests for the JobDetailPage route component (§7.7–§7.10, §10.4).
 *
 * Verifies guard clause, prop passthrough to JobDetailHeader,
 * FitScoreBreakdown, StretchScoreBreakdown, ScoreExplanation,
 * ExtractedSkillsTags, JobDescription, CultureSignals, and
 * MarkAsAppliedCard rendering when job data is available.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
	ExtractedSkill,
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
const SKILLS_TESTID = "extracted-skills-stub";
const DESCRIPTION_TESTID = "job-description-stub";
const CULTURE_TESTID = "culture-signals-stub";
const MARK_AS_APPLIED_TESTID = "mark-as-applied-stub";
const ONBOARDED_STATUS = { status: "onboarded", persona: { id: "p-1" } };

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

function MockScoreBreakdown({
	score,
	scoreType,
}: {
	score: FitScoreResult | StretchScoreResult | undefined;
	scoreType: "fit" | "stretch";
}) {
	const testid = scoreType === "fit" ? BREAKDOWN_TESTID : STRETCH_TESTID;
	return <div data-testid={testid}>{score ? "scored" : "none"}</div>;
}
MockScoreBreakdown.displayName = "MockScoreBreakdown";

vi.mock("@/components/jobs/score-breakdown", () => ({
	ScoreBreakdown: MockScoreBreakdown,
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

function MockExtractedSkillsTags({
	skills,
}: {
	skills: ExtractedSkill[] | undefined;
}) {
	return (
		<div data-testid={SKILLS_TESTID}>
			{skills ? `${skills.length} skills` : "none"}
		</div>
	);
}
MockExtractedSkillsTags.displayName = "MockExtractedSkillsTags";

vi.mock("@/components/jobs/extracted-skills-tags", () => ({
	ExtractedSkillsTags: MockExtractedSkillsTags,
}));

function MockJobDescription({ description }: { description: string }) {
	return <div data-testid={DESCRIPTION_TESTID}>{description}</div>;
}
MockJobDescription.displayName = "MockJobDescription";

vi.mock("@/components/jobs/job-description", () => ({
	JobDescription: MockJobDescription,
}));

function MockCultureSignals({ cultureText }: { cultureText: string | null }) {
	return <div data-testid={CULTURE_TESTID}>{cultureText ?? "null"}</div>;
}
MockCultureSignals.displayName = "MockCultureSignals";

vi.mock("@/components/jobs/culture-signals", () => ({
	CultureSignals: MockCultureSignals,
}));

function MockMarkAsAppliedCard({
	jobId,
	applyUrl,
}: {
	jobId: string;
	applyUrl: string | null;
}) {
	return (
		<div data-testid={MARK_AS_APPLIED_TESTID}>
			{jobId}|{applyUrl ?? "null"}
		</div>
	);
}
MockMarkAsAppliedCard.displayName = "MockMarkAsAppliedCard";

vi.mock("@/components/jobs/mark-as-applied-card", () => ({
	MarkAsAppliedCard: MockMarkAsAppliedCard,
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
				description: "We are hiring a senior engineer.",
				culture_text: "Fast-paced and collaborative.",
				apply_url: "https://example.com/apply",
			},
		},
	};
}

function makeSkillsData(): ExtractedSkill[] {
	return [
		{
			id: "s-1",
			job_posting_id: MOCK_JOB_ID,
			skill_name: "Python",
			skill_type: "Hard",
			is_required: true,
			years_requested: 3,
		},
		{
			id: "s-2",
			job_posting_id: MOCK_JOB_ID,
			skill_name: "FastAPI",
			skill_type: "Hard",
			is_required: false,
			years_requested: null,
		},
	];
}

/**
 * Sets up the useQuery mock to return different data for the job detail
 * query and the extracted skills query.
 */
function setupQueries(options?: {
	jobData?: ReturnType<typeof makeJobData>;
	skillsData?: { data: { data: ExtractedSkill[] } };
}) {
	mocks.mockUseQuery.mockImplementation(
		(opts: { queryKey: readonly string[] }) => {
			if (opts.queryKey[2] === "extracted-skills") {
				return options?.skillsData ?? { data: undefined };
			}
			return options?.jobData ?? { data: undefined };
		},
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDetailPage", () => {
	beforeEach(() => {
		mocks.mockUseParams.mockReturnValue({ id: MOCK_JOB_ID });
		mocks.mockUsePersonaStatus.mockReturnValue(ONBOARDED_STATUS);
		setupQueries();
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
		render(<JobDetailPage />);

		const header = screen.getByTestId(HEADER_TESTID);
		expect(header).toBeInTheDocument();
		expect(header).toHaveTextContent(MOCK_JOB_ID);
	});

	it("does not render FitScoreBreakdown when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(BREAKDOWN_TESTID)).not.toBeInTheDocument();
	});

	it("renders FitScoreBreakdown when job data is available", () => {
		setupQueries({ jobData: makeJobData(makeScoreDetails()) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(BREAKDOWN_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(BREAKDOWN_TESTID)).toHaveTextContent("scored");
	});

	it("renders FitScoreBreakdown with undefined fit when score_details is null", () => {
		setupQueries({ jobData: makeJobData(null) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(BREAKDOWN_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(BREAKDOWN_TESTID)).toHaveTextContent("none");
	});

	// -----------------------------------------------------------------------
	// StretchScoreBreakdown
	// -----------------------------------------------------------------------

	it("does not render StretchScoreBreakdown when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(STRETCH_TESTID)).not.toBeInTheDocument();
	});

	it("renders StretchScoreBreakdown when job data is available", () => {
		setupQueries({ jobData: makeJobData(makeScoreDetails()) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(STRETCH_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(STRETCH_TESTID)).toHaveTextContent("scored");
	});

	it("renders StretchScoreBreakdown with undefined when score_details is null", () => {
		setupQueries({ jobData: makeJobData(null) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(STRETCH_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(STRETCH_TESTID)).toHaveTextContent("none");
	});

	// -----------------------------------------------------------------------
	// ScoreExplanation
	// -----------------------------------------------------------------------

	it("does not render ScoreExplanation when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(EXPLANATION_TESTID)).not.toBeInTheDocument();
	});

	it("renders ScoreExplanation when job data is available", () => {
		setupQueries({ jobData: makeJobData(makeScoreDetails()) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(EXPLANATION_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(EXPLANATION_TESTID)).toHaveTextContent(
			"available",
		);
	});

	it("renders ScoreExplanation with undefined when score_details is null", () => {
		setupQueries({ jobData: makeJobData(null) });
		render(<JobDetailPage />);

		expect(screen.getByTestId(EXPLANATION_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(EXPLANATION_TESTID)).toHaveTextContent("none");
	});

	// -----------------------------------------------------------------------
	// ExtractedSkillsTags
	// -----------------------------------------------------------------------

	it("does not render ExtractedSkillsTags when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(SKILLS_TESTID)).not.toBeInTheDocument();
	});

	it("renders ExtractedSkillsTags when job data is available", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(SKILLS_TESTID)).toBeInTheDocument();
	});

	it("passes extracted skills from query to ExtractedSkillsTags", () => {
		const skills = makeSkillsData();
		setupQueries({
			jobData: makeJobData(),
			skillsData: { data: { data: skills } },
		});
		render(<JobDetailPage />);

		expect(screen.getByTestId(SKILLS_TESTID)).toHaveTextContent("2 skills");
	});

	// -----------------------------------------------------------------------
	// JobDescription
	// -----------------------------------------------------------------------

	it("does not render JobDescription when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(DESCRIPTION_TESTID)).not.toBeInTheDocument();
	});

	it("renders JobDescription when job data is available", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(DESCRIPTION_TESTID)).toBeInTheDocument();
	});

	it("passes description to JobDescription", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(DESCRIPTION_TESTID)).toHaveTextContent(
			"We are hiring a senior engineer.",
		);
	});

	// -----------------------------------------------------------------------
	// CultureSignals
	// -----------------------------------------------------------------------

	it("does not render CultureSignals when data is loading", () => {
		render(<JobDetailPage />);

		expect(screen.queryByTestId(CULTURE_TESTID)).not.toBeInTheDocument();
	});

	it("renders CultureSignals when job data is available", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(CULTURE_TESTID)).toBeInTheDocument();
	});

	it("passes culture_text to CultureSignals", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(CULTURE_TESTID)).toHaveTextContent(
			"Fast-paced and collaborative.",
		);
	});

	// -----------------------------------------------------------------------
	// MarkAsAppliedCard
	// -----------------------------------------------------------------------

	it("does not render MarkAsAppliedCard when data is loading", () => {
		render(<JobDetailPage />);

		expect(
			screen.queryByTestId(MARK_AS_APPLIED_TESTID),
		).not.toBeInTheDocument();
	});

	it("renders MarkAsAppliedCard when job data is available", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(MARK_AS_APPLIED_TESTID)).toBeInTheDocument();
	});

	it("passes apply_url to MarkAsAppliedCard", () => {
		setupQueries({ jobData: makeJobData() });
		render(<JobDetailPage />);

		expect(screen.getByTestId(MARK_AS_APPLIED_TESTID)).toHaveTextContent(
			"https://example.com/apply",
		);
	});
});
