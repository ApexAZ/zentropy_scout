/**
 * Tests for the landing page composition.
 *
 * REQ-024 §4.1–§4.5: Verifies all 5 landing sections render.
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

import LandingPage from "./page";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LandingPage", () => {
	it("renders landing-page wrapper", () => {
		render(<LandingPage />);
		expect(screen.getByTestId("landing-page")).toBeInTheDocument();
	});

	it("renders all 5 landing sections", () => {
		render(<LandingPage />);
		expect(screen.getByTestId("landing-nav")).toBeInTheDocument();
		expect(screen.getByTestId("hero-section")).toBeInTheDocument();
		expect(screen.getByTestId("feature-cards")).toBeInTheDocument();
		expect(screen.getByTestId("how-it-works")).toBeInTheDocument();
		expect(screen.getByTestId("landing-footer")).toBeInTheDocument();
	});
});
