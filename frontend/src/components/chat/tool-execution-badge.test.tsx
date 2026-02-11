/**
 * Tests for the tool execution badge component.
 *
 * REQ-012 §5.4: On tool_start, show inline badge with spinner.
 * On tool_result, replace spinner with success (checkmark) or failure (X) icon.
 */

import { render } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import type { ToolExecution } from "@/types/chat";

import { ToolExecutionBadge, formatToolLabel } from "./tool-execution-badge";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const RUNNING_TOOL: ToolExecution = {
	tool: "favorite_job",
	args: { job_id: "abc-123" },
	status: "running",
};

const SUCCESS_TOOL: ToolExecution = {
	tool: "search_jobs",
	args: { query: "frontend" },
	status: "success",
};

const ERROR_TOOL: ToolExecution = {
	tool: "score_posting",
	args: { posting_id: "xyz" },
	status: "error",
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const BADGE_SELECTOR = '[data-slot="tool-execution"]';
const SPINNER_SELECTOR = '[data-slot="tool-spinner"]';
const SUCCESS_ICON_SELECTOR = '[data-slot="tool-success-icon"]';
const ERROR_ICON_SELECTOR = '[data-slot="tool-error-icon"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBadge(
	props: Partial<ComponentProps<typeof ToolExecutionBadge>> = {},
) {
	return render(<ToolExecutionBadge execution={RUNNING_TOOL} {...props} />);
}

// ---------------------------------------------------------------------------
// formatToolLabel
// ---------------------------------------------------------------------------

describe("formatToolLabel", () => {
	it("converts snake_case to title case", () => {
		expect(formatToolLabel("favorite_job")).toBe("Favorite job");
	});

	it("handles single word", () => {
		expect(formatToolLabel("search")).toBe("Search");
	});

	it("handles multiple underscores", () => {
		expect(formatToolLabel("generate_cover_letter")).toBe(
			"Generate cover letter",
		);
	});

	it("trims whitespace", () => {
		expect(formatToolLabel("  favorite_job  ")).toBe("Favorite job");
	});

	it("returns empty string for empty input", () => {
		expect(formatToolLabel("")).toBe("");
	});
});

// ---------------------------------------------------------------------------
// Running state
// ---------------------------------------------------------------------------

describe("ToolExecutionBadge", () => {
	describe("running state", () => {
		it("renders tool label with ellipsis", () => {
			const { container } = renderBadge();

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge?.textContent).toContain("Favorite job");
			expect(badge?.textContent).toContain("...");
		});

		it("shows spinner icon", () => {
			const { container } = renderBadge();

			expect(container.querySelector(SPINNER_SELECTOR)).toBeInTheDocument();
		});

		it("spinner has spin animation", () => {
			const { container } = renderBadge();

			const spinner = container.querySelector(SPINNER_SELECTOR);
			expect(spinner).toHaveClass("motion-safe:animate-spin");
		});

		it("has data-status running", () => {
			const { container } = renderBadge();

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveAttribute("data-status", "running");
		});

		it("does not show success icon", () => {
			const { container } = renderBadge();

			expect(
				container.querySelector(SUCCESS_ICON_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not show error icon", () => {
			const { container } = renderBadge();

			expect(
				container.querySelector(ERROR_ICON_SELECTOR),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Success state
	// -----------------------------------------------------------------------

	describe("success state", () => {
		it("renders tool label without ellipsis", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge?.textContent).toContain("Search jobs");
			expect(badge?.textContent).not.toContain("...");
		});

		it("shows success icon", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			expect(
				container.querySelector(SUCCESS_ICON_SELECTOR),
			).toBeInTheDocument();
		});

		it("has data-status success", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveAttribute("data-status", "success");
		});

		it("does not show spinner", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			expect(container.querySelector(SPINNER_SELECTOR)).not.toBeInTheDocument();
		});

		it("uses success color", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveClass("text-success");
		});

		it("success icon is aria-hidden", () => {
			const { container } = renderBadge({ execution: SUCCESS_TOOL });

			const icon = container.querySelector(SUCCESS_ICON_SELECTOR);
			expect(icon).toHaveAttribute("aria-hidden", "true");
		});
	});

	// -----------------------------------------------------------------------
	// Error state
	// -----------------------------------------------------------------------

	describe("error state", () => {
		it("renders tool label without ellipsis", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge?.textContent).toContain("Score posting");
			expect(badge?.textContent).not.toContain("...");
		});

		it("shows error icon", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			expect(container.querySelector(ERROR_ICON_SELECTOR)).toBeInTheDocument();
		});

		it("has data-status error", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveAttribute("data-status", "error");
		});

		it("does not show spinner", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			expect(container.querySelector(SPINNER_SELECTOR)).not.toBeInTheDocument();
		});

		it("uses destructive color", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveClass("text-destructive");
		});

		it("error icon is aria-hidden", () => {
			const { container } = renderBadge({ execution: ERROR_TOOL });

			const icon = container.querySelector(ERROR_ICON_SELECTOR);
			expect(icon).toHaveAttribute("aria-hidden", "true");
		});
	});

	// -----------------------------------------------------------------------
	// Shared behavior
	// -----------------------------------------------------------------------

	describe("shared behavior", () => {
		it("renders as inline-flex element", () => {
			const { container } = renderBadge();

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveClass("inline-flex");
		});

		it("has badge/chip styling", () => {
			const { container } = renderBadge();

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveClass("rounded-full");
			expect(badge).toHaveClass("text-xs");
		});

		it("icons are aria-hidden", () => {
			const { container } = renderBadge();

			const spinner = container.querySelector(SPINNER_SELECTOR);
			expect(spinner).toHaveAttribute("aria-hidden", "true");
		});

		it("merges custom className", () => {
			const { container } = renderBadge({ className: "mt-1" });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveClass("mt-1");
		});

		it("has accessible label describing the tool status", () => {
			const { container } = renderBadge();

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Favorite job"),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like tool names as plain text", () => {
			const xssTool: ToolExecution = {
				tool: "<img src=x onerror=alert(1)>",
				args: {},
				status: "success",
			};
			const { container } = renderBadge({ execution: xssTool });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge?.textContent).toContain("<img");
			expect(container.querySelector("img")).not.toBeInTheDocument();
		});

		it("renders script tag tool names as plain text", () => {
			const xssTool: ToolExecution = {
				tool: '<script>alert("xss")</script>',
				args: {},
				status: "running",
			};
			const { container } = renderBadge({ execution: xssTool });

			const badge = container.querySelector(BADGE_SELECTOR);
			expect(badge?.textContent).toContain("<script>");
			expect(container.querySelector("script")).not.toBeInTheDocument();
		});
	});
});
