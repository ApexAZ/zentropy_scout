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
		it("renders Applied", () => {
			renderBadge({ status: "Applied" });

			expect(screen.getByText("Applied")).toBeInTheDocument();
		});

		it("renders Interviewing", () => {
			renderBadge({ status: "Interviewing" });

			expect(screen.getByText("Interviewing")).toBeInTheDocument();
		});

		it("renders Offer", () => {
			renderBadge({ status: "Offer" });

			expect(screen.getByText("Offer")).toBeInTheDocument();
		});

		it("renders Accepted", () => {
			renderBadge({ status: "Accepted" });

			expect(screen.getByText("Accepted")).toBeInTheDocument();
		});

		it("renders Rejected", () => {
			renderBadge({ status: "Rejected" });

			expect(screen.getByText("Rejected")).toBeInTheDocument();
		});

		it("renders Withdrawn", () => {
			renderBadge({ status: "Withdrawn" });

			expect(screen.getByText("Withdrawn")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Document statuses
	// ---------------------------------------------------------------------------

	describe("document statuses", () => {
		it("renders Draft", () => {
			renderBadge({ status: "Draft" });

			expect(screen.getByText("Draft")).toBeInTheDocument();
		});

		it("renders Approved", () => {
			renderBadge({ status: "Approved" });

			expect(screen.getByText("Approved")).toBeInTheDocument();
		});

		it("renders Archived", () => {
			renderBadge({ status: "Archived" });

			expect(screen.getByText("Archived")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Job posting statuses
	// ---------------------------------------------------------------------------

	// "Applied" shared with ApplicationStatus — tested in application statuses group.
	describe("job posting statuses", () => {
		it("renders Discovered", () => {
			renderBadge({ status: "Discovered" });

			expect(screen.getByText("Discovered")).toBeInTheDocument();
		});

		it("renders Dismissed", () => {
			renderBadge({ status: "Dismissed" });

			expect(screen.getByText("Dismissed")).toBeInTheDocument();
		});

		it("renders Expired", () => {
			renderBadge({ status: "Expired" });

			expect(screen.getByText("Expired")).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Special statuses
	// ---------------------------------------------------------------------------

	describe("special statuses", () => {
		it("renders Active", () => {
			renderBadge({ status: "Active" });

			expect(screen.getByText("Active")).toBeInTheDocument();
		});

		it("renders Filtered", () => {
			renderBadge({ status: "Filtered" });

			expect(screen.getByText("Filtered")).toBeInTheDocument();
		});

		it("renders None", () => {
			renderBadge({ status: "None" });

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
