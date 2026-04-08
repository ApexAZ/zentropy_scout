/**
 * Tests for the compact job card displayed inline in chat.
 *
 * REQ-012 §5.3: Structured chat cards — job card (compact).
 * Displays job title, company/location/work model, scores,
 * salary range, and action buttons (View, Favorite, Dismiss).
 * REQ-034 §9.3: Fit/stretch visual treatment — Growth Role amber
 * chip, contextual score labels ({fit}% match vs {stretch}% stretch).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { JobCardData } from "@/types/chat";

import { ChatJobCard, formatSalary, isStretchRole } from "./chat-job-card";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const FULL_JOB: JobCardData = {
	jobId: "job-123",
	jobTitle: "Senior Scrum Master",
	companyName: "Acme Corp",
	location: "Austin, TX",
	workModel: "Remote",
	fitScore: 92,
	stretchScore: 45,
	salaryMin: 140_000,
	salaryMax: 160_000,
	salaryCurrency: "USD",
	isFavorite: false,
};

const MINIMAL_JOB: JobCardData = {
	jobId: "job-456",
	jobTitle: "Frontend Developer",
	companyName: "Startup Inc",
	location: null,
	workModel: null,
	fitScore: null,
	stretchScore: null,
	salaryMin: null,
	salaryMax: null,
	salaryCurrency: null,
	isFavorite: false,
};

const FAVORITED_JOB: JobCardData = {
	...FULL_JOB,
	isFavorite: true,
};

/** Stretch job by score rule: stretchScore (80) > fitScore (60) + 10. */
const STRETCH_JOB: JobCardData = {
	...FULL_JOB,
	fitScore: 60,
	stretchScore: 80,
};

/** Fit job: stretchScore (70) is NOT > fitScore (60) + 10. */
const NEAR_EQUAL_JOB: JobCardData = {
	...FULL_JOB,
	fitScore: 60,
	stretchScore: 70,
};

/** Explicit search_bucket="stretch" overrides score rule. */
const BUCKET_STRETCH_JOB: JobCardData = {
	...FULL_JOB,
	fitScore: 92,
	stretchScore: 45,
	searchBucket: "stretch",
};

/** Explicit search_bucket="fit" overrides score rule even when scores say stretch. */
const BUCKET_FIT_JOB: JobCardData = {
	...FULL_JOB,
	fitScore: 60,
	stretchScore: 80,
	searchBucket: "fit",
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const CARD_SELECTOR = '[data-slot="chat-job-card"]';
const META_SELECTOR = '[data-slot="job-meta"]';
const SCORES_SELECTOR = '[data-slot="job-scores"]';
const SALARY_SELECTOR = '[data-slot="job-salary"]';
const GROWTH_CHIP_SELECTOR = '[data-slot="growth-chip"]';
const SCORE_LABEL_SELECTOR = '[data-slot="score-label"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderCard(props: Partial<ComponentProps<typeof ChatJobCard>> = {}) {
	return render(<ChatJobCard data={FULL_JOB} {...props} />);
}

// ---------------------------------------------------------------------------
// formatSalary
// ---------------------------------------------------------------------------

describe("formatSalary", () => {
	it("formats USD range with k abbreviation", () => {
		expect(formatSalary(140_000, 160_000, "USD")).toBe("$140k–$160k");
	});

	it("formats single salary value", () => {
		expect(formatSalary(120_000, null, "USD")).toBe("$120k+");
	});

	it("formats max-only salary", () => {
		expect(formatSalary(null, 200_000, "USD")).toBe("Up to $200k");
	});

	it("formats non-USD currency", () => {
		expect(formatSalary(80_000, 100_000, "GBP")).toBe("£80k–£100k");
	});

	it("formats EUR currency", () => {
		expect(formatSalary(60_000, 90_000, "EUR")).toBe("€60k–€90k");
	});

	it("returns null when no salary info", () => {
		expect(formatSalary(null, null, null)).toBeNull();
	});

	it("returns null when no salary amounts even with currency", () => {
		expect(formatSalary(null, null, "USD")).toBeNull();
	});

	it("falls back to currency code for unknown currencies", () => {
		expect(formatSalary(50_000, 70_000, "JPY")).toBe("JPY 50k–70k");
	});

	it("formats exact amounts under 1000", () => {
		expect(formatSalary(500, 800, "USD")).toBe("$500–$800");
	});
});

// ---------------------------------------------------------------------------
// isStretchRole (REQ-034 §9.3)
// ---------------------------------------------------------------------------

