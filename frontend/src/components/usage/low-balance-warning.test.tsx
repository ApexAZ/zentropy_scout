/**
 * Tests for the LowBalanceWarning component.
 *
 * REQ-029 §9.5: Low-balance warning banner with threshold-based
 * color coding and CTA to scroll to funding packs.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LowBalanceWarning } from "./low-balance-warning";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

/** Below $0.10 — red (destructive). */
const BALANCE_CRITICAL = 0.05;
/** Between $0.10 and $1.00 — amber (primary). */
const BALANCE_LOW = 0.5;
/** At or above $1.00 — no warning. */
const BALANCE_HEALTHY = 5.0;
/** Exactly $0.10 — amber threshold boundary. */
const BALANCE_AT_LOW = 0.1;
/** Exactly $1.00 — no warning boundary. */
const BALANCE_AT_HIGH = 1.0;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LowBalanceWarning", () => {
	it("renders red warning when balance is below $0.10", () => {
		render(<LowBalanceWarning balance={BALANCE_CRITICAL} />);
		const warning = screen.getByTestId("low-balance-warning");
		expect(warning).toBeInTheDocument();
		expect(warning.className).toContain("destructive");
		expect(screen.getByText(/balance is nearly empty/i)).toBeInTheDocument();
	});

	it("renders amber warning when balance is below $1.00", () => {
		render(<LowBalanceWarning balance={BALANCE_LOW} />);
		const warning = screen.getByTestId("low-balance-warning");
		expect(warning).toBeInTheDocument();
		expect(warning.className).not.toContain("destructive");
		expect(screen.getByText(/balance is running low/i)).toBeInTheDocument();
	});

	it("renders nothing when balance is at or above $1.00", () => {
		render(<LowBalanceWarning balance={BALANCE_HEALTHY} />);
		expect(screen.queryByTestId("low-balance-warning")).not.toBeInTheDocument();
	});

	it("renders amber warning at exactly $0.10 boundary", () => {
		render(<LowBalanceWarning balance={BALANCE_AT_LOW} />);
		const warning = screen.getByTestId("low-balance-warning");
		expect(warning).toBeInTheDocument();
		expect(warning.className).not.toContain("destructive");
	});

	it("renders nothing at exactly $1.00 boundary", () => {
		render(<LowBalanceWarning balance={BALANCE_AT_HIGH} />);
		expect(screen.queryByTestId("low-balance-warning")).not.toBeInTheDocument();
	});

	it("includes a CTA link to funding packs section", () => {
		render(<LowBalanceWarning balance={BALANCE_CRITICAL} />);
		const cta = screen.getByRole("link", { name: /add funds/i });
		expect(cta).toBeInTheDocument();
		expect(cta).toHaveAttribute("href", "#funding-packs");
	});

	it("renders red warning when balance is zero", () => {
		render(<LowBalanceWarning balance={0} />);
		const warning = screen.getByTestId("low-balance-warning");
		expect(warning).toBeInTheDocument();
		expect(warning.className).toContain("destructive");
	});
});
