/**
 * Tests for the streaming cursor component.
 *
 * REQ-012 §5.4: Show a blinking cursor at the end of the message
 * bubble during streaming. Removed on chat_done.
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StreamingCursor } from "./streaming-cursor";

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const CURSOR_SELECTOR = '[data-slot="streaming-cursor"]';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StreamingCursor", () => {
	it("renders a visible cursor character", () => {
		const { container } = render(<StreamingCursor />);

		const cursor = container.querySelector(CURSOR_SELECTOR);
		expect(cursor).toBeInTheDocument();
		expect(cursor?.textContent).toBeTruthy();
	});

	it("is aria-hidden since it is decorative", () => {
		const { container } = render(<StreamingCursor />);

		const cursor = container.querySelector(CURSOR_SELECTOR);
		expect(cursor).toHaveAttribute("aria-hidden", "true");
	});

	it("has blink animation class", () => {
		const { container } = render(<StreamingCursor />);

		const cursor = container.querySelector(CURSOR_SELECTOR);
		expect(cursor).toHaveClass("motion-safe:animate-blink-caret");
	});

	it("renders as an inline element", () => {
		const { container } = render(<StreamingCursor />);

		const cursor = container.querySelector(CURSOR_SELECTOR);
		expect(cursor?.tagName.toLowerCase()).toBe("span");
	});

	it("merges custom className", () => {
		const { container } = render(<StreamingCursor className="ml-0.5" />);

		const cursor = container.querySelector(CURSOR_SELECTOR);
		expect(cursor).toHaveClass("ml-0.5");
	});
});
