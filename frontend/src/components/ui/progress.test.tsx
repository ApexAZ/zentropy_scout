/**
 * Tests for the Progress bar UI primitive.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Progress } from "./progress";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const INDICATOR_SELECTOR = '[data-slot="progress-indicator"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderProgress(props: { value?: number; className?: string } = {}) {
	return render(<Progress {...props} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Progress", () => {
	it("renders with progressbar role", () => {
		renderProgress({ value: 50 });
		expect(screen.getByRole("progressbar")).toBeInTheDocument();
	});

	it("sets aria-valuenow to the value prop", () => {
		renderProgress({ value: 42 });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveAttribute("aria-valuenow", "42");
	});

	it("sets aria-valuemin to 0 and aria-valuemax to 100", () => {
		renderProgress({ value: 50 });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveAttribute("aria-valuemin", "0");
		expect(bar).toHaveAttribute("aria-valuemax", "100");
	});

	it("renders the indicator with correct width percentage", () => {
		renderProgress({ value: 75 });
		const indicator = screen
			.getByRole("progressbar")
			.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveStyle({ transform: "translateX(-25%)" });
	});

	it("handles 0% value", () => {
		renderProgress({ value: 0 });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveAttribute("aria-valuenow", "0");
		const indicator = bar.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveStyle({ transform: "translateX(-100%)" });
	});

	it("handles 100% value", () => {
		renderProgress({ value: 100 });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveAttribute("aria-valuenow", "100");
		const indicator = bar.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveStyle({ transform: "translateX(-0%)" });
	});

	it("applies custom className to the root", () => {
		renderProgress({ value: 50, className: "custom-class" });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveClass("custom-class");
	});

	it("has data-slot='progress' on the root", () => {
		renderProgress({ value: 50 });
		const bar = screen.getByRole("progressbar");
		expect(bar).toHaveAttribute("data-slot", "progress");
	});

	it("defaults to 0 when value is undefined", () => {
		renderProgress();
		const bar = screen.getByRole("progressbar");
		const indicator = bar.querySelector(INDICATOR_SELECTOR);
		expect(indicator).toHaveStyle({ transform: "translateX(-100%)" });
	});
});
