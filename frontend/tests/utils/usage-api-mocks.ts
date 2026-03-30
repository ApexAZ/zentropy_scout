/**
 * Stateful Playwright route mock controller for usage page E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * balance and summary responses can be customized per test.
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import {
	balanceResponse,
	checkoutErrorResponse,
	checkoutResponse,
	emptyPackList,
	emptyPurchaseList,
	emptyTransactionList,
	emptyUsageHistoryList,
	emptyUsageSummaryResponse,
	onboardedPersonaList,
	packList,
	purchaseList,
	transactionList,
	transactionPage1,
	transactionPage2,
	usageHistoryList,
	usageHistoryPage1,
	usageHistoryPage2,
	usageSummaryResponse,
} from "../fixtures/usage-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	PACK_IDS,
	TRANSACTION_IDS,
	USAGE_RECORD_IDS,
} from "../fixtures/usage-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UsageMockState {
	/** Balance string with 6 decimal places (e.g., "10.500000"). */
	balance: string;
	/** Whether to return paginated (2-page) usage history. */
	paginatedHistory: boolean;
	/** Whether to return paginated (2-page) transaction history. */
	paginatedTransactions: boolean;
	/** Whether to return empty data for all usage endpoints. */
	emptyState: boolean;
	/** Whether POST /credits/checkout returns 502 STRIPE_ERROR. */
	checkoutError: boolean;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class UsageMockController {
	state: UsageMockState;

	constructor(initialState?: Partial<UsageMockState>) {
		this.state = {
			balance: "10.500000",
			paginatedHistory: false,
			paginatedTransactions: false,
			emptyState: false,
			checkoutError: false,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|credits|persona-change-flags|personas|usage)/,
			async (route) => this.handleRoute(route),
		);
	}

	// -----------------------------------------------------------------------
	// Main router
	// -----------------------------------------------------------------------

	private async handleRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const parsed = new URL(url);
		const path = parsed.pathname;

		// ---- Chat messages — always empty ----
		if (path.includes("/chat")) {
			return this.json(route, this.emptyList());
		}

		// ---- Persona change flags — always empty ----
		if (path.endsWith("/persona-change-flags")) {
			return this.json(route, this.emptyList());
		}

		// ---- Personas (required for persona status guard) ----
		if (path.endsWith("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		// ---- Credits endpoints (REQ-029) ----
		if (path.includes("/credits")) {
			return this.handleCredits(route, path);
		}

		// ---- Usage endpoints ----
		if (path.includes("/usage")) {
			return this.handleUsage(route, path, parsed);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Credits handler (REQ-029)
	// -----------------------------------------------------------------------

	private async handleCredits(route: Route, path: string): Promise<void> {
		// GET /credits/packs
		if (path.endsWith("/credits/packs")) {
			if (this.state.emptyState) {
				return this.json(route, emptyPackList());
			}
			return this.json(route, packList());
		}

		// POST /credits/checkout
		if (
			path.endsWith("/credits/checkout") &&
			route.request().method() === "POST"
		) {
			if (this.state.checkoutError) {
				return this.json(route, checkoutErrorResponse(), 502);
			}
			return this.json(route, checkoutResponse());
		}

		// GET /credits/purchases
		if (path.endsWith("/credits/purchases")) {
			if (this.state.emptyState) {
				return this.json(route, emptyPurchaseList());
			}
			return this.json(route, purchaseList());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Usage handler
	// -----------------------------------------------------------------------

	private async handleUsage(
		route: Route,
		path: string,
		parsed: URL,
	): Promise<void> {
		// GET /usage/balance
		if (path.endsWith("/usage/balance")) {
			return this.json(route, balanceResponse(this.state.balance));
		}

		// GET /usage/summary
		if (path.endsWith("/usage/summary")) {
			if (this.state.emptyState) {
				return this.json(route, emptyUsageSummaryResponse());
			}
			return this.json(route, usageSummaryResponse());
		}

		// GET /usage/history
		if (path.endsWith("/usage/history")) {
			if (this.state.emptyState) {
				return this.json(route, emptyUsageHistoryList());
			}
			if (this.state.paginatedHistory) {
				const page = parsed.searchParams.get("page");
				if (page === "2") {
					return this.json(route, usageHistoryPage2());
				}
				return this.json(route, usageHistoryPage1());
			}
			return this.json(route, usageHistoryList());
		}

		// GET /usage/transactions
		if (path.endsWith("/usage/transactions")) {
			if (this.state.emptyState) {
				return this.json(route, emptyTransactionList());
			}
			if (this.state.paginatedTransactions) {
				const txPage = parsed.searchParams.get("page");
				if (txPage === "2") {
					return this.json(route, transactionPage2());
				}
				return this.json(route, transactionPage1());
			}
			return this.json(route, transactionList());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private emptyList(): {
		data: never[];
		meta: { total: 0; page: 1; per_page: 100; total_pages: 1 };
	} {
		return {
			data: [],
			meta: { total: 0, page: 1, per_page: 100, total_pages: 1 },
		};
	}

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * Set up mocks for the usage page with default data.
 * Balance: $10.50 (green), 3 usage records, 3 transactions.
 */
export async function setupUsageMocks(
	page: Page,
): Promise<UsageMockController> {
	const controller = new UsageMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with a specific balance for color threshold testing.
 */
export async function setupUsageMocksWithBalance(
	page: Page,
	balance: string,
): Promise<UsageMockController> {
	const controller = new UsageMockController({ balance });
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with paginated usage history (2 pages).
 */
export async function setupPaginatedUsageMocks(
	page: Page,
): Promise<UsageMockController> {
	const controller = new UsageMockController({ paginatedHistory: true });
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with paginated transaction history (2 pages).
 */
export async function setupPaginatedTransactionMocks(
	page: Page,
): Promise<UsageMockController> {
	const controller = new UsageMockController({ paginatedTransactions: true });
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with empty data for all usage endpoints.
 */
export async function setupEmptyUsageMocks(
	page: Page,
): Promise<UsageMockController> {
	const controller = new UsageMockController({ emptyState: true });
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with checkout error mode (POST /checkout returns 502).
 */
export async function setupCheckoutErrorMocks(
	page: Page,
): Promise<UsageMockController> {
	const controller = new UsageMockController({ checkoutError: true });
	await controller.setupRoutes(page);
	return controller;
}
