/**
 * Tests for the ScoreExplanation component (§7.9).
 *
 * REQ-012 §8.3: Explanation section with summary and categorized icon lists.
 * REQ-008 §8.1: Score explanation display structure.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ScoreExplanation as ScoreExplanationType } from "@/types/job";

import { ScoreExplanation } from "./score-explanation";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "score-explanation";
const NOT_AVAILABLE_TESTID = "explanation-not-available";
const SUMMARY_TESTID = "explanation-summary";
const STRENGTHS_TESTID = "explanation-strengths";
const GAPS_TESTID = "explanation-gaps";
const STRETCH_TESTID = "explanation-stretch";
const WARNINGS_TESTID = "explanation-warnings";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeExplanation(
	overrides?: Partial<ScoreExplanationType>,
): ScoreExplanationType {
	return {
		summary: "Strong technical fit with 4 of 5 required skills.",
		strengths: ["Python", "FastAPI", "SQL"],
		gaps: ["Kubernetes (required)", "Terraform (preferred)"],
		stretch_opportunities: ["Kubernetes aligns with growth targets"],
		warnings: [],
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderExplanation(
	explanation?: ScoreExplanationType,
	className?: string,
) {
	return render(
		<ScoreExplanation explanation={explanation} className={className} />,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ScoreExplanation", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Not available
	// -----------------------------------------------------------------------

	describe("not available", () => {
		it("renders 'No explanation' badge when undefined", () => {
			renderExplanation(undefined);

			expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toBeInTheDocument();
		});

		it("does not render summary or sections when undefined", () => {
			renderExplanation(undefined);

			expect(screen.queryByTestId(SUMMARY_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(STRENGTHS_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(GAPS_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(STRETCH_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(WARNINGS_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Summary
	// -----------------------------------------------------------------------

	describe("summary", () => {
		it("renders summary text", () => {
			renderExplanation(makeExplanation());

			expect(screen.getByTestId(SUMMARY_TESTID)).toHaveTextContent(
				"Strong technical fit with 4 of 5 required skills.",
			);
		});

		it("renders summary in a paragraph element", () => {
			renderExplanation(makeExplanation());

			const summary = screen.getByTestId(SUMMARY_TESTID);
			expect(summary.tagName).toBe("P");
		});
	});

	// -----------------------------------------------------------------------
	// Strengths
	// -----------------------------------------------------------------------

	describe("strengths", () => {
		it("renders strengths section when non-empty", () => {
			renderExplanation(makeExplanation());

			expect(screen.getByTestId(STRENGTHS_TESTID)).toBeInTheDocument();
		});

		it("renders each strength as a list item", () => {
			renderExplanation(makeExplanation());

			const section = screen.getByTestId(STRENGTHS_TESTID);
			const items = within(section).getAllByRole("listitem");
			expect(items).toHaveLength(3);
			expect(items[0]).toHaveTextContent("Python");
			expect(items[1]).toHaveTextContent("FastAPI");
			expect(items[2]).toHaveTextContent("SQL");
		});

		it("hides strengths section when array is empty", () => {
			renderExplanation(makeExplanation({ strengths: [] }));

			expect(screen.queryByTestId(STRENGTHS_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Gaps
	// -----------------------------------------------------------------------

	describe("gaps", () => {
		it("renders gaps section when non-empty", () => {
			renderExplanation(makeExplanation());

			expect(screen.getByTestId(GAPS_TESTID)).toBeInTheDocument();
		});

		it("renders each gap as a list item", () => {
			renderExplanation(makeExplanation());

			const section = screen.getByTestId(GAPS_TESTID);
			const items = within(section).getAllByRole("listitem");
			expect(items).toHaveLength(2);
			expect(items[0]).toHaveTextContent("Kubernetes (required)");
			expect(items[1]).toHaveTextContent("Terraform (preferred)");
		});

		it("hides gaps section when array is empty", () => {
			renderExplanation(makeExplanation({ gaps: [] }));

			expect(screen.queryByTestId(GAPS_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Stretch opportunities
	// -----------------------------------------------------------------------

	describe("stretch opportunities", () => {
		it("renders stretch section when non-empty", () => {
			renderExplanation(makeExplanation());

			expect(screen.getByTestId(STRETCH_TESTID)).toBeInTheDocument();
		});

		it("renders each opportunity as a list item", () => {
			renderExplanation(makeExplanation());

			const section = screen.getByTestId(STRETCH_TESTID);
			const items = within(section).getAllByRole("listitem");
			expect(items).toHaveLength(1);
			expect(items[0]).toHaveTextContent(
				"Kubernetes aligns with growth targets",
			);
		});

		it("hides stretch section when array is empty", () => {
			renderExplanation(makeExplanation({ stretch_opportunities: [] }));

			expect(screen.queryByTestId(STRETCH_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Warnings
	// -----------------------------------------------------------------------

	describe("warnings", () => {
		it("renders warnings section when non-empty", () => {
			renderExplanation(
				makeExplanation({ warnings: ["Salary not disclosed"] }),
			);

			expect(screen.getByTestId(WARNINGS_TESTID)).toBeInTheDocument();
		});

		it("renders each warning as a list item", () => {
			renderExplanation(
				makeExplanation({
					warnings: ["Salary not disclosed", "High ghost risk"],
				}),
			);

			const section = screen.getByTestId(WARNINGS_TESTID);
			const items = within(section).getAllByRole("listitem");
			expect(items).toHaveLength(2);
			expect(items[0]).toHaveTextContent("Salary not disclosed");
			expect(items[1]).toHaveTextContent("High ghost risk");
		});

		it("hides warnings section when array is empty", () => {
			renderExplanation(makeExplanation({ warnings: [] }));

			expect(screen.queryByTestId(WARNINGS_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// All arrays empty
	// -----------------------------------------------------------------------

	describe("all arrays empty", () => {
		it("still shows summary when all category arrays are empty", () => {
			renderExplanation(
				makeExplanation({
					strengths: [],
					gaps: [],
					stretch_opportunities: [],
					warnings: [],
				}),
			);

			expect(screen.getByTestId(SUMMARY_TESTID)).toBeInTheDocument();
		});

		it("renders no category sections when all arrays are empty", () => {
			renderExplanation(
				makeExplanation({
					strengths: [],
					gaps: [],
					stretch_opportunities: [],
					warnings: [],
				}),
			);

			expect(screen.queryByTestId(STRENGTHS_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(GAPS_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(STRETCH_TESTID)).not.toBeInTheDocument();
			expect(screen.queryByTestId(WARNINGS_TESTID)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edge cases
	// -----------------------------------------------------------------------

	describe("edge cases", () => {
		it("renders single-item arrays correctly", () => {
			renderExplanation(
				makeExplanation({
					strengths: ["One strength"],
					gaps: ["One gap"],
					stretch_opportunities: ["One opportunity"],
					warnings: ["One warning"],
				}),
			);

			const strengths = screen.getByTestId(STRENGTHS_TESTID);
			expect(within(strengths).getAllByRole("listitem")).toHaveLength(1);

			const gaps = screen.getByTestId(GAPS_TESTID);
			expect(within(gaps).getAllByRole("listitem")).toHaveLength(1);

			const stretch = screen.getByTestId(STRETCH_TESTID);
			expect(within(stretch).getAllByRole("listitem")).toHaveLength(1);

			const warnings = screen.getByTestId(WARNINGS_TESTID);
			expect(within(warnings).getAllByRole("listitem")).toHaveLength(1);
		});

		it("merges custom className", () => {
			renderExplanation(makeExplanation(), "mt-4");

			const section = screen.getByTestId(SECTION_TESTID);
			expect(section).toHaveClass("mt-4");
		});
	});
});
