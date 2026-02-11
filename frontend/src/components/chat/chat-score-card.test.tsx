/**
 * Tests for the score summary card displayed inline in chat.
 *
 * REQ-012 §5.3: Structured chat cards — score summary card.
 * Displays fit score breakdown (5 components with weights),
 * stretch score with tier, strengths, and gaps.
 */

import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import type { ScoreCardData } from "@/types/chat";
import type {
	FitScoreResult,
	ScoreExplanation,
	StretchScoreResult,
} from "@/types/job";

import { ChatScoreCard, formatComponentLabel } from "./chat-score-card";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const FIT_SCORE: FitScoreResult = {
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
};

const STRETCH_SCORE: StretchScoreResult = {
	total: 45,
	components: {
		target_role: 50,
		target_skills: 40,
		growth_trajectory: 45,
	},
	weights: {
		target_role: 0.5,
		target_skills: 0.4,
		growth_trajectory: 0.1,
	},
};

const EXPLANATION: ScoreExplanation = {
	summary: "Strong match with growth potential.",
	strengths: ["Python", "FastAPI", "SQL"],
	gaps: ["Kubernetes (required)"],
	stretch_opportunities: ["Cloud infrastructure"],
	warnings: [],
};

const FULL_SCORE: ScoreCardData = {
	jobId: "job-123",
	jobTitle: "Senior Scrum Master",
	fit: FIT_SCORE,
	stretch: STRETCH_SCORE,
	explanation: EXPLANATION,
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const CARD_SELECTOR = '[data-slot="chat-score-card"]';
const FIT_SECTION_SELECTOR = '[data-slot="fit-section"]';
const FIT_COMPONENTS_SELECTOR = '[data-slot="fit-components"]';
const STRETCH_SECTION_SELECTOR = '[data-slot="stretch-section"]';
const STRENGTHS_SELECTOR = '[data-slot="score-strengths"]';
const GAPS_SELECTOR = '[data-slot="score-gaps"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderCard(props: Partial<ComponentProps<typeof ChatScoreCard>> = {}) {
	return render(<ChatScoreCard data={FULL_SCORE} {...props} />);
}

// ---------------------------------------------------------------------------
// formatComponentLabel
// ---------------------------------------------------------------------------

describe("formatComponentLabel", () => {
	it("converts hard_skills to 'Hard Skills'", () => {
		expect(formatComponentLabel("hard_skills")).toBe("Hard Skills");
	});

	it("converts experience_level to 'Experience Level'", () => {
		expect(formatComponentLabel("experience_level")).toBe("Experience Level");
	});

	it("converts location_logistics to 'Location Logistics'", () => {
		expect(formatComponentLabel("location_logistics")).toBe(
			"Location Logistics",
		);
	});

	it("handles single word", () => {
		expect(formatComponentLabel("skills")).toBe("Skills");
	});
});

// ---------------------------------------------------------------------------
// Score Summary Card
// ---------------------------------------------------------------------------

