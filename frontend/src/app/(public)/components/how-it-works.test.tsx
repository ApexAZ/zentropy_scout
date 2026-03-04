/**
 * Tests for HowItWorks component.
 *
 * REQ-024 §4.4: 3-step visual walkthrough with icons.
 * REQ-024 §6.1: Unit tests for HowItWorks.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HowItWorks } from "./how-it-works";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HowItWorks", () => {
	it("renders 3 steps", () => {
		render(<HowItWorks />);
		for (let i = 0; i < 3; i++) {
			expect(screen.getByTestId(`how-it-works-step-${i}`)).toBeInTheDocument();
		}
	});

	it("each step has a title", () => {
		render(<HowItWorks />);
		expect(screen.getByText("Build your persona")).toBeInTheDocument();
		expect(screen.getByText("Scout finds matches")).toBeInTheDocument();
		expect(screen.getByText("Generate & apply")).toBeInTheDocument();
	});

	it("has how-it-works test id", () => {
		render(<HowItWorks />);
		expect(screen.getByTestId("how-it-works")).toBeInTheDocument();
	});

	it("has How it works aria-label", () => {
		render(<HowItWorks />);
		expect(
			screen.getByRole("region", { name: "How it works" }),
		).toBeInTheDocument();
	});
});
