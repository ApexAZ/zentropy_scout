/**
 * Tests for HeroSection component.
 *
 * REQ-024 §4.2: Hero headline, subtitle, CTA button, sign-in link, graphic.
 * REQ-024 §6.1: Unit tests for HeroSection.
 */

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("./hero-showcase", () => ({
	HeroShowcase: () => <div data-testid="hero-showcase" />,
}));

vi.mock("next/link", () => ({
	default: function MockLink({
		children,
		href,
		...props
	}: {
		children: ReactNode;
		href: string;
		[key: string]: unknown;
	}) {
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	},
}));

import { HeroSection } from "./hero-section";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HeroSection", () => {
	it("renders Zentropy logo", () => {
		render(<HeroSection />);
		expect(screen.getByTestId("hero-logo")).toBeInTheDocument();
	});

	it("renders feature showcase", () => {
		render(<HeroSection />);
		expect(screen.getByTestId("hero-showcase")).toBeInTheDocument();
	});

	it("CTA button links to /register", () => {
		render(<HeroSection />);
		const cta = screen.getByTestId("hero-cta");
		expect(cta).toHaveAttribute("href", "/register");
	});

	it("sign-in link links to /login", () => {
		render(<HeroSection />);
		const signIn = screen.getByTestId("hero-sign-in");
		expect(signIn).toHaveAttribute("href", "/login");
	});
});
