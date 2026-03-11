/**
 * Tests for the UsagePage component.
 *
 * REQ-029 §9.1: Page layout with funding packs and purchase history.
 * REQ-029 §9.4: Success/cancel handling after Stripe redirect.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/lib/query-keys";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockReplace = vi.fn();
	const mockSearchParams = vi.fn();
	const mockShowToast = {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	};
	const mockUseBalance = vi.fn();
	const mockApiGet = vi.fn();
	const mockFetchPurchases = vi.fn();
	return {
		mockReplace,
		mockSearchParams,
		mockShowToast,
		mockUseBalance,
		mockApiGet,
		mockFetchPurchases,
	};
});

vi.mock("next/navigation", () => ({
	useRouter: () => ({ replace: mocks.mockReplace }),
	useSearchParams: mocks.mockSearchParams,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("@/hooks/use-balance", () => ({
	useBalance: mocks.mockUseBalance,
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

vi.mock("@/lib/api/credits", () => ({
	fetchPurchases: mocks.mockFetchPurchases,
}));

// ---------------------------------------------------------------------------
// Test IDs — single source of truth for mock components + assertions
// ---------------------------------------------------------------------------

const TID_LOW_BALANCE = "section-low-balance";
const TID_BALANCE_CARD = "section-balance-card";
const TID_FUNDING_PACKS = "section-funding-packs";
const TID_PURCHASE_TABLE = "section-purchase-table";
const TID_USAGE_SUMMARY = "section-usage-summary";
const TID_USAGE_TABLE = "section-usage-table";
const TID_TRANSACTION_TABLE = "section-transaction-table";

const STRIPE_SUCCESS_PARAMS = "status=success";

// ---------------------------------------------------------------------------
// Mock child components as simple marker divs
// ---------------------------------------------------------------------------

vi.mock("./balance-card", () => ({
	BalanceCard: () => <div data-testid={TID_BALANCE_CARD} />,
}));

vi.mock("./funding-packs", () => ({
	FundingPacks: () => <div data-testid={TID_FUNDING_PACKS} />,
}));

vi.mock("./low-balance-warning", () => ({
	LowBalanceWarning: ({ balance }: { balance: number }) => (
		<div data-testid={TID_LOW_BALANCE} data-balance={balance} />
	),
}));

vi.mock("./purchase-table", () => ({
	PurchaseTable: () => <div data-testid={TID_PURCHASE_TABLE} />,
}));

vi.mock("./usage-summary", () => ({
	UsageSummary: () => <div data-testid={TID_USAGE_SUMMARY} />,
}));

vi.mock("./usage-table", () => ({
	UsageTable: () => <div data-testid={TID_USAGE_TABLE} />,
}));

vi.mock("./transaction-table", () => ({
	TransactionTable: () => <div data-testid={TID_TRANSACTION_TABLE} />,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EMPTY_LIST_RESPONSE = {
	data: [],
	meta: { page: 1, per_page: 20, total: 0, total_pages: 1 },
};

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

async function renderUsagePage() {
	const { UsagePage } = await import("./usage-page");
	return render(<UsagePage />, { wrapper });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	mocks.mockSearchParams.mockReturnValue(new URLSearchParams());
	mocks.mockUseBalance.mockReturnValue({
		balance: "5.000000",
		isLoading: false,
		error: null,
	});
	mocks.mockApiGet.mockResolvedValue(EMPTY_LIST_RESPONSE);
	mocks.mockFetchPurchases.mockResolvedValue(EMPTY_LIST_RESPONSE);
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsagePage", () => {
	it("renders Usage & Billing heading", async () => {
		await renderUsagePage();
		expect(screen.getByText("Usage & Billing")).toBeInTheDocument();
	});

	it("renders all page sections", async () => {
		await renderUsagePage();
		expect(screen.getByTestId(TID_BALANCE_CARD)).toBeInTheDocument();
		expect(screen.getByTestId(TID_FUNDING_PACKS)).toBeInTheDocument();
		expect(screen.getByTestId(TID_PURCHASE_TABLE)).toBeInTheDocument();
		expect(screen.getByTestId(TID_USAGE_SUMMARY)).toBeInTheDocument();
		expect(screen.getByTestId(TID_USAGE_TABLE)).toBeInTheDocument();
		expect(screen.getByTestId(TID_TRANSACTION_TABLE)).toBeInTheDocument();
	});

	it("renders sections in correct DOM order", async () => {
		const { container } = await renderUsagePage();
		const html = container.innerHTML;
		const order = [
			TID_LOW_BALANCE,
			TID_BALANCE_CARD,
			TID_FUNDING_PACKS,
			TID_PURCHASE_TABLE,
			TID_USAGE_SUMMARY,
			TID_USAGE_TABLE,
			TID_TRANSACTION_TABLE,
		];
		for (let i = 0; i < order.length - 1; i++) {
			const posA = html.indexOf(order[i]);
			const posB = html.indexOf(order[i + 1]);
			expect(posA).toBeLessThan(posB);
		}
	});

	it("shows low-balance warning when balance is low", async () => {
		mocks.mockUseBalance.mockReturnValue({
			balance: "0.500000",
			isLoading: false,
			error: null,
		});
		await renderUsagePage();
		const warning = screen.getByTestId(TID_LOW_BALANCE);
		expect(warning).toBeInTheDocument();
		expect(warning).toHaveAttribute("data-balance", "0.5");
	});

	it("hides low-balance warning while balance is loading", async () => {
		mocks.mockUseBalance.mockReturnValue({
			balance: undefined,
			isLoading: true,
			error: null,
		});
		await renderUsagePage();
		expect(screen.queryByTestId(TID_LOW_BALANCE)).not.toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Stripe redirect handling (REQ-029 §9.4)
	// -----------------------------------------------------------------------

	describe("Stripe redirect handling", () => {
		it("shows success toast on status=success", async () => {
			mocks.mockSearchParams.mockReturnValue(
				new URLSearchParams(STRIPE_SUCCESS_PARAMS),
			);
			await renderUsagePage();
			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Payment successful! Your balance has been updated.",
				);
			});
		});

		it("invalidates balance query on status=success", async () => {
			const spy = vi.spyOn(queryClient, "invalidateQueries");
			mocks.mockSearchParams.mockReturnValue(
				new URLSearchParams(STRIPE_SUCCESS_PARAMS),
			);
			await renderUsagePage();
			await waitFor(() => {
				expect(spy).toHaveBeenCalledWith({
					queryKey: queryKeys.balance,
				});
			});
		});

		it("shows info toast on status=cancelled", async () => {
			mocks.mockSearchParams.mockReturnValue(
				new URLSearchParams("status=cancelled"),
			);
			await renderUsagePage();
			await waitFor(() => {
				expect(mocks.mockShowToast.info).toHaveBeenCalledWith(
					"Purchase cancelled.",
				);
			});
		});

		it("cleans URL by calling router.replace", async () => {
			mocks.mockSearchParams.mockReturnValue(
				new URLSearchParams(STRIPE_SUCCESS_PARAMS),
			);
			await renderUsagePage();
			await waitFor(() => {
				expect(mocks.mockReplace).toHaveBeenCalledWith("/usage");
			});
		});

		it("does nothing when no status param", async () => {
			await renderUsagePage();
			expect(mocks.mockShowToast.success).not.toHaveBeenCalled();
			expect(mocks.mockShowToast.info).not.toHaveBeenCalled();
			expect(mocks.mockReplace).not.toHaveBeenCalled();
		});
	});
});
