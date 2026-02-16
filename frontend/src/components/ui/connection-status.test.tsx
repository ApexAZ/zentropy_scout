/**
 * Tests for the ConnectionStatus indicator component.
 *
 * REQ-012 §5.5: Reconnection UX — visual indicator in chat header.
 * REQ-012 §13.8: ARIA labels on icons, prefers-reduced-motion respected.
 */

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectionStatus } from "./connection-status";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CONNECTED = "connected" as const;
const RECONNECTING = "reconnecting" as const;
const DISCONNECTED = "disconnected" as const;

const ARIA_PREFIX = "Connection status: ";
const DOT_SELECTOR = '[data-slot="connection-status-dot"]';
const ROOT_SELECTOR = '[data-slot="connection-status"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderStatus(
	props: Partial<ComponentProps<typeof ConnectionStatus>> = {},
) {
	return render(<ConnectionStatus status={CONNECTED} {...props} />);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ConnectionStatus", () => {
	describe("rendering", () => {
		it("has data-slot attribute", () => {
			const { container } = renderStatus();

			expect(container.querySelector(ROOT_SELECTOR)).toBeInTheDocument();
		});

		it("has role=status for accessibility", () => {
			renderStatus();

			expect(screen.getByRole("status")).toBeInTheDocument();
		});

		it("uses <output> element for implicit aria-live polite", () => {
			const { container } = renderStatus();

			// <output> provides implicit role="status" and aria-live="polite"
			const output = container.querySelector("output");
			expect(output).toBeInTheDocument();
		});

		it("sets data-status attribute matching status prop", () => {
			const { container } = renderStatus({ status: RECONNECTING });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveAttribute(
				"data-status",
				RECONNECTING,
			);
		});

		it("applies custom className", () => {
			const { container } = renderStatus({ className: "ml-2" });

			expect(container.querySelector(ROOT_SELECTOR)).toHaveClass("ml-2");
		});

		it("renders a dot element", () => {
			const { container } = renderStatus();

			expect(container.querySelector(DOT_SELECTOR)).toBeInTheDocument();
		});
	});

	// ---------------------------------------------------------------------------
	// Connected state
	// ---------------------------------------------------------------------------

	describe("connected state", () => {
		it("renders green dot", () => {
			const { container } = renderStatus({ status: CONNECTED });

			expect(container.querySelector(DOT_SELECTOR)).toHaveClass("bg-success");
		});

		it("shows 'Connected' label", () => {
			renderStatus({ status: CONNECTED });

			expect(screen.getByText("Connected")).toBeInTheDocument();
		});

		it("includes status in aria-label", () => {
			renderStatus({ status: CONNECTED });

			expect(screen.getByRole("status")).toHaveAttribute(
				"aria-label",
				`${ARIA_PREFIX}Connected`,
			);
		});
	});

	// ---------------------------------------------------------------------------
	// Reconnecting state
	// ---------------------------------------------------------------------------

	describe("reconnecting state", () => {
		it("renders amber dot", () => {
			const { container } = renderStatus({ status: RECONNECTING });

			expect(container.querySelector(DOT_SELECTOR)).toHaveClass("bg-warning");
		});

		it("shows 'Reconnecting...' label", () => {
			renderStatus({ status: RECONNECTING });

			expect(screen.getByText("Reconnecting...")).toBeInTheDocument();
		});

		it("applies pulse animation respecting reduced motion", () => {
			const { container } = renderStatus({ status: RECONNECTING });

			expect(container.querySelector(DOT_SELECTOR)).toHaveClass(
				"motion-safe:animate-pulse",
			);
		});

		it("includes status in aria-label", () => {
			renderStatus({ status: RECONNECTING });

			expect(screen.getByRole("status")).toHaveAttribute(
				"aria-label",
				`${ARIA_PREFIX}Reconnecting`,
			);
		});
	});

	// ---------------------------------------------------------------------------
	// Disconnected state
	// ---------------------------------------------------------------------------

	describe("disconnected state", () => {
		it("renders red dot", () => {
			const { container } = renderStatus({ status: DISCONNECTED });

			expect(container.querySelector(DOT_SELECTOR)).toHaveClass(
				"bg-destructive",
			);
		});

		it("shows 'Disconnected' label", () => {
			renderStatus({ status: DISCONNECTED });

			expect(screen.getByText("Disconnected")).toBeInTheDocument();
		});

		it("includes status in aria-label", () => {
			renderStatus({ status: DISCONNECTED });

			expect(screen.getByRole("status")).toHaveAttribute(
				"aria-label",
				`${ARIA_PREFIX}Disconnected`,
			);
		});
	});

	// ---------------------------------------------------------------------------
	// Animation safety
	// ---------------------------------------------------------------------------

	describe("animation", () => {
		it("does not apply pulse animation for connected state", () => {
			const { container } = renderStatus({ status: CONNECTED });

			expect(container.querySelector(DOT_SELECTOR)).not.toHaveClass(
				"motion-safe:animate-pulse",
			);
		});

		it("does not apply pulse animation for disconnected state", () => {
			const { container } = renderStatus({ status: DISCONNECTED });

			expect(container.querySelector(DOT_SELECTOR)).not.toHaveClass(
				"motion-safe:animate-pulse",
			);
		});
	});
});
