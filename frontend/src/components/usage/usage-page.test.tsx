/**
 * Tests for the UsagePage layout component.
 *
 * REQ-020 §9.2: Usage dashboard page composing balance card,
 * period summary, usage table, and transaction table.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUseBalance: vi.fn<
		() => {
			balance: string | undefined;
			isLoading: boolean;
			error: Error | null;
		}
	>(),
	mockUseQuery: vi.fn(),
}));

vi.mock("@/hooks/use-balance", () => ({
	useBalance: mocks.mockUseBalance,
}));

vi.mock("@tanstack/react-query", () => ({
	useQuery: mocks.mockUseQuery,
}));

vi.mock("./balance-card", () => ({
	BalanceCard: () => <div data-testid="mock-balance-card" />,
}));

vi.mock("./usage-summary", () => ({
	UsageSummary: () => <div data-testid="mock-usage-summary" />,
}));

vi.mock("./usage-table", () => ({
	UsageTable: () => <div data-testid="mock-usage-table" />,
}));

vi.mock("./transaction-table", () => ({
	TransactionTable: () => <div data-testid="mock-transaction-table" />,
}));

import { UsagePage } from "./usage-page";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockUseBalance.mockReturnValue({
		balance: "10.000000",
		isLoading: false,
		error: null,
	});
	mocks.mockUseQuery.mockReturnValue({
		data: undefined,
		isLoading: false,
		error: null,
	});
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsagePage", () => {
	it("renders page container with testid", () => {
		render(<UsagePage />);
		expect(screen.getByTestId("usage-page")).toBeInTheDocument();
	});

	it("renders Usage & Billing heading", () => {
		render(<UsagePage />);
		expect(
			screen.getByRole("heading", { name: /usage & billing/i, level: 1 }),
		).toBeInTheDocument();
	});

	it("renders BalanceCard component", () => {
		render(<UsagePage />);
		expect(screen.getByTestId("mock-balance-card")).toBeInTheDocument();
	});

	it("renders UsageSummary component", () => {
		render(<UsagePage />);
		expect(screen.getByTestId("mock-usage-summary")).toBeInTheDocument();
	});

	it("renders UsageTable component", () => {
		render(<UsagePage />);
		expect(screen.getByTestId("mock-usage-table")).toBeInTheDocument();
	});

	it("renders TransactionTable component", () => {
		render(<UsagePage />);
		expect(screen.getByTestId("mock-transaction-table")).toBeInTheDocument();
	});
});
