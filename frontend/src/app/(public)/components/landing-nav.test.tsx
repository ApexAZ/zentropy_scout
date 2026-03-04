/**
 * Tests for LandingNav component.
 *
 * REQ-024 §4.1: Navigation bar with logo, sign-in link, and CTA button.
 * REQ-024 §6.1: Unit tests for LandingNav.
 */

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

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

vi.mock("next/image", () => ({
	default: function MockImage(props: Record<string, unknown>) {
		// eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text -- test mock
		return <img {...props} />;
	},
}));

import { LandingNav } from "./landing-nav";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LandingNav", () => {
	it("renders logo with alt text", () => {
		render(<LandingNav />);
		const logo = screen.getByTestId("landing-logo");
		expect(logo).toHaveAttribute("alt", "Zentropy Scout");
	});

	it("renders Get Started CTA linking to /register", () => {
		render(<LandingNav />);
		const cta = screen.getByRole("link", { name: /get started/i });
		expect(cta).toHaveAttribute("href", "/register");
	});

	it("renders Sign In link to /login", () => {
		render(<LandingNav />);
		const signIn = screen.getByRole("link", { name: /sign in/i });
		expect(signIn).toHaveAttribute("href", "/login");
	});

	it("has landing-nav test id", () => {
		render(<LandingNav />);
		expect(screen.getByTestId("landing-nav")).toBeInTheDocument();
	});
});