describe("ChatScoreCard", () => {
	// -----------------------------------------------------------------------
	// Fit score section
	// -----------------------------------------------------------------------

	describe("fit score section", () => {
		it("renders fit score total", () => {
			const { container } = renderCard();

			const fitSection = container.querySelector(FIT_SECTION_SELECTOR);
			expect(fitSection?.textContent).toContain("92");
		});

		it("renders fit tier label", () => {
			const { container } = renderCard();

			const fitSection = container.querySelector(FIT_SECTION_SELECTOR);
			expect(fitSection?.textContent).toContain("High");
		});

		it("renders all 5 fit score components", () => {
			const { container } = renderCard();

			const components = container.querySelector(FIT_COMPONENTS_SELECTOR);
			expect(components?.textContent).toContain("Hard Skills");
			expect(components?.textContent).toContain("82");
			expect(components?.textContent).toContain("40%");
		});

		it("renders experience component with score and weight", () => {
			const { container } = renderCard();

			const components = container.querySelector(FIT_COMPONENTS_SELECTOR);
			expect(components?.textContent).toContain("Experience Level");
			expect(components?.textContent).toContain("95");
			expect(components?.textContent).toContain("25%");
		});

		it("renders soft skills component", () => {
			const { container } = renderCard();

			const components = container.querySelector(FIT_COMPONENTS_SELECTOR);
			expect(components?.textContent).toContain("Soft Skills");
			expect(components?.textContent).toContain("88");
			expect(components?.textContent).toContain("15%");
		});

		it("renders role title component", () => {
			const { container } = renderCard();

			const components = container.querySelector(FIT_COMPONENTS_SELECTOR);
			expect(components?.textContent).toContain("Role Title");
			expect(components?.textContent).toContain("90");
			expect(components?.textContent).toContain("10%");
		});

		it("renders location component", () => {
			const { container } = renderCard();

			const components = container.querySelector(FIT_COMPONENTS_SELECTOR);
			expect(components?.textContent).toContain("Location Logistics");
			expect(components?.textContent).toContain("100");
		});
	});

	// -----------------------------------------------------------------------
	// Stretch score section
	// -----------------------------------------------------------------------

	describe("stretch score section", () => {
		it("renders stretch score total", () => {
			const { container } = renderCard();

			const stretchSection = container.querySelector(STRETCH_SECTION_SELECTOR);
			expect(stretchSection?.textContent).toContain("45");
		});

		it("renders stretch tier label", () => {
			const { container } = renderCard();

			const stretchSection = container.querySelector(STRETCH_SECTION_SELECTOR);
			expect(stretchSection?.textContent).toContain("Lateral");
		});
	});

	// -----------------------------------------------------------------------
	// Strengths and gaps
	// -----------------------------------------------------------------------

	describe("strengths and gaps", () => {
		it("renders strengths list", () => {
			const { container } = renderCard();

			const strengths = container.querySelector(STRENGTHS_SELECTOR);
			expect(strengths?.textContent).toContain("Python");
			expect(strengths?.textContent).toContain("FastAPI");
			expect(strengths?.textContent).toContain("SQL");
		});

		it("renders gaps list", () => {
			const { container } = renderCard();

			const gaps = container.querySelector(GAPS_SELECTOR);
			expect(gaps?.textContent).toContain("Kubernetes (required)");
		});

		it("does not render strengths section when empty", () => {
			const noStrengths: ScoreCardData = {
				...FULL_SCORE,
				explanation: { ...EXPLANATION, strengths: [] },
			};
			const { container } = renderCard({ data: noStrengths });

			expect(
				container.querySelector(STRENGTHS_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render gaps section when empty", () => {
			const noGaps: ScoreCardData = {
				...FULL_SCORE,
				explanation: { ...EXPLANATION, gaps: [] },
			};
			const { container } = renderCard({ data: noGaps });

			expect(container.querySelector(GAPS_SELECTOR)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Structure & styling
	// -----------------------------------------------------------------------

	describe("structure", () => {
		it("has data-slot attribute", () => {
			const { container } = renderCard();

			expect(container.querySelector(CARD_SELECTOR)).toBeInTheDocument();
		});

		it("renders with card styling", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveClass("rounded-lg");
			expect(card).toHaveClass("border");
		});

		it("merges custom className", () => {
			const { container } = renderCard({ className: "mt-2" });

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveClass("mt-2");
		});

		it("has correct section order: fit → stretch → strengths → gaps", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			const allSlots = Array.from(card?.querySelectorAll("[data-slot]") ?? []);
			const slotNames = allSlots.map((el) => el.getAttribute("data-slot"));

			const fitIdx = slotNames.indexOf("fit-section");
			const stretchIdx = slotNames.indexOf("stretch-section");
			const strengthsIdx = slotNames.indexOf("score-strengths");
			const gapsIdx = slotNames.indexOf("score-gaps");

			expect(fitIdx).toBeLessThan(stretchIdx);
			expect(stretchIdx).toBeLessThan(strengthsIdx);
			expect(strengthsIdx).toBeLessThan(gapsIdx);
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("has aria-label describing the score card", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Score summary"),
			);
		});

		it("fit components list uses list semantics", () => {
			renderCard();

			const list = screen.getByRole("list", { name: /fit.*components/i });
			expect(list).toBeInTheDocument();
		});

		it("each fit component is a list item", () => {
			renderCard();

			const items = screen.getAllByRole("listitem");
			expect(items.length).toBeGreaterThanOrEqual(5);
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like strength text as plain text", () => {
			const xssScore: ScoreCardData = {
				...FULL_SCORE,
				explanation: {
					...EXPLANATION,
					strengths: ['<script>alert("xss")</script>'],
				},
			};
			renderCard({ data: xssScore });

			expect(
				screen.getByText('<script>alert("xss")</script>'),
			).toBeInTheDocument();
		});

		it("renders HTML-like gap text as plain text", () => {
			const xssScore: ScoreCardData = {
				...FULL_SCORE,
				explanation: {
					...EXPLANATION,
					gaps: ["<img src=x onerror=alert(1)>"],
				},
			};
			const { container } = renderCard({ data: xssScore });

			expect(container.querySelector("img")).not.toBeInTheDocument();
		});
	});
});
