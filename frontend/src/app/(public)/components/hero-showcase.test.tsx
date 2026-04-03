/**
 * Tests for HeroShowcase component.
 *
 * REQ-024 §4.2: Rotating feature showcase on hero right side.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HeroShowcase } from "./hero-showcase";

afterEach(() => {
	cleanup();
});

describe("HeroShowcase", () => {
	it("renders showcase container", () => {
		render(<HeroShowcase />);
		expect(screen.getByTestId("hero-showcase")).toBeInTheDocument();
	});

	it("renders the first slide visible on mount", () => {
		render(<HeroShowcase />);
		expect(screen.getByText("Build Your Persona")).toBeInTheDocument();
	});
});