describe("isStretchRole", () => {
	describe("explicit searchBucket", () => {
		it("returns true for stretch bucket regardless of scores", () => {
			expect(isStretchRole("stretch", 92, 45)).toBe(true);
		});

		it("returns false for fit bucket regardless of scores", () => {
			expect(isStretchRole("fit", 40, 80)).toBe(false);
		});

		it("returns false for manual bucket", () => {
			expect(isStretchRole("manual", 40, 80)).toBe(false);
		});

		it("returns false for pool bucket", () => {
			expect(isStretchRole("pool", 40, 80)).toBe(false);
		});
	});

	describe("score-based fallback", () => {
		it("returns true when stretchScore exceeds fitScore by more than 10", () => {
			expect(isStretchRole(null, 60, 71)).toBe(true);
		});

		it("returns false at the exact +10 boundary", () => {
			expect(isStretchRole(null, 60, 70)).toBe(false);
		});

		it("returns false when fitScore exceeds stretchScore", () => {
			expect(isStretchRole(null, 92, 45)).toBe(false);
		});

		it("returns true when only stretchScore is present", () => {
			expect(isStretchRole(null, null, 65)).toBe(true);
		});

		it("returns false when only fitScore is present", () => {
			expect(isStretchRole(null, 75, null)).toBe(false);
		});

		it("returns false when both scores are null", () => {
			expect(isStretchRole(null, null, null)).toBe(false);
		});

		it("returns false when searchBucket is undefined and scores favor fit", () => {
			expect(isStretchRole(undefined, 80, 50)).toBe(false);
		});
	});
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ChatJobCard", () => {
	describe("content display", () => {
		it("renders job title", () => {
			renderCard();

			expect(screen.getByText(FULL_JOB.jobTitle)).toBeInTheDocument();
		});

		it("renders company name in meta line", () => {
			const { container } = renderCard();

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("Acme Corp");
		});

		it("renders location in meta line", () => {
			const { container } = renderCard();

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("Austin, TX");
		});

		it("renders work model in meta line", () => {
			const { container } = renderCard();

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("Remote");
		});

		it("renders dot separators in meta line", () => {
			const { container } = renderCard();

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("·");
		});

		it("renders fit score badge", () => {
			const { container } = renderCard();

			const scores = container.querySelector(SCORES_SELECTOR);
			expect(scores?.textContent).toContain("92");
		});

		it("renders stretch score badge", () => {
			const { container } = renderCard();

			const scores = container.querySelector(SCORES_SELECTOR);
			expect(scores?.textContent).toContain("45");
		});

		it("renders salary range", () => {
			const { container } = renderCard();

			const salary = container.querySelector(SALARY_SELECTOR);
			expect(salary?.textContent).toContain("$140k");
			expect(salary?.textContent).toContain("$160k");
		});
	});

	// -----------------------------------------------------------------------
	// Minimal data (null fields)
	// -----------------------------------------------------------------------

	describe("minimal data", () => {
		it("renders without location", () => {
			const { container } = renderCard({ data: MINIMAL_JOB });

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("Startup Inc");
			expect(meta?.textContent).not.toContain("·");
		});

		it("does not render scores section when both are null", () => {
			const { container } = renderCard({ data: MINIMAL_JOB });

			expect(container.querySelector(SCORES_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not render salary section when salary is null", () => {
			const { container } = renderCard({ data: MINIMAL_JOB });

			expect(container.querySelector(SALARY_SELECTOR)).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Action buttons
	// -----------------------------------------------------------------------

	describe("action buttons", () => {
		it("renders View button", () => {
			renderCard();

			expect(screen.getByRole("button", { name: /view/i })).toBeInTheDocument();
		});

		it("renders Favorite button", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: /favorite/i }),
			).toBeInTheDocument();
		});

		it("renders Dismiss button", () => {
			renderCard();

			expect(
				screen.getByRole("button", { name: /dismiss/i }),
			).toBeInTheDocument();
		});

		it("calls onView with jobId when View is clicked", async () => {
			const user = userEvent.setup();
			const onView = vi.fn();
			renderCard({ onView });

			await user.click(screen.getByRole("button", { name: /view/i }));

			expect(onView).toHaveBeenCalledWith("job-123");
		});

		it("calls onFavorite with jobId when Favorite is clicked", async () => {
			const user = userEvent.setup();
			const onFavorite = vi.fn();
			renderCard({ onFavorite });

			await user.click(screen.getByRole("button", { name: /favorite/i }));

			expect(onFavorite).toHaveBeenCalledWith("job-123");
		});

		it("calls onDismiss with jobId when Dismiss is clicked", async () => {
			const user = userEvent.setup();
			const onDismiss = vi.fn();
			renderCard({ onDismiss });

			await user.click(screen.getByRole("button", { name: /dismiss/i }));

			expect(onDismiss).toHaveBeenCalledWith("job-123");
		});

		it("shows filled heart icon when favorited", () => {
			const { container } = renderCard({ data: FAVORITED_JOB });

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute("data-favorited", "true");
		});

		it("shows empty heart icon when not favorited", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute("data-favorited", "false");
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

		it("has correct DOM order: title → meta → scores → salary → actions", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			const children = Array.from(card?.children ?? []);
			const slots = children.map(
				(el) => el.getAttribute("data-slot") ?? el.tagName,
			);

			const titleIdx = slots.indexOf("job-title");
			const metaIdx = slots.indexOf("job-meta");
			const scoresIdx = slots.indexOf("job-scores");
			const salaryIdx = slots.indexOf("job-salary");
			const actionsIdx = slots.indexOf("job-actions");

			expect(titleIdx).toBeLessThan(metaIdx);
			expect(metaIdx).toBeLessThan(scoresIdx);
			expect(scoresIdx).toBeLessThan(salaryIdx);
			expect(salaryIdx).toBeLessThan(actionsIdx);
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("has aria-label describing the job", () => {
			const { container } = renderCard();

			const card = container.querySelector(CARD_SELECTOR);
			expect(card).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Senior Scrum Master"),
			);
			expect(card).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Acme Corp"),
			);
		});

		it("action buttons have accessible names", () => {
			renderCard();

			expect(screen.getByRole("button", { name: /view/i })).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /favorite/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /dismiss/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like job title as plain text", () => {
			const xssJob: JobCardData = {
				...FULL_JOB,
				jobTitle: '<script>alert("xss")</script>',
			};
			renderCard({ data: xssJob });

			expect(
				screen.getByText('<script>alert("xss")</script>'),
			).toBeInTheDocument();
		});

		it("renders HTML-like company name as plain text", () => {
			const xssJob: JobCardData = {
				...FULL_JOB,
				companyName: "<img src=x onerror=alert(1)>",
			};
			const { container } = renderCard({ data: xssJob });

			const meta = container.querySelector(META_SELECTOR);
			expect(meta?.textContent).toContain("<img src=x onerror=alert(1)>");
			expect(container.querySelector("img")).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Fit/stretch visual treatment (REQ-034 §9.3)
	// -----------------------------------------------------------------------

	describe("fit/stretch visual treatment", () => {
		describe("fit jobs (no Growth chip)", () => {
			it("does not show Growth Role chip when fit by score rule", () => {
				const { container } = renderCard();

				expect(
					container.querySelector(GROWTH_CHIP_SELECTOR),
				).not.toBeInTheDocument();
			});

			it("shows fit score label with '% match'", () => {
				const { container } = renderCard();

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("92% match");
			});

			it("does not show Growth Role chip for near-equal scores", () => {
				const { container } = renderCard({ data: NEAR_EQUAL_JOB });

				expect(
					container.querySelector(GROWTH_CHIP_SELECTOR),
				).not.toBeInTheDocument();
			});

			it("shows fit score label for near-equal scores", () => {
				const { container } = renderCard({ data: NEAR_EQUAL_JOB });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("60% match");
			});
		});

		describe("stretch jobs (Growth chip)", () => {
			it("shows Growth Role chip when stretch by score rule", () => {
				const { container } = renderCard({ data: STRETCH_JOB });

				const chip = container.querySelector(GROWTH_CHIP_SELECTOR);
				expect(chip).toBeInTheDocument();
				expect(chip?.textContent).toBe("Growth Role");
			});

			it("shows stretch score label with '% stretch'", () => {
				const { container } = renderCard({ data: STRETCH_JOB });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("80% stretch");
			});

			it("renders Growth Role chip as a pill badge", () => {
				const { container } = renderCard({ data: STRETCH_JOB });

				const chip = container.querySelector(GROWTH_CHIP_SELECTOR);
				expect(chip).toHaveClass("rounded-full");
			});
		});

		describe("search_bucket prop overrides score rule", () => {
			it("shows Growth chip when searchBucket is stretch despite fit scores", () => {
				const { container } = renderCard({ data: BUCKET_STRETCH_JOB });

				const chip = container.querySelector(GROWTH_CHIP_SELECTOR);
				expect(chip).toBeInTheDocument();
				expect(chip?.textContent).toBe("Growth Role");
			});

			it("shows stretch score label when searchBucket is stretch", () => {
				const { container } = renderCard({ data: BUCKET_STRETCH_JOB });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("45% stretch");
			});

			it("hides Growth chip when searchBucket is fit despite stretch scores", () => {
				const { container } = renderCard({ data: BUCKET_FIT_JOB });

				expect(
					container.querySelector(GROWTH_CHIP_SELECTOR),
				).not.toBeInTheDocument();
			});

			it("shows fit score label when searchBucket is fit", () => {
				const { container } = renderCard({ data: BUCKET_FIT_JOB });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("60% match");
			});
		});

		describe("edge cases", () => {
			it("does not show score label when both scores are null", () => {
				const { container } = renderCard({ data: MINIMAL_JOB });

				expect(
					container.querySelector(SCORE_LABEL_SELECTOR),
				).not.toBeInTheDocument();
			});

			it("shows fit score label when only fitScore is present", () => {
				const oneScoreJob: JobCardData = {
					...FULL_JOB,
					fitScore: 75,
					stretchScore: null,
				};
				const { container } = renderCard({ data: oneScoreJob });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("75% match");
			});

			it("shows stretch score label when only stretchScore is present", () => {
				const oneScoreJob: JobCardData = {
					...FULL_JOB,
					fitScore: null,
					stretchScore: 65,
				};
				const { container } = renderCard({ data: oneScoreJob });

				const label = container.querySelector(SCORE_LABEL_SELECTOR);
				expect(label?.textContent).toBe("65% stretch");
			});
		});
	});
});
