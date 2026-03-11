/**
 * Tests for the BalanceCard component.
 *
 * REQ-020 §9.2: Current balance display with color coding.
 * REQ-029 §9.1: "Add Funds" button links to funding packs section.
 * REQ-023 §5.1, §7.5: Usage bar with color thresholds and width scaling.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BalanceCard } from "./balance-card";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

/** Balance > $1.00 — green threshold. */
const BALANCE_HIGH = "5.000000";
/** Balance $0.10–$1.00 — amber threshold. */
const BALANCE_MID = "0.500000";
/** Balance < $0.10 — red threshold. */
const BALANCE_LOW = "0.050000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get the inner fill element of the usage bar. */
function getBarFill(): HTMLElement {
	const bar = screen.getByTestId("usage-bar");
	return bar.firstElementChild as HTMLElement;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BalanceCard", () => {
	it("renders Current Balance heading", () => {
		render(<BalanceCard balance="10.000000" isLoading={false} />);
		expect(screen.getByText("Current Balance")).toBeInTheDocument();
	});

	it("formats balance to 2 decimal places", () => {
		render(<BalanceCard balance="10.500000" isLoading={false} />);
		expect(screen.getByTestId("balance-amount")).toHaveTextContent("$10.50");
	});

	it("shows green text for balance > $1.00", () => {
		render(<BalanceCard balance={BALANCE_HIGH} isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-success",
		);
	});

	it("shows amber text for balance between $0.10 and $1.00", () => {
		render(<BalanceCard balance={BALANCE_MID} isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-primary",
		);
	});

	it("shows red text for balance < $0.10", () => {
		render(<BalanceCard balance={BALANCE_LOW} isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-destructive",
		);
	});

	it("shows $0.00 when balance is undefined", () => {
		render(<BalanceCard balance={undefined} isLoading={false} />);
		expect(screen.getByTestId("balance-amount")).toHaveTextContent("$0.00");
	});

	it("shows $0.00 when balance is non-numeric", () => {
		render(<BalanceCard balance="not-a-number" isLoading={false} />);
		expect(screen.getByTestId("balance-amount")).toHaveTextContent("$0.00");
	});

	it("shows loading skeleton when loading", () => {
		render(<BalanceCard balance={undefined} isLoading={true} />);
		expect(screen.getByTestId("balance-skeleton")).toBeInTheDocument();
		expect(screen.queryByTestId("balance-amount")).not.toBeInTheDocument();
	});

	it("renders Add Funds link to funding packs section", () => {
		render(<BalanceCard balance="10.000000" isLoading={false} />);
		const link = screen.getByRole("link", { name: /add funds/i });
		expect(link).toHaveAttribute("href", "#funding-packs");
	});

	// -----------------------------------------------------------------------
	// Usage bar (REQ-023 §5.1, §7.5)
	// -----------------------------------------------------------------------

	it("renders usage bar", () => {
		render(<BalanceCard balance={BALANCE_HIGH} isLoading={false} />);
		expect(screen.getByTestId("usage-bar")).toBeInTheDocument();
	});

	it("usage bar is green when balance > $1.00", () => {
		render(<BalanceCard balance={BALANCE_HIGH} isLoading={false} />);
		expect(getBarFill().className).toContain("bg-success");
	});

	it("usage bar is amber when balance $0.10–$1.00", () => {
		render(<BalanceCard balance={BALANCE_MID} isLoading={false} />);
		expect(getBarFill().className).toContain("bg-primary");
	});

	it("usage bar is red when balance < $0.10", () => {
		render(<BalanceCard balance={BALANCE_LOW} isLoading={false} />);
		expect(getBarFill().className).toContain("bg-destructive");
	});

	it("usage bar width scales with balance capped at 100%", () => {
		const { unmount: u1 } = render(
			<BalanceCard balance="7.500000" isLoading={false} />,
		);
		expect(getBarFill().style.width).toBe("50%");
		u1();

		const { unmount: u2 } = render(
			<BalanceCard balance="15.000000" isLoading={false} />,
		);
		expect(getBarFill().style.width).toBe("100%");
		u2();

		render(<BalanceCard balance="20.000000" isLoading={false} />);
		expect(getBarFill().style.width).toBe("100%");
	});

	it("usage bar has accessible progress element", () => {
		render(<BalanceCard balance="7.420000" isLoading={false} />);
		const progress = screen.getByRole("progressbar", {
			name: "Balance: $7.42",
		});
		expect(progress).toBeInTheDocument();
	});

	it("usage bar hidden during loading", () => {
		render(<BalanceCard balance={undefined} isLoading={true} />);
		expect(screen.queryByTestId("usage-bar")).not.toBeInTheDocument();
	});
});
