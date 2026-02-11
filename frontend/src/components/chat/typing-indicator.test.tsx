/**
 * Tests for the typing indicator component.
 *
 * REQ-012 §5.4: While tokens are streaming, show a
 * "Scout is typing..." indicator above the input.
 * Disappear on chat_done.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TypingIndicator } from "./typing-indicator";

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const INDICATOR_SELECTOR = '[data-slot="typing-indicator"]';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TypingIndicator", () => {
	it("renders typing text", () => {
		render(<TypingIndicator />);

		expect(screen.getByText(/Scout is typing/)).toBeInTheDocument();
	});

	it("has data-slot attribute", () => {
		const { container } = render(<TypingIndicator />);

		const indicator = container.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toBeInTheDocument();
	});

	it("has role=status for accessibility", () => {
		render(<TypingIndicator />);

		expect(screen.getByRole("status")).toBeInTheDocument();
	});

	it("has aria-live polite for screen readers", () => {
		render(<TypingIndicator />);

		const status = screen.getByRole("status");
		expect(status).toHaveAttribute("aria-live", "polite");
	});

	it("uses muted small text styling", () => {
		const { container } = render(<TypingIndicator />);

		const indicator = container.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveClass("text-muted-foreground");
		expect(indicator).toHaveClass("text-xs");
	});

	it("has pulse animation", () => {
		const { container } = render(<TypingIndicator />);

		const indicator = container.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveClass("motion-safe:animate-pulse");
	});

	it("merges custom className", () => {
		const { container } = render(<TypingIndicator className="px-3" />);

		const indicator = container.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveClass("px-3");
	});
});
