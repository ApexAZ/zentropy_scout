/**
 * Tests for the StatusBadge component.
 *
 * REQ-012 §11.1: Application status badge colors.
 * REQ-012 §8.5: "Filtered" badge for non-negotiable failures.
 * REQ-012 §9.2: Draft/Approved document status display.
 */

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./status-badge";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROOT_SELECTOR = '[data-slot="status-badge"]';
const BG_SUCCESS = "bg-success";
const BG_MUTED = "bg-muted";
const BG_DESTRUCTIVE = "bg-destructive";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBadge(props: Partial<ComponentProps<typeof StatusBadge>> = {}) {
	return render(<StatusBadge status="Applied" {...props} />);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("StatusBadge", () => {
	describe("rendering", () => {
		it("has data-slot attribute", () => {
			const { container } = renderBadge();

			expect(container.querySelector(ROOT_SELECTOR)).toBeInTheDocument();
		});

		it("applies custom className", () => {
			const { container } = renderBadge({ className: "ml-2" });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveClass("ml-2");
		});

		it("sets data-status attribute matching status prop", () => {
			const { container } = renderBadge({ status: "Interviewing" });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"data-status",
				"Interviewing",
			);
		});
	});

	// ---------------------------------------------------------------------------
	// Application statuses (REQ-012 §11.1)
	// ---------------------------------------------------------------------------

	describe("application statuses", () => {
		it("renders Applied with primary color", () => {
			const { container } = renderBadge({ status: "Applied" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-primary");
			expect(screen.getByText("Applied")).toBeInTheDocument();
		});

		it("renders Interviewing with warning color", () => {
			const { container } = renderBadge({ status: "Interviewing" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-warning");
			expect(screen.getByText("Interviewing")).toBeInTheDocument();
		});

		it("renders Offer with success color", () => {
			const { container } = renderBadge({ status: "Offer" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_SUCCESS);
			expect(screen.getByText("Offer")).toBeInTheDocument();
		});

		it("renders Accepted with success color and semibold", () => {
			const { container } = renderBadge({ status: "Accepted" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_SUCCESS);
			expect(root).toHaveClass("font-semibold");
			expect(screen.getByText("Accepted")).toBeInTheDocument();
		});

		it("renders Rejected with destructive color", () => {
			const { container } = renderBadge({ status: "Rejected" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_DESTRUCTIVE);
			expect(screen.getByText("Rejected")).toBeInTheDocument();
		});

		it("renders Withdrawn with muted color", () => {
			const { container } = renderBadge({ status: "Withdrawn" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_MUTED);
			expect(screen.getByText("Withdrawn")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Document statuses
	// ---------------------------------------------------------------------------

	describe("document statuses", () => {
		it("renders Draft with warning color", () => {
			const { container } = renderBadge({ status: "Draft" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-warning");
			expect(screen.getByText("Draft")).toBeInTheDocument();
		});

		it("renders Approved with success color", () => {
			const { container } = renderBadge({ status: "Approved" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_SUCCESS);
			expect(screen.getByText("Approved")).toBeInTheDocument();
		});

		it("renders Archived with muted color", () => {
			const { container } = renderBadge({ status: "Archived" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_MUTED);
			expect(screen.getByText("Archived")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Job posting statuses
	// ---------------------------------------------------------------------------

	// "Applied" shared with ApplicationStatus — tested in application statuses group.
	describe("job posting statuses", () => {
		it("renders Discovered with info color", () => {
			const { container } = renderBadge({ status: "Discovered" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass("bg-info");
			expect(screen.getByText("Discovered")).toBeInTheDocument();
		});

		it("renders Dismissed with muted color", () => {
			const { container } = renderBadge({ status: "Dismissed" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_MUTED);
			expect(screen.getByText("Dismissed")).toBeInTheDocument();
		});

		it("renders Expired with destructive color", () => {
			const { container } = renderBadge({ status: "Expired" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_DESTRUCTIVE);
			expect(screen.getByText("Expired")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Special statuses
	// ---------------------------------------------------------------------------

	describe("special statuses", () => {
		it("renders Active with success color", () => {
			const { container } = renderBadge({ status: "Active" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_SUCCESS);
			expect(screen.getByText("Active")).toBeInTheDocument();
		});

		it("renders Filtered with destructive color", () => {
			const { container } = renderBadge({ status: "Filtered" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_DESTRUCTIVE);
			expect(screen.getByText("Filtered")).toBeInTheDocument();
		});

		it("renders None with muted color", () => {
			const { container } = renderBadge({ status: "None" });
			const root = container.querySelector(ROOT_SELECTOR);

			expect(root).toHaveClass(BG_MUTED);
			expect(screen.getByText("None")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Accessibility
	// ---------------------------------------------------------------------------

	describe("accessibility", () => {
		it("has descriptive aria-label including status", () => {
			const { container } = renderBadge({ status: "Interviewing" });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"aria-label",
				"Status: Interviewing",
			);
		});
	});
});
