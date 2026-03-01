/**
 * Tests for the TransactionTable component.
 *
 * REQ-020 §9.2: Transaction history — paginated table of
 * credit transactions with color-coded amounts.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CreditTransactionResponse } from "@/types/usage";

import { TransactionTable } from "./transaction-table";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_TRANSACTIONS: CreditTransactionResponse[] = [
	{
		id: "t-1",
		amount_usd: "5.000000",
		transaction_type: "purchase",
		description: "Credit purchase",
		created_at: "2026-03-01T09:00:00Z",
	},
	{
		id: "t-2",
		amount_usd: "-0.001300",
		transaction_type: "usage_debit",
		description: "extraction — claude-3-5-haiku-20241022",
		created_at: "2026-03-01T10:00:00Z",
	},
	{
		id: "t-3",
		amount_usd: "1.000000",
		transaction_type: "admin_grant",
		description: null,
		created_at: "2026-03-01T08:00:00Z",
	},
];

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TransactionTable", () => {
	const defaultProps = {
		transactions: MOCK_TRANSACTIONS,
		isLoading: false,
		page: 1,
		totalPages: 1,
		onPageChange: vi.fn(),
	};

	it("renders Transaction History heading", () => {
		render(<TransactionTable {...defaultProps} />);
		expect(screen.getByText("Transaction History")).toBeInTheDocument();
	});

	it("renders transaction rows", () => {
		render(<TransactionTable {...defaultProps} />);
		expect(screen.getByText("purchase")).toBeInTheDocument();
		expect(screen.getByText("usage_debit")).toBeInTheDocument();
		expect(screen.getByText("admin_grant")).toBeInTheDocument();
	});

	it("shows green text for positive amounts", () => {
		render(
			<TransactionTable
				{...defaultProps}
				transactions={[MOCK_TRANSACTIONS[0]]}
			/>,
		);
		const amount = screen.getByTestId("tx-amount-t-1");
		expect(amount.className).toContain("text-green");
	});

	it("shows red text for negative amounts", () => {
		render(
			<TransactionTable
				{...defaultProps}
				transactions={[MOCK_TRANSACTIONS[1]]}
			/>,
		);
		const amount = screen.getByTestId("tx-amount-t-2");
		expect(amount.className).toContain("text-red");
	});

	it("shows empty state when no transactions", () => {
		render(<TransactionTable {...defaultProps} transactions={[]} />);
		expect(screen.getByText(/no transactions/i)).toBeInTheDocument();
	});

	it("shows loading state", () => {
		render(
			<TransactionTable {...defaultProps} transactions={[]} isLoading={true} />,
		);
		expect(screen.getByTestId("transaction-table-loading")).toBeInTheDocument();
	});

	it("shows em-dash for null description", () => {
		render(
			<TransactionTable
				{...defaultProps}
				transactions={[MOCK_TRANSACTIONS[2]]}
			/>,
		);
		expect(screen.getByText("—")).toBeInTheDocument();
	});

	it("calls onPageChange when Next is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<TransactionTable
				{...defaultProps}
				page={1}
				totalPages={3}
				onPageChange={onPageChange}
			/>,
		);
		screen.getByRole("button", { name: /next/i }).click();
		expect(onPageChange).toHaveBeenCalledWith(2);
	});
});
