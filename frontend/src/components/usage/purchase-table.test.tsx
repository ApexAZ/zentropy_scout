/**
 * Tests for the PurchaseTable component.
 *
 * REQ-029 §8.3: Purchase history — paginated table of credit
 * purchases, grants, and refunds with signed amounts.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PurchaseItem } from "@/types/usage";

import { PurchaseTable } from "./purchase-table";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_PURCHASES: PurchaseItem[] = [
	{
		id: "p-1",
		amount_usd: "10.000000",
		amount_display: "$10.00",
		transaction_type: "purchase",
		description: "Starter pack",
		created_at: "2026-03-10T15:30:00Z",
	},
	{
		id: "p-2",
		amount_usd: "0.100000",
		amount_display: "$0.10",
		transaction_type: "signup_grant",
		description: "Welcome bonus — free starter balance",
		created_at: "2026-03-08T10:00:00Z",
	},
	{
		id: "p-3",
		amount_usd: "-5.000000",
		amount_display: "-$5.00",
		transaction_type: "refund",
		description: "Refund for duplicate charge",
		created_at: "2026-03-09T12:00:00Z",
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

describe("PurchaseTable", () => {
	const defaultProps = {
		purchases: MOCK_PURCHASES,
		isLoading: false,
		page: 1,
		totalPages: 1,
		onPageChange: vi.fn(),
	};

	it("renders Purchase History heading", () => {
		render(<PurchaseTable {...defaultProps} />);
		expect(screen.getByText("Purchase History")).toBeInTheDocument();
	});

	it("renders purchase rows with description and type", () => {
		render(<PurchaseTable {...defaultProps} />);
		expect(screen.getByText(MOCK_PURCHASES[0].description)).toBeInTheDocument();
		expect(screen.getByText(MOCK_PURCHASES[1].description)).toBeInTheDocument();
		expect(screen.getByText("purchase")).toBeInTheDocument();
		expect(screen.getByText("signup_grant")).toBeInTheDocument();
	});

	it("displays amount_display for each purchase", () => {
		render(<PurchaseTable {...defaultProps} />);
		expect(
			screen.getByText(MOCK_PURCHASES[0].amount_display),
		).toBeInTheDocument();
		expect(
			screen.getByText(MOCK_PURCHASES[1].amount_display),
		).toBeInTheDocument();
	});

	it("shows green text for positive amounts", () => {
		render(<PurchaseTable {...defaultProps} purchases={[MOCK_PURCHASES[0]]} />);
		const amount = screen.getByTestId("purchase-amount-p-1");
		expect(amount.className).toContain("text-success");
	});

	it("shows red text for negative amounts", () => {
		render(<PurchaseTable {...defaultProps} purchases={[MOCK_PURCHASES[2]]} />);
		const amount = screen.getByTestId("purchase-amount-p-3");
		expect(amount.className).toContain("text-destructive");
	});

	it("shows empty state when no purchases", () => {
		render(<PurchaseTable {...defaultProps} purchases={[]} />);
		expect(screen.getByText(/no purchases yet/i)).toBeInTheDocument();
	});

	it("shows loading state", () => {
		render(<PurchaseTable {...defaultProps} purchases={[]} isLoading={true} />);
		expect(screen.getByTestId("purchase-table-loading")).toBeInTheDocument();
	});

	it("calls onPageChange when Next is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<PurchaseTable
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
