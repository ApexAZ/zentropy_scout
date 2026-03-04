/**
 * Tests for LandingFooter component.
 *
 * REQ-024 §4.5: Footer with copyright, ToS, Privacy, Sign In links.
 * REQ-024 §6.1: Unit tests for LandingFooter.
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

import { LandingFooter } from "./landing-footer";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LandingFooter", () => {
	it("renders copyright text", () => {
		render(<LandingFooter />);
		expect(screen.getByText(/© 2026 Zentropy Scout/)).toBeInTheDocument();
	});

	it("renders Terms of Service link", () => {
		render(<LandingFooter />);
		const tos = screen.getByTestId("footer-tos");
		expect(tos).toHaveTextContent("Terms of Service");
	});

	it("renders Privacy Policy link", () => {
		render(<LandingFooter />);
		const privacy = screen.getByTestId("footer-privacy");
		expect(privacy).toHaveTextContent("Privacy Policy");
	});

	it("renders Sign In link to /login", () => {
		render(<LandingFooter />);
		const signIn = screen.getByRole("link", { name: /sign in/i });
		expect(signIn).toHaveAttribute("href", "/login");
	});

	it("has landing-footer test id", () => {
		render(<LandingFooter />);
		expect(screen.getByTestId("landing-footer")).toBeInTheDocument();
	});
});
