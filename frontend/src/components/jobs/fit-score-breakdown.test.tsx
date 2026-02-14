/**
 * Tests for the FitScoreBreakdown component (§7.8).
 *
 * REQ-012 §8.3: Fit score section with expandable component breakdown.
 * REQ-012 §8.4: Fit score drill-down showing weights and weighted contributions.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { FitScoreResult } from "@/types/job";

import { FitScoreBreakdown } from "./fit-score-breakdown";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BREAKDOWN_TESTID = "fit-score-breakdown";
const TOGGLE_TESTID = "fit-score-toggle";
const NOT_SCORED_TESTID = "fit-score-not-scored";
const PANEL_TESTID = "fit-score-panel";

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBreakdown(fit?: FitScoreResult, className?: string) {
	return render(<FitScoreBreakdown fit={fit} className={className} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FitScoreBreakdown", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Not scored
	// -----------------------------------------------------------------------

	describe("not scored", () => {
		it("renders 'Not scored' badge when fit is undefined", () => {
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
			renderBreakdown(makeFitScore());

			expect(screen.queryByTestId(PANEL_TESTID)).not.toBeInTheDocument();
		});

		it("shows total score and tier badge when collapsed", () => {
			renderBreakdown(makeFitScore());

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("92");
			expect(breakdown.textContent).toContain("High");
		});

		it("shows chevron icon for toggle", () => {
			renderBreakdown(makeFitScore());

			expect(screen.getByTestId(TOGGLE_TESTID)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Expanded state
	// -----------------------------------------------------------------------

	describe("expanded state", () => {
		it("expands component rows on toggle click", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			expect(screen.getByTestId(PANEL_TESTID)).toBeInTheDocument();
		});

		it("shows all 5 component names in order", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
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
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			expect(panel.textContent).toContain("82");
			expect(panel.textContent).toContain("95");
			expect(panel.textContent).toContain("88");
			expect(panel.textContent).toContain("90");
			expect(panel.textContent).toContain("100");
		});

		it("shows weight percentages", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
			expect(panel.textContent).toContain("40%");
			expect(panel.textContent).toContain("25%");
			expect(panel.textContent).toContain("15%");
			// 10% appears twice (role_title + location_logistics)
			const matches = panel.textContent?.match(/10%/g);
			expect(matches?.length).toBeGreaterThanOrEqual(2);
		});

		it("shows weighted contributions (Math.round(score * weight))", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const panel = screen.getByTestId(PANEL_TESTID);
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
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));
			expect(screen.getByTestId(PANEL_TESTID)).toBeInTheDocument();

			await user.click(screen.getByTestId(TOGGLE_TESTID));
			expect(screen.queryByTestId(PANEL_TESTID)).not.toBeInTheDocument();
		});

		it("changes chevron direction when expanded", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

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
		it("shows Medium tier for score 75", () => {
			renderBreakdown(makeFitScore({ total: 75 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Medium");
		});

		it("shows Low tier for score 60", () => {
			renderBreakdown(makeFitScore({ total: 60 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Low");
		});

		it("shows Poor tier for score 59", () => {
			renderBreakdown(makeFitScore({ total: 59 }));

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown.textContent).toContain("Poor");
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("toggle has aria-expanded false when collapsed", () => {
			renderBreakdown(makeFitScore());

			expect(screen.getByTestId(TOGGLE_TESTID)).toHaveAttribute(
				"aria-expanded",
				"false",
			);
		});

		it("toggle has aria-expanded true when expanded", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			expect(screen.getByTestId(TOGGLE_TESTID)).toHaveAttribute(
				"aria-expanded",
				"true",
			);
		});

		it("component list uses list semantics", async () => {
			const user = userEvent.setup();
			renderBreakdown(makeFitScore());

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
			renderBreakdown(zeroFit);

			await user.click(screen.getByTestId(TOGGLE_TESTID));

			const hardRow = screen.getByTestId("fit-component-hard_skills");
			expect(hardRow.textContent).toContain("0");
		});

		it("merges custom className", () => {
			renderBreakdown(makeFitScore(), "mt-4");

			const breakdown = screen.getByTestId(BREAKDOWN_TESTID);
			expect(breakdown).toHaveClass("mt-4");
		});
	});
});
