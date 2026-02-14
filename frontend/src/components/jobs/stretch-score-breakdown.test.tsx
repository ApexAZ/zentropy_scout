/**
 * Tests for the StretchScoreBreakdown component (§7.9).
 *
 * REQ-012 §8.3: Stretch score section with expandable component breakdown.
 * REQ-012 §8.4: Stretch score drill-down showing weights and weighted contributions.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { StretchScoreResult } from "@/types/job";

import { StretchScoreBreakdown } from "./stretch-score-breakdown";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BREAKDOWN_TESTID = "stretch-score-breakdown";
const TOGGLE_TESTID = "stretch-score-toggle";
const NOT_SCORED_TESTID = "stretch-score-not-scored";
const PANEL_TESTID = "stretch-score-panel";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

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
// Helpers
// ---------------------------------------------------------------------------

function renderBreakdown(stretch?: StretchScoreResult, className?: string) {
	return render(
		<StretchScoreBreakdown stretch={stretch} className={className} />,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StretchScoreBreakdown", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Not scored
	// -----------------------------------------------------------------------

	describe("not scored", () => {
		it("renders 'Not scored' badge when stretch is undefined", () => {
			renderBreakdown(undefined);

			expect(screen.getByTestId(NOT_SCORED_TESTID)).toBeInTheDocument();
		});

		it("does not render toggle button when not scored", () => {
			renderBreakdown(undefined);

			expect(screen.queryByTestId(TOGGLE_TESTID)).not.toBeInTheDocument();
		});

		it("does not render component rows when not scored", () => {
			renderBreakdown(undefined);

			expect(screen.queryByTestId(PANEL_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Collapsed state (default)
	// -----------------------------------------------------------------------

	describe("collapsed state", () => {
		it("starts collapsed by default", () => {
			renderBreakdown(makeStretchScore());

			expect(screen.queryByTestId(PANEL_TESTID)).not.toBeInTheDocument();
		});

		it("shows total score and tier badge when collapsed", () => {
			renderBreakdown(makeStretchScore());

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("45");
			expect(breakdown.textContent).toContain("Lateral");
		});

		it("shows chevron icon for toggle", () => {
			renderBreakdown(makeStretchScore());

			expect(screen.getByTestId(TOGGLE_TESTID)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Expanded state
	// -----------------------------------------------------------------------

	describe("expanded state", () => {
		it("expands component rows on toggle click", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			expect(screen.getByTestId(PANEL_TESTID)).toBeInTheDocument();
		});

		it("shows all 3 component names in order", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			const items = within(panel).getAllByRole("listitem");
			expect(items).toHaveLength(3);
			expect(items[0].textContent).toContain("Target Role");
			expect(items[1].textContent).toContain("Target Skills");
			expect(items[2].textContent).toContain("Growth Trajectory");
		});

		it("shows individual component scores", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			expect(panel.textContent).toContain("30");
			expect(panel.textContent).toContain("60");
			expect(panel.textContent).toContain("70");
		});

		it("shows weight percentages", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			expect(panel.textContent).toContain("50%");
			expect(panel.textContent).toContain("40%");
			expect(panel.textContent).toContain("10%");
		});

		it("shows weighted contributions (Math.round(score * weight))", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

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
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));
			expect(screen.getByTestId(PANEL_TESTID)).toBeInTheDocument();

			await user.click(screen.getByTestId(TOGGLE_TESTID));
			expect(screen.queryByTestId(PANEL_TESTID)).not.toBeInTheDocument();
		});

		it("changes chevron direction when expanded", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			const toggle = screen.getByTestId(TOGGLE_TESTID);
			expect(
				toggle.querySelector('[data-testid="chevron-right"]'),
			).toBeInTheDocument();

			await user.click(toggle);
			expect(
				toggle.querySelector('[data-testid="chevron-down"]'),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Tier display
	// -----------------------------------------------------------------------

	describe("tier display", () => {
		it("shows High Growth tier for score 80", () => {
			renderBreakdown(makeStretchScore({ total: 80 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("High Growth");
		});

		it("shows Moderate Growth tier for score 65", () => {
			renderBreakdown(makeStretchScore({ total: 65 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Moderate Growth");
		});

		it("shows Lateral tier for score 45", () => {
			renderBreakdown(makeStretchScore({ total: 45 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Lateral");
		});

		it("shows Low Growth tier for score 30", () => {
			renderBreakdown(makeStretchScore({ total: 30 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Low Growth");
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("toggle has aria-expanded false when collapsed", () => {
			renderBreakdown(makeStretchScore());

			expect(screen.getByTestId(TOGGLE_TESTID)).toHaveAttribute(
				"aria-expanded",
				"false",
			);
		});

		it("toggle has aria-expanded true when expanded", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			expect(screen.getByTestId(TOGGLE_TESTID)).toHaveAttribute(
				"aria-expanded",
				"true",
			);
		});

		it("component list uses list semantics", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeStretchScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			const list = within(panel).getByRole("list");
			expect(list).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edge cases
	// -----------------------------------------------------------------------

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
			renderBreakdown(zeroStretch);

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const roleRow = screen.getByTestId("stretch-component-target_role");
			expect(roleRow.textContent).toContain("0");
		});

		it("merges custom className", () => {
			renderBreakdown(makeStretchScore(), "mt-4");

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown).toHaveClass("mt-4");
		});
	});
});
