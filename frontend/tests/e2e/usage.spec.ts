/**
 * E2E tests for the usage dashboard page and balance indicator.
 *
 * REQ-020 §9: Balance display in navigation bar (color-coded, clickable),
 * usage dashboard page at /usage, and 402 insufficient balance handling.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import {
	setupEmptyUsageMocks,
	setupPaginatedTransactionMocks,
	setupPaginatedUsageMocks,
	setupUsageMocks,
	setupUsageMocksWithBalance,
	TRANSACTION_IDS,
} from "../utils/usage-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors
// ---------------------------------------------------------------------------

const BALANCE_INDICATOR = "balance-indicator";
const BALANCE_AMOUNT = "balance-amount";
const PAGE_1_OF_2 = "Page 1 of 2";
const PAGE_2_OF_2 = "Page 2 of 2";

// ---------------------------------------------------------------------------
// A. Balance Indicator in Navigation (4 tests)
// ---------------------------------------------------------------------------

test.describe("Balance Indicator — Navigation Bar", () => {
	test("displays balance in green when balance >= $1.00", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "10.500000");
		await page.goto("/");

		const indicator = page.getByTestId(BALANCE_INDICATOR);
		await expect(indicator).toBeVisible();
		await expect(indicator).toHaveText("$10.50");
		await expect(indicator).toHaveClass(/text-green-600/);
	});

	test("displays balance in amber when balance is $0.10–$1.00", async ({
		page,
	}) => {
		await setupUsageMocksWithBalance(page, "0.500000");
		await page.goto("/");

		const indicator = page.getByTestId(BALANCE_INDICATOR);
		await expect(indicator).toBeVisible();
		await expect(indicator).toHaveText("$0.50");
		await expect(indicator).toHaveClass(/text-amber-500/);
	});

	test("displays balance in red when balance < $0.10", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "0.050000");
		await page.goto("/");

		const indicator = page.getByTestId(BALANCE_INDICATOR);
		await expect(indicator).toBeVisible();
		await expect(indicator).toHaveText("$0.05");
		await expect(indicator).toHaveClass(/text-red-500/);
	});

	test("clicking balance indicator navigates to /usage", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/");

		const indicator = page.getByTestId(BALANCE_INDICATOR);
		await expect(indicator).toBeVisible();

		await indicator.click();
		await expect(page).toHaveURL(/\/usage/);
	});
});

// ---------------------------------------------------------------------------
// B. Usage Page Layout (2 tests)
// ---------------------------------------------------------------------------

test.describe("Usage Page Layout", () => {
	test("renders all four page sections with data", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// Page and heading
		await expect(page.getByTestId("usage-page")).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Usage & Billing" }),
		).toBeVisible();

		// Balance card with amount and disabled Add Funds button
		await expect(page.getByTestId("balance-card")).toBeVisible();
		await expect(page.getByTestId(BALANCE_AMOUNT)).toBeVisible();
		await expect(page.getByTestId(BALANCE_AMOUNT)).toHaveText("$10.50");
		await expect(
			page.getByRole("button", { name: "Add Funds" }),
		).toBeDisabled();

		// Period summary stats
		await expect(page.getByTestId("total-calls")).toHaveText("42");
		await expect(page.getByTestId("total-cost")).toHaveText("$3.90");
		await expect(page.getByTestId("total-tokens")).toHaveText("20,000");

		// Usage records table (Recent Activity)
		await expect(page.getByText("Recent Activity")).toBeVisible();
		await expect(
			page.getByText("claude-3-5-sonnet-20241022").first(),
		).toBeVisible();

		// Transaction history table
		await expect(page.getByText("Transaction History")).toBeVisible();
		await expect(page.getByText("Initial credit purchase")).toBeVisible();
	});

	test("renders empty state messages when no data", async ({ page }) => {
		await setupEmptyUsageMocks(page);
		await page.goto("/usage");

		await expect(page.getByTestId("usage-page")).toBeVisible();

		// Empty summary — API returns zero-filled data, component shows zeros
		await expect(page.getByTestId("total-calls")).toHaveText("0");
		await expect(page.getByTestId("total-cost")).toHaveText("$0.00");
		await expect(page.getByTestId("total-tokens")).toHaveText("0");

		// Breakdown tables hidden when no data
		await expect(page.getByText("By Task Type")).not.toBeAttached();
		await expect(page.getByText("By Provider")).not.toBeAttached();

		// Empty usage records
		await expect(page.getByText("No usage records yet.")).toBeVisible();

		// Empty transactions
		await expect(page.getByText("No transactions yet.")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Balance Card Color Coding (3 tests)
// ---------------------------------------------------------------------------

test.describe("Balance Card — Color Coding", () => {
	test("balance card shows green for high balance", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "5.000000");
		await page.goto("/usage");

		const amount = page.getByTestId(BALANCE_AMOUNT);
		await expect(amount).toHaveText("$5.00");
		await expect(amount).toHaveClass(/text-green-600/);
	});

	test("balance card shows amber for medium balance", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "0.750000");
		await page.goto("/usage");

		const amount = page.getByTestId(BALANCE_AMOUNT);
		await expect(amount).toHaveText("$0.75");
		await expect(amount).toHaveClass(/text-amber-500/);
	});

	test("balance card shows red for low balance", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "0.030000");
		await page.goto("/usage");

		const amount = page.getByTestId(BALANCE_AMOUNT);
		await expect(amount).toHaveText("$0.03");
		await expect(amount).toHaveClass(/text-red-500/);
	});
});

// ---------------------------------------------------------------------------
// D. Summary Breakdown Tables (2 tests)
// ---------------------------------------------------------------------------

test.describe("Summary Breakdown Tables", () => {
	test("displays cost breakdown by task type", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// By Task Type section heading
		await expect(page.getByText("By Task Type")).toBeVisible();

		// Task type rows — scoped to breakdown section via data-testid
		const taskTypeSection = page.getByTestId("task-type-breakdown");
		await expect(
			taskTypeSection.getByRole("cell", { name: "extraction" }),
		).toBeVisible();
		await expect(
			taskTypeSection.getByRole("cell", { name: "generation" }),
		).toBeVisible();
	});

	test("displays cost breakdown by provider", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// By Provider section heading
		await expect(page.getByText("By Provider")).toBeVisible();

		// Provider rows — scoped to breakdown section via data-testid
		const providerSection = page.getByTestId("provider-breakdown");
		await expect(
			providerSection.getByRole("cell", { name: "claude", exact: true }),
		).toBeVisible();
		await expect(
			providerSection.getByRole("cell", { name: "openai", exact: true }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Transaction Amount Colors (2 tests)
// ---------------------------------------------------------------------------

test.describe("Transaction Amount Colors", () => {
	test("credit amounts display in green", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// tx-001 is a +$10.00 purchase (positive = green)
		const creditAmount = page.getByTestId(`tx-amount-${TRANSACTION_IDS[0]}`);
		await expect(creditAmount).toBeVisible();
		await expect(creditAmount).toHaveText("+$10.00");
		await expect(creditAmount).toHaveClass(/text-green-600/);
	});

	test("debit amounts display in red", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// tx-002 is a -$0.01 usage debit (negative = red)
		const debitAmount = page.getByTestId(`tx-amount-${TRANSACTION_IDS[1]}`);
		await expect(debitAmount).toBeVisible();
		await expect(debitAmount).toHaveClass(/text-red-500/);
	});
});

// ---------------------------------------------------------------------------
// F. Pagination (2 tests)
// ---------------------------------------------------------------------------

test.describe("Usage History Pagination", () => {
	test("shows pagination controls with page info", async ({ page }) => {
		await setupPaginatedUsageMocks(page);
		await page.goto("/usage");

		// Should show "Page 1 of 2"
		await expect(page.getByText(PAGE_1_OF_2)).toBeVisible();

		// Previous should be disabled on page 1
		const prevButton = page.getByRole("button", { name: "Previous" }).first();
		await expect(prevButton).toBeDisabled();

		// Next should be enabled
		const nextButton = page.getByRole("button", { name: "Next" }).first();
		await expect(nextButton).toBeEnabled();
	});

	test("clicking Next loads page 2", async ({ page }) => {
		await setupPaginatedUsageMocks(page);
		await page.goto("/usage");

		await expect(page.getByText(PAGE_1_OF_2)).toBeVisible();

		// Click Next on the usage history table (first pagination)
		const nextButton = page.getByRole("button", { name: "Next" }).first();
		await nextButton.click();

		// Should now show page 2 content
		await expect(page.getByText(PAGE_2_OF_2)).toBeVisible();
	});
});

test.describe("Transaction History Pagination", () => {
	test("shows pagination and navigates to page 2", async ({ page }) => {
		await setupPaginatedTransactionMocks(page);
		await page.goto("/usage");

		// Transaction table should show "Page 1 of 2"
		await expect(page.getByText(PAGE_1_OF_2)).toBeVisible();

		// Hide TanStack Query DevTools floating button — its SVG circle
		// overlaps the transaction table pagination at the bottom of the page.
		const tsqd = page.locator(".tsqd-parent-container");
		if (await tsqd.count()) {
			await tsqd.evaluate((el) => (el.style.display = "none"));
		}

		// Click Next — use exact match to avoid the Next.js Dev Tools
		// button whose aria-label ("Open Next.js Dev Tools") contains "Next"
		const nextButton = page.getByRole("button", { name: "Next", exact: true });
		await nextButton.click();

		// Should now show page 2
		await expect(page.getByText(PAGE_2_OF_2)).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// G. 402 Insufficient Balance Toast (1 test)
// ---------------------------------------------------------------------------

test.describe("402 Insufficient Balance", () => {
	test("shows error toast when balance API returns 402", async ({ page }) => {
		// Set up usage mocks but override balance to return 402.
		// The useBalance hook calls apiGet → apiFetch, which triggers
		// handleInsufficientBalance(402) → showToast.error() before throwing.
		await setupUsageMocks(page);

		// Override balance endpoint AFTER setup (later routes take priority)
		await page.route(/\/api\/v1\/usage\/balance/, async (route) => {
			await route.fulfill({
				status: 402,
				contentType: "application/json",
				body: JSON.stringify({
					error: {
						code: "INSUFFICIENT_BALANCE",
						message: "Your balance is $0.00. Please add funds to continue.",
						details: [
							{
								balance_usd: "0.000000",
								minimum_required: "0.000001",
							},
						],
					},
				}),
			});
		});

		await page.goto("/");

		// Error toast should appear from the useBalance hook's failed fetch
		await expect(
			page.getByText("Insufficient balance. Please add funds to continue."),
		).toBeVisible();
	});
});
