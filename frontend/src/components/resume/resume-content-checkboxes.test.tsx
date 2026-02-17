/**
 * Tests for the ResumeContentCheckboxes shared component.
 *
 * REQ-012 §9.2: Verifies rendering of job/bullet/education/certification/skill
 * checkbox sections and toggle callbacks.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UseResumeContentSelectionReturn } from "@/hooks/use-resume-content-selection";
import type {
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";

import { ResumeContentCheckboxes } from "./resume-content-checkboxes";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_JOBS: WorkHistory[] = [
	{
		id: "job-1",
		persona_id: "p-1",
		company_name: "Acme",
		company_industry: null,
		job_title: "Engineer",
		start_date: "2020-01-01",
		end_date: "2023-06-01",
		is_current: false,
		location: "NYC",
		work_model: "Onsite",
		description: "Built things",
		display_order: 0,
		bullets: [
			{
				id: "b-1",
				work_history_id: "job-1",
				text: "First bullet",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			},
			{
				id: "b-2",
				work_history_id: "job-1",
				text: "Second bullet",
				skills_demonstrated: [],
				metrics: null,
				display_order: 1,
			},
		],
	},
];

const MOCK_EDUCATIONS: Education[] = [
	{
		id: "edu-1",
		persona_id: "p-1",
		institution: "MIT",
		degree: "BS",
		field_of_study: "Computer Science",
		graduation_year: 2020,
		gpa: null,
		honors: null,
		display_order: 0,
	},
];

const MOCK_CERTIFICATIONS: Certification[] = [
	{
		id: "cert-1",
		persona_id: "p-1",
		certification_name: "AWS Solutions Architect",
		issuing_organization: "Amazon",
		date_obtained: "2022-01-15",
		expiration_date: null,
		credential_id: null,
		verification_url: null,
		display_order: 0,
	},
];

const MOCK_SKILLS: Skill[] = [
	{
		id: "skill-1",
		persona_id: "p-1",
		skill_name: "TypeScript",
		skill_type: "Hard",
		category: "Programming",
		proficiency: "Expert",
		years_used: 5,
		last_used: "Current",
		display_order: 0,
	},
];

// ---------------------------------------------------------------------------
// Default props factory
// ---------------------------------------------------------------------------

function defaultSelection(
	overrides: Partial<UseResumeContentSelectionReturn> = {},
): UseResumeContentSelectionReturn {
	return {
		includedJobs: [],
		bulletSelections: {},
		bulletOrder: {},
		includedEducation: ["edu-1"],
		includedCertifications: ["cert-1"],
		skillsEmphasis: ["skill-1"],
		setIncludedJobs: vi.fn(),
		setBulletSelections: vi.fn(),
		setBulletOrder: vi.fn(),
		setIncludedEducation: vi.fn(),
		setIncludedCertifications: vi.fn(),
		setSkillsEmphasis: vi.fn(),
		handleToggleJob: vi.fn(),
		handleToggleBullet: vi.fn(),
		handleToggleEducation: vi.fn(),
		handleToggleCertification: vi.fn(),
		handleToggleSkill: vi.fn(),
		...overrides,
	};
}

function defaultProps(
	selectionOverrides: Partial<UseResumeContentSelectionReturn> = {},
) {
	return {
		jobs: MOCK_JOBS,
		educations: MOCK_EDUCATIONS,
		certifications: MOCK_CERTIFICATIONS,
		skills: MOCK_SKILLS,
		selection: defaultSelection(selectionOverrides),
	};
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResumeContentCheckboxes", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Section rendering
	// -----------------------------------------------------------------------

	describe("section headings", () => {
		it("renders Included Jobs heading", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("heading", { name: /included jobs/i }),
			).toBeInTheDocument();
		});

		it("renders Education heading when educations exist", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("heading", { name: /education/i }),
			).toBeInTheDocument();
		});

		it("hides Education heading when empty", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} educations={[]} />);

			expect(
				screen.queryByRole("heading", { name: /^education$/i }),
			).not.toBeInTheDocument();
		});

		it("renders Certifications heading when certifications exist", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("heading", { name: /certifications/i }),
			).toBeInTheDocument();
		});

		it("hides Certifications heading when empty", () => {
			render(
				<ResumeContentCheckboxes {...defaultProps()} certifications={[]} />,
			);

			expect(
				screen.queryByRole("heading", { name: /certifications/i }),
			).not.toBeInTheDocument();
		});

		it("renders Skills Emphasis heading when skills exist", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("heading", { name: /skills emphasis/i }),
			).toBeInTheDocument();
		});

		it("hides Skills Emphasis heading when empty", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} skills={[]} />);

			expect(
				screen.queryByRole("heading", { name: /skills emphasis/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Job checkboxes
	// -----------------------------------------------------------------------

	describe("job checkboxes", () => {
		it("renders job with title and company", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(screen.getByText("Engineer")).toBeInTheDocument();
			expect(screen.getByText("Acme")).toBeInTheDocument();
		});

		it("calls handleToggleJob when job checkbox clicked", async () => {
			const props = defaultProps();
			const user = userEvent.setup();
			render(<ResumeContentCheckboxes {...props} />);

			await user.click(
				screen.getByRole("checkbox", {
					name: /engineer at acme/i,
				}),
			);

			expect(props.selection.handleToggleJob).toHaveBeenCalledWith(
				"job-1",
				MOCK_JOBS[0],
			);
		});

		it("shows bullets when job is included", () => {
			render(
				<ResumeContentCheckboxes
					{...defaultProps({
						includedJobs: ["job-1"],
						bulletSelections: { "job-1": ["b-1", "b-2"] },
					})}
				/>,
			);

			expect(screen.getByText("First bullet")).toBeInTheDocument();
			expect(screen.getByText("Second bullet")).toBeInTheDocument();
		});

		it("hides bullets when job is not included", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(screen.queryByText("First bullet")).not.toBeInTheDocument();
		});

		it("calls handleToggleBullet when bullet checkbox clicked", async () => {
			const props = defaultProps({
				includedJobs: ["job-1"],
				bulletSelections: { "job-1": ["b-1", "b-2"] },
			});
			const user = userEvent.setup();
			render(<ResumeContentCheckboxes {...props} />);

			await user.click(screen.getByRole("checkbox", { name: "First bullet" }));

			expect(props.selection.handleToggleBullet).toHaveBeenCalledWith(
				"job-1",
				"b-1",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Education checkboxes
	// -----------------------------------------------------------------------

	describe("education checkboxes", () => {
		it("renders education entry", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("checkbox", {
					name: /bs computer science at mit/i,
				}),
			).toBeInTheDocument();
		});

		it("calls handleToggleEducation when clicked", async () => {
			const props = defaultProps();
			const user = userEvent.setup();
			render(<ResumeContentCheckboxes {...props} />);

			await user.click(
				screen.getByRole("checkbox", {
					name: /bs computer science at mit/i,
				}),
			);

			expect(props.selection.handleToggleEducation).toHaveBeenCalledWith(
				"edu-1",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Certification checkboxes
	// -----------------------------------------------------------------------

	describe("certification checkboxes", () => {
		it("renders certification entry", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("checkbox", {
					name: /aws solutions architect from amazon/i,
				}),
			).toBeInTheDocument();
		});

		it("calls handleToggleCertification when clicked", async () => {
			const props = defaultProps();
			const user = userEvent.setup();
			render(<ResumeContentCheckboxes {...props} />);

			await user.click(
				screen.getByRole("checkbox", {
					name: /aws solutions architect from amazon/i,
				}),
			);

			expect(props.selection.handleToggleCertification).toHaveBeenCalledWith(
				"cert-1",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Skill checkboxes
	// -----------------------------------------------------------------------

	describe("skill checkboxes", () => {
		it("renders skill entry", () => {
			render(<ResumeContentCheckboxes {...defaultProps()} />);

			expect(
				screen.getByRole("checkbox", { name: /typescript/i }),
			).toBeInTheDocument();
		});

		it("calls handleToggleSkill when clicked", async () => {
			const props = defaultProps();
			const user = userEvent.setup();
			render(<ResumeContentCheckboxes {...props} />);

			await user.click(screen.getByRole("checkbox", { name: /typescript/i }));

			expect(props.selection.handleToggleSkill).toHaveBeenCalledWith("skill-1");
		});
	});

	// -----------------------------------------------------------------------
	// Custom bullet rendering
	// -----------------------------------------------------------------------

	describe("renderBullets prop", () => {
		it("uses renderBullets when provided", () => {
			render(
				<ResumeContentCheckboxes
					{...defaultProps({
						includedJobs: ["job-1"],
						bulletSelections: { "job-1": ["b-1"] },
					})}
					renderBullets={(job) => (
						<div data-testid="custom-bullets">Custom for {job.job_title}</div>
					)}
				/>,
			);

			expect(screen.getByTestId("custom-bullets")).toHaveTextContent(
				"Custom for Engineer",
			);
			// Default bullets should not be rendered
			expect(screen.queryByText("First bullet")).not.toBeInTheDocument();
		});
	});
});
