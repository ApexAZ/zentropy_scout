/**
 * Tests for the ScoreTierBadge component.
 *
 * REQ-012 §8.4: Score tier display with numeric score + tier label + color.
 * REQ-008 §7.1–7.2: Fit and Stretch tier ranges.
 */

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreTierBadge } from "./score-tier-badge";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FIT = "fit" as const;
const STRETCH = "stretch" as const;
const ROOT_SELECTOR = '[data-slot="score-tier-badge"]';
const NOT_SCORED_TEXT = "Not scored";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBadge(
	props: Partial<ComponentProps<typeof ScoreTierBadge>> = {},
) {
	return render(<ScoreTierBadge score={92} scoreType={FIT} {...props} />);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ScoreTierBadge", () => {
	describe("rendering", () => {
		it("has data-slot attribute", () => {
			const { container } = renderBadge();

			expect(container.querySelector(ROOT_SELECTOR)).toBeInTheDocument();
		});

		it("applies custom className", () => {
			const { container } = renderBadge({ className: "ml-2" });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveClass("ml-2");
		});

		it("sets data-score-type attribute matching scoreType prop", () => {
			const { container } = renderBadge({ scoreType: STRETCH });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"data-score-type",
				STRETCH,
			);
		});

		it("sets data-tier attribute matching derived tier", () => {
			const { container } = renderBadge({ score: 92, scoreType: FIT });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"data-tier",
				"high",
			);
		});
	});

	// ---------------------------------------------------------------------------
	// Fit score tiers
	// ---------------------------------------------------------------------------

	describe("fit score tiers", () => {
		it("renders High tier for score 92 with success color", () => {
			const { container } = renderBadge({ score: 92, scoreType: FIT });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-success");
			expect(screen.getByText("92")).toBeInTheDocument();
			expect(screen.getByText("High")).toBeInTheDocument();
		});

		it("renders Medium tier for score 80 with primary color", () => {
			const { container } = renderBadge({ score: 80, scoreType: FIT });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-primary");
			expect(screen.getByText("Medium")).toBeInTheDocument();
		});

		it("renders Low tier for score 65 with warning color", () => {
			const { container } = renderBadge({ score: 65, scoreType: FIT });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-warning");
			expect(screen.getByText("Low")).toBeInTheDocument();
		});

		it("renders Poor tier for score 30 with destructive color", () => {
			const { container } = renderBadge({ score: 30, scoreType: FIT });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-destructive");
			expect(screen.getByText("Poor")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Fit score boundaries
	// ---------------------------------------------------------------------------

	describe("fit score boundaries", () => {
		it("score 90 is High (inclusive lower bound)", () => {
			expect(screen.queryByText("High")).not.toBeInTheDocument();
			renderBadge({ score: 90, scoreType: FIT });

			expect(screen.getByText("High")).toBeInTheDocument();
		});

		it("score 75 is Medium (inclusive lower bound)", () => {
			renderBadge({ score: 75, scoreType: FIT });

			expect(screen.getByText("Medium")).toBeInTheDocument();
		});

		it("score 60 is Low (inclusive lower bound)", () => {
			renderBadge({ score: 60, scoreType: FIT });

			expect(screen.getByText("Low")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Stretch score tiers
	// ---------------------------------------------------------------------------

	describe("stretch score tiers", () => {
		it("renders High Growth tier for score 85 with purple color", () => {
			const { container } = renderBadge({ score: 85, scoreType: STRETCH });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-stretch-high");
			expect(screen.getByText("85")).toBeInTheDocument();
			expect(screen.getByText("High Growth")).toBeInTheDocument();
		});

		it("renders Moderate Growth tier for score 70 with primary color", () => {
			const { container } = renderBadge({ score: 70, scoreType: STRETCH });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-primary");
			expect(screen.getByText("Moderate Growth")).toBeInTheDocument();
		});

		it("renders Lateral tier for score 50 with gray color", () => {
			const { container } = renderBadge({ score: 50, scoreType: STRETCH });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-stretch-lateral");
			expect(screen.getByText("Lateral")).toBeInTheDocument();
		});

		it("renders Low Growth tier for score 20 with muted color", () => {
			const { container } = renderBadge({ score: 20, scoreType: STRETCH });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-muted");
			expect(screen.getByText("Low Growth")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Stretch score boundaries
	// ---------------------------------------------------------------------------

	describe("stretch score boundaries", () => {
		it("score 80 is High Growth (inclusive lower bound)", () => {
			renderBadge({ score: 80, scoreType: STRETCH });

			expect(screen.getByText("High Growth")).toBeInTheDocument();
		});

		it("score 60 is Moderate Growth (inclusive lower bound)", () => {
			renderBadge({ score: 60, scoreType: STRETCH });

			expect(screen.getByText("Moderate Growth")).toBeInTheDocument();
		});

		it("score 40 is Lateral (inclusive lower bound)", () => {
			renderBadge({ score: 40, scoreType: STRETCH });

			expect(screen.getByText("Lateral")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Null score
	// ---------------------------------------------------------------------------

	describe("null score", () => {
		it("renders 'Not scored' text with no number", () => {
			renderBadge({ score: null });

			expect(screen.getByText(NOT_SCORED_TEXT)).toBeInTheDocument();
			expect(screen.queryByText("92")).not.toBeInTheDocument();
		});

		it("uses border styling for unscored state", () => {
			const { container } = renderBadge({ score: null });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("border");
			expect(root).toHaveAttribute("data-tier", "none");
		});
	});

	// ---------------------------------------------------------------------------
	// Accessibility
	// ---------------------------------------------------------------------------

	describe("accessibility", () => {
		it("scored badge has descriptive aria-label", () => {
			const { container } = renderBadge({ score: 92, scoreType: FIT });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"aria-label",
				"Fit score: 92, High",
			);
		});

		it("null badge has 'Not scored' aria-label", () => {
			const { container } = renderBadge({ score: null, scoreType: STRETCH });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"aria-label",
				"Stretch score: Not scored",
			);
		});
	});
});
