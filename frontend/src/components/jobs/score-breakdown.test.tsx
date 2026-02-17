/**
 * Tests for the ScoreBreakdown generic component.
 *
 * REQ-012 §8.3: Score section with expandable component breakdown.
 * REQ-012 §8.4: Score drill-down showing weights and weighted contributions.
 *
 * Covers both "fit" and "stretch" scoreType variants via parameterized tests.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { FitScoreResult, StretchScoreResult } from "@/types/job";

import { ScoreBreakdown } from "./score-breakdown";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeFitScore(overrides?: Partial<FitScoreResult>): FitScoreResult {
	return {
		total: 92,
		components: {
			hard_skills: 82,
			soft_skills: 88,
			experience_level: 95,
			role_title: 90,
			location_logistics: 100,
		},
		weights: {
			hard_skills: 0.4,
			soft_skills: 0.15,
			experience_level: 0.25,
			role_title: 0.1,
			location_logistics: 0.1,
		},
		...overrides,
	};
}

function makeStretchScore(
	overrides?: Partial<StretchScoreResult>,
): StretchScoreResult {
	return {
		total: 45,
		components: {
			target_role: 30,
			target_skills: 60,
			growth_trajectory: 70,
		},
		weights: {
			target_role: 0.5,
			target_skills: 0.4,
			growth_trajectory: 0.1,
		},
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Tests — Fit score type
// ---------------------------------------------------------------------------

describe("ScoreBreakdown (fit)", () => {
	afterEach(() => {
		cleanup();
	});

	// -- Not scored --------------------------------------------------------

	describe("not scored", () => {
		it("renders 'Not scored' badge when score is undefined", () => {
			render(<ScoreBreakdown score={undefined} scoreType="fit" />);

			expect(screen.getByTestId("fit-score-not-scored")).toBeInTheDocument();
		});

		it("does not render toggle button when not scored", () => {
			render(<ScoreBreakdown score={undefined} scoreType="fit" />);

			expect(screen.queryByTestId("fit-score-toggle")).not.toBeInTheDocument();
		});

		it("does not render component rows when not scored", () => {
			render(<ScoreBreakdown score={undefined} scoreType="fit" />);

			expect(screen.queryByTestId("fit-score-panel")).not.toBeInTheDocument();
		});
	});

	// -- Collapsed state ---------------------------------------------------

	describe("collapsed state", () => {
		it("starts collapsed by default", () => {
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			expect(screen.queryByTestId("fit-score-panel")).not.toBeInTheDocument();
		});

		it("shows total score and tier badge when collapsed", () => {
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			const breakdown = screen.getByTestId("fit-score-breakdown");
			expect(breakdown.textContent).toContain("92");
			expect(breakdown.textContent).toContain("High");
		});

		it("shows chevron icon for toggle", () => {
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			expect(screen.getByTestId("fit-score-toggle")).toBeInTheDocument();
		});
	});

	// -- Expanded state ----------------------------------------------------

	describe("expanded state", () => {
		it("expands component rows on toggle click", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			expect(screen.getByTestId("fit-score-panel")).toBeInTheDocument();
		});

		it("shows all 5 component names in order", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			const panel = screen.getByTestId("fit-score-panel");
			const items = within(panel).getAllByRole("listitem");
			expect(items).toHaveLength(5);
			expect(items[0].textContent).toContain("Hard Skills");
			expect(items[1].textContent).toContain("Experience Level");
			expect(items[2].textContent).toContain("Soft Skills");
			expect(items[3].textContent).toContain("Role Title");
			expect(items[4].textContent).toContain("Location Logistics");
		});

		it("shows individual component scores", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			const panel = screen.getByTestId("fit-score-panel");
			expect(panel.textContent).toContain("82");
			expect(panel.textContent).toContain("95");
			expect(panel.textContent).toContain("88");
			expect(panel.textContent).toContain("90");
			expect(panel.textContent).toContain("100");
		});

		it("shows weight percentages", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			const panel = screen.getByTestId("fit-score-panel");
			expect(panel.textContent).toContain("40%");
			expect(panel.textContent).toContain("25%");
			expect(panel.textContent).toContain("15%");
			// 10% appears twice (role_title + location_logistics)
			const matches = panel.textContent?.match(/10%/g);
			expect(matches?.length).toBeGreaterThanOrEqual(2);
		});

		it("shows weighted contributions (Math.round(score * weight))", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			expect(screen.getByTestId("fit-score-panel")).toBeInTheDocument();
			// hard_skills: Math.round(82 * 0.4) = 33
			const hardSkillsRow = screen.getByTestId("fit-component-hard_skills");
			expect(hardSkillsRow.textContent).toContain("33");
			// experience_level: Math.round(95 * 0.25) = 24
			const expRow = screen.getByTestId("fit-component-experience_level");
			expect(expRow.textContent).toContain("24");
			// soft_skills: Math.round(88 * 0.15) = 13
			const softRow = screen.getByTestId("fit-component-soft_skills");
			expect(softRow.textContent).toContain("13");
			// role_title: Math.round(90 * 0.1) = 9
			const roleRow = screen.getByTestId("fit-component-role_title");
			expect(roleRow.textContent).toContain("9");
			// location_logistics: Math.round(100 * 0.1) = 10
			const locRow = screen.getByTestId("fit-component-location_logistics");
			expect(locRow.textContent).toContain("10");
		});

		it("collapses on second click", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));
			expect(screen.getByTestId("fit-score-panel")).toBeInTheDocument();

			await user.click(screen.getByTestId("fit-score-toggle"));
			expect(screen.queryByTestId("fit-score-panel")).not.toBeInTheDocument();
		});

		it("changes chevron direction when expanded", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			const toggle = screen.getByTestId("fit-score-toggle");
			expect(
				toggle.querySelector('[data-testid="chevron-right"]'),
			).toBeInTheDocument();

			await user.click(toggle);
			expect(
				toggle.querySelector('[data-testid="chevron-down"]'),
			).toBeInTheDocument();
		});
	});

	// -- Tier display ------------------------------------------------------

	describe("tier display", () => {
		it("shows Medium tier for score 75", () => {
			render(
				<ScoreBreakdown score={makeFitScore({ total: 75 })} scoreType="fit" />,
			);

			const breakdown = screen.getByTestId("fit-score-breakdown");
			expect(breakdown.textContent).toContain("Medium");
		});

		it("shows Low tier for score 60", () => {
			render(
				<ScoreBreakdown score={makeFitScore({ total: 60 })} scoreType="fit" />,
			);

			const breakdown = screen.getByTestId("fit-score-breakdown");
			expect(breakdown.textContent).toContain("Low");
		});

		it("shows Poor tier for score 59", () => {
			render(
				<ScoreBreakdown score={makeFitScore({ total: 59 })} scoreType="fit" />,
			);

			const breakdown = screen.getByTestId("fit-score-breakdown");
			expect(breakdown.textContent).toContain("Poor");
		});
	});

	// -- Accessibility -----------------------------------------------------

	describe("accessibility", () => {
		it("toggle has aria-expanded false when collapsed", () => {
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			expect(screen.getByTestId("fit-score-toggle")).toHaveAttribute(
				"aria-expanded",
				"false",
			);
		});

		it("toggle has aria-expanded true when expanded", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			expect(screen.getByTestId("fit-score-toggle")).toHaveAttribute(
				"aria-expanded",
				"true",
			);
		});

		it("component list uses list semantics", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeFitScore()} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			const panel = screen.getByTestId("fit-score-panel");
			const list = within(panel).getByRole("list");
			expect(list).toBeInTheDocument();
		});
	});

	// -- Edge cases --------------------------------------------------------

	describe("edge cases", () => {
		it("renders zero scores correctly", async () => {
			const user = userEvent.setup();
			const zeroFit = makeFitScore({
				total: 0,
				components: {
					hard_skills: 0,
					soft_skills: 0,
					experience_level: 0,
					role_title: 0,
					location_logistics: 0,
				},
			});
			render(<ScoreBreakdown score={zeroFit} scoreType="fit" />);

			await user.click(screen.getByTestId("fit-score-toggle"));

			const hardRow = screen.getByTestId("fit-component-hard_skills");
			expect(hardRow.textContent).toContain("0");
		});

		it("merges custom className", () => {
			render(
				<ScoreBreakdown
					score={makeFitScore()}
					scoreType="fit"
					className="mt-4"
				/>,
			);

			const breakdown = screen.getByTestId("fit-score-breakdown");
			expect(breakdown).toHaveClass("mt-4");
		});
	});
});

// ---------------------------------------------------------------------------
// Tests — Stretch score type
// ---------------------------------------------------------------------------

describe("ScoreBreakdown (stretch)", () => {
	afterEach(() => {
		cleanup();
	});

	// -- Not scored --------------------------------------------------------

	describe("not scored", () => {
		it("renders 'Not scored' badge when score is undefined", () => {
			render(<ScoreBreakdown score={undefined} scoreType="stretch" />);

			expect(
				screen.getByTestId("stretch-score-not-scored"),
			).toBeInTheDocument();
		});

		it("does not render toggle button when not scored", () => {
			render(<ScoreBreakdown score={undefined} scoreType="stretch" />);

			expect(
				screen.queryByTestId("stretch-score-toggle"),
			).not.toBeInTheDocument();
		});

		it("does not render component rows when not scored", () => {
			render(<ScoreBreakdown score={undefined} scoreType="stretch" />);

			expect(
				screen.queryByTestId("stretch-score-panel"),
			).not.toBeInTheDocument();
		});
	});

	// -- Collapsed state ---------------------------------------------------

	describe("collapsed state", () => {
		it("starts collapsed by default", () => {
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			expect(
				screen.queryByTestId("stretch-score-panel"),
			).not.toBeInTheDocument();
		});

		it("shows total score and tier badge when collapsed", () => {
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown.textContent).toContain("45");
			expect(breakdown.textContent).toContain("Lateral");
		});

		it("shows chevron icon for toggle", () => {
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			expect(screen.getByTestId("stretch-score-toggle")).toBeInTheDocument();
		});
	});

	// -- Expanded state ----------------------------------------------------

	describe("expanded state", () => {
		it("expands component rows on toggle click", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			expect(screen.getByTestId("stretch-score-panel")).toBeInTheDocument();
		});

		it("shows all 3 component names in order", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			const panel = screen.getByTestId("stretch-score-panel");
			const items = within(panel).getAllByRole("listitem");
			expect(items).toHaveLength(3);
			expect(items[0].textContent).toContain("Target Role");
			expect(items[1].textContent).toContain("Target Skills");
			expect(items[2].textContent).toContain("Growth Trajectory");
		});

		it("shows individual component scores", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			const panel = screen.getByTestId("stretch-score-panel");
			expect(panel.textContent).toContain("30");
			expect(panel.textContent).toContain("60");
			expect(panel.textContent).toContain("70");
		});

		it("shows weight percentages", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			const panel = screen.getByTestId("stretch-score-panel");
			expect(panel.textContent).toContain("50%");
			expect(panel.textContent).toContain("40%");
			expect(panel.textContent).toContain("10%");
		});

		it("shows weighted contributions (Math.round(score * weight))", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			// target_role: Math.round(30 * 0.5) = 15
			const roleRow = screen.getByTestId("stretch-component-target_role");
			expect(roleRow.textContent).toContain("15");
			// target_skills: Math.round(60 * 0.4) = 24
			const skillsRow = screen.getByTestId("stretch-component-target_skills");
			expect(skillsRow.textContent).toContain("24");
			// growth_trajectory: Math.round(70 * 0.1) = 7
			const growthRow = screen.getByTestId(
				"stretch-component-growth_trajectory",
			);
			expect(growthRow.textContent).toContain("7");
		});

		it("collapses on second click", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));
			expect(screen.getByTestId("stretch-score-panel")).toBeInTheDocument();

			await user.click(screen.getByTestId("stretch-score-toggle"));
			expect(
				screen.queryByTestId("stretch-score-panel"),
			).not.toBeInTheDocument();
		});

		it("changes chevron direction when expanded", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			const toggle = screen.getByTestId("stretch-score-toggle");
			expect(
				toggle.querySelector('[data-testid="chevron-right"]'),
			).toBeInTheDocument();

			await user.click(toggle);
			expect(
				toggle.querySelector('[data-testid="chevron-down"]'),
			).toBeInTheDocument();
		});
	});

	// -- Tier display ------------------------------------------------------

	describe("tier display", () => {
		it("shows High Growth tier for score 80", () => {
			render(
				<ScoreBreakdown
					score={makeStretchScore({ total: 80 })}
					scoreType="stretch"
				/>,
			);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown.textContent).toContain("High Growth");
		});

		it("shows Moderate Growth tier for score 65", () => {
			render(
				<ScoreBreakdown
					score={makeStretchScore({ total: 65 })}
					scoreType="stretch"
				/>,
			);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown.textContent).toContain("Moderate Growth");
		});

		it("shows Lateral tier for score 45", () => {
			render(
				<ScoreBreakdown
					score={makeStretchScore({ total: 45 })}
					scoreType="stretch"
				/>,
			);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown.textContent).toContain("Lateral");
		});

		it("shows Low Growth tier for score 30", () => {
			render(
				<ScoreBreakdown
					score={makeStretchScore({ total: 30 })}
					scoreType="stretch"
				/>,
			);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown.textContent).toContain("Low Growth");
		});
	});

	// -- Accessibility -----------------------------------------------------

	describe("accessibility", () => {
		it("toggle has aria-expanded false when collapsed", () => {
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			expect(screen.getByTestId("stretch-score-toggle")).toHaveAttribute(
				"aria-expanded",
				"false",
			);
		});

		it("toggle has aria-expanded true when expanded", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			expect(screen.getByTestId("stretch-score-toggle")).toHaveAttribute(
				"aria-expanded",
				"true",
			);
		});

		it("component list uses list semantics", async () => {
			const user = userEvent.setup();
			render(<ScoreBreakdown score={makeStretchScore()} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			const panel = screen.getByTestId("stretch-score-panel");
			const list = within(panel).getByRole("list");
			expect(list).toBeInTheDocument();
		});
	});

	// -- Edge cases --------------------------------------------------------

	describe("edge cases", () => {
		it("renders zero scores correctly", async () => {
			const user = userEvent.setup();
			const zeroStretch = makeStretchScore({
				total: 0,
				components: {
					target_role: 0,
					target_skills: 0,
					growth_trajectory: 0,
				},
			});
			render(<ScoreBreakdown score={zeroStretch} scoreType="stretch" />);

			await user.click(screen.getByTestId("stretch-score-toggle"));

			const roleRow = screen.getByTestId("stretch-component-target_role");
			expect(roleRow.textContent).toContain("0");
		});

		it("merges custom className", () => {
			render(
				<ScoreBreakdown
					score={makeStretchScore()}
					scoreType="stretch"
					className="mt-4"
				/>,
			);

			const breakdown = screen.getByTestId("stretch-score-breakdown");
			expect(breakdown).toHaveClass("mt-4");
		});
	});
});
