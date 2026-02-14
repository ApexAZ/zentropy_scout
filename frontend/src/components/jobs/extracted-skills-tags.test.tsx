/**
 * Tests for the ExtractedSkillsTags component (§7.10).
 *
 * REQ-012 §8.3: Extracted skills grouped by Required / Preferred with chip display.
 * REQ-005 §4.2: ExtractedSkill model shape.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ExtractedSkill } from "@/types/job";

import { ExtractedSkillsTags } from "./extracted-skills-tags";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "extracted-skills-tags";
const NOT_AVAILABLE_TESTID = "skills-not-available";
const REQUIRED_GROUP_TESTID = "skills-required-group";
const PREFERRED_GROUP_TESTID = "skills-preferred-group";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeSkills(overrides?: Partial<ExtractedSkill>[]): ExtractedSkill[] {
	const defaults: ExtractedSkill[] = [
		{
			id: "s-1",
			job_posting_id: "j-1",
			skill_name: "Python",
			skill_type: "Hard",
			is_required: true,
			years_requested: 3,
		},
		{
			id: "s-2",
			job_posting_id: "j-1",
			skill_name: "FastAPI",
			skill_type: "Hard",
			is_required: true,
			years_requested: null,
		},
		{
			id: "s-3",
			job_posting_id: "j-1",
			skill_name: "Terraform",
			skill_type: "Hard",
			is_required: false,
			years_requested: null,
		},
		{
			id: "s-4",
			job_posting_id: "j-1",
			skill_name: "Redis",
			skill_type: "Hard",
			is_required: false,
			years_requested: 2,
		},
	];

	if (!overrides) return defaults;

	return defaults.map((skill, i) => ({
		...skill,
		...(overrides[i] ?? {}),
	}));
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSkills(skills?: ExtractedSkill[], className?: string) {
	return render(<ExtractedSkillsTags skills={skills} className={className} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractedSkillsTags", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Not available
	// -----------------------------------------------------------------------

	describe("not available", () => {
		it("renders 'No skills extracted' badge when undefined", () => {
			renderSkills(undefined);

			expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toBeInTheDocument();
			expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toHaveTextContent(
				"No skills extracted",
			);
		});

		it("renders 'No skills extracted' badge when empty array", () => {
			renderSkills([]);

			expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toBeInTheDocument();
		});

		it("does not render group headings when undefined", () => {
			renderSkills(undefined);

			expect(
				screen.queryByTestId(REQUIRED_GROUP_TESTID),
			).not.toBeInTheDocument();
			expect(
				screen.queryByTestId(PREFERRED_GROUP_TESTID),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Required skills
	// -----------------------------------------------------------------------

	describe("required skills", () => {
		it("renders required group heading", () => {
			renderSkills(makeSkills());

			const group = screen.getByTestId(REQUIRED_GROUP_TESTID);
			expect(group).toBeInTheDocument();
			expect(group).toHaveTextContent("Required");
		});

		it("renders each required skill as a chip", () => {
			renderSkills(makeSkills());

			expect(screen.getByTestId("skill-chip-Python")).toBeInTheDocument();
			expect(screen.getByTestId("skill-chip-FastAPI")).toBeInTheDocument();
		});

		it("hides required group when no skills are required", () => {
			const allPreferred = makeSkills().map((s) => ({
				...s,
				is_required: false,
			}));
			renderSkills(allPreferred);

			expect(
				screen.queryByTestId(REQUIRED_GROUP_TESTID),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Preferred skills
	// -----------------------------------------------------------------------

	describe("preferred skills", () => {
		it("renders preferred group heading", () => {
			renderSkills(makeSkills());

			const group = screen.getByTestId(PREFERRED_GROUP_TESTID);
			expect(group).toBeInTheDocument();
			expect(group).toHaveTextContent("Preferred");
		});

		it("renders each preferred skill as a chip", () => {
			renderSkills(makeSkills());

			expect(screen.getByTestId("skill-chip-Terraform")).toBeInTheDocument();
			expect(screen.getByTestId("skill-chip-Redis")).toBeInTheDocument();
		});

		it("hides preferred group when no skills are preferred", () => {
			const allRequired = makeSkills().map((s) => ({
				...s,
				is_required: true,
			}));
			renderSkills(allRequired);

			expect(
				screen.queryByTestId(PREFERRED_GROUP_TESTID),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Years requested
	// -----------------------------------------------------------------------

	describe("years requested", () => {
		it("shows years suffix when years_requested is present", () => {
			renderSkills(makeSkills());

			expect(screen.getByTestId("skill-chip-Python")).toHaveTextContent(
				"Python (3+ yr)",
			);
			expect(screen.getByTestId("skill-chip-Redis")).toHaveTextContent(
				"Redis (2+ yr)",
			);
		});

		it("omits years suffix when years_requested is null", () => {
			renderSkills(makeSkills());

			expect(screen.getByTestId("skill-chip-FastAPI")).toHaveTextContent(
				"FastAPI",
			);
			expect(screen.getByTestId("skill-chip-FastAPI")).not.toHaveTextContent(
				"yr",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Mixed skills
	// -----------------------------------------------------------------------

	describe("mixed skills", () => {
		it("separates required and preferred into correct groups", () => {
			renderSkills(makeSkills());

			const requiredGroup = screen.getByTestId(REQUIRED_GROUP_TESTID);
			const preferredGroup = screen.getByTestId(PREFERRED_GROUP_TESTID);

			expect(requiredGroup).toHaveTextContent("Python");
			expect(requiredGroup).toHaveTextContent("FastAPI");
			expect(requiredGroup).not.toHaveTextContent("Terraform");

			expect(preferredGroup).toHaveTextContent("Terraform");
			expect(preferredGroup).toHaveTextContent("Redis");
			expect(preferredGroup).not.toHaveTextContent("Python");
		});
	});

	// -----------------------------------------------------------------------
	// Edge cases
	// -----------------------------------------------------------------------

	describe("edge cases", () => {
		it("renders only required group when all skills are required", () => {
			const allRequired = makeSkills().map((s) => ({
				...s,
				is_required: true,
			}));
			renderSkills(allRequired);

			expect(screen.getByTestId(REQUIRED_GROUP_TESTID)).toBeInTheDocument();
			expect(
				screen.queryByTestId(PREFERRED_GROUP_TESTID),
			).not.toBeInTheDocument();
		});

		it("merges custom className", () => {
			renderSkills(makeSkills(), "mt-4");

			const section = screen.getByTestId(SECTION_TESTID);
			expect(section).toHaveClass("mt-4");
		});
	});
});
