/**
 * Tests for the BalanceCard component.
 *
 * REQ-020 §9.2: Current balance display with color coding
 * and disabled "Add Funds" button (REQ-021).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BalanceCard } from "./balance-card";

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
		render(<BalanceCard balance="5.000000" isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-green",
		);
	});

	it("shows amber text for balance between $0.10 and $1.00", () => {
		render(<BalanceCard balance="0.500000" isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-amber",
		);
	});

	it("shows red text for balance < $0.10", () => {
		render(<BalanceCard balance="0.050000" isLoading={false} />);
		expect(screen.getByTestId("balance-amount").className).toContain(
			"text-red",
		);
	});

	it("shows $0.00 when balance is undefined", () => {
		render(<BalanceCard balance={undefined} isLoading={false} />);
		expect(screen.getByTestId("balance-amount")).toHaveTextContent("$0.00");
	});

	it("shows loading skeleton when loading", () => {
		render(<BalanceCard balance={undefined} isLoading={true} />);
		expect(screen.getByTestId("balance-skeleton")).toBeInTheDocument();
		expect(screen.queryByTestId("balance-amount")).not.toBeInTheDocument();
	});

	it("renders disabled Add Funds button", () => {
		render(<BalanceCard balance="10.000000" isLoading={false} />);
		const button = screen.getByRole("button", { name: /add funds/i });
		expect(button).toBeDisabled();
	});
});
