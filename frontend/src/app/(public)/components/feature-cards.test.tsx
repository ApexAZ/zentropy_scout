/**
 * Tests for FeatureCards component.
 *
 * REQ-024 §4.3: 4 feature highlight cards with icons, titles, descriptions.
 * REQ-024 §6.1: Unit tests for FeatureCards.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FeatureCards } from "./feature-cards";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FeatureCards", () => {
	it("renders 4 feature cards", () => {
		render(<FeatureCards />);
		for (let i = 0; i < 4; i++) {
			expect(screen.getByTestId(`feature-card-${i}`)).toBeInTheDocument();
		}
	});

	it("each card has a title", () => {
		render(<FeatureCards />);
		expect(screen.getByText("Build Your Persona")).toBeInTheDocument();
		expect(screen.getByText("Smart Job Matching")).toBeInTheDocument();
		expect(screen.getByText("Tailored Documents")).toBeInTheDocument();
		expect(screen.getByText("Track Applications")).toBeInTheDocument();
	});

	it("has feature-cards test id", () => {
		render(<FeatureCards />);
		expect(screen.getByTestId("feature-cards")).toBeInTheDocument();
	});

	it("has Features aria-label", () => {
		render(<FeatureCards />);
		expect(
			screen.getByRole("region", { name: "Features" }),
		).toBeInTheDocument();
	});
});
