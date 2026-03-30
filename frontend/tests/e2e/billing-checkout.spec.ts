/**
 * E2E tests for billing checkout flows and funding pack display.
 *
 * REQ-029 §9.2: Funding pack cards with checkout redirect.
 * REQ-029 §9.3: Checkout flow via location.assign.
 * REQ-029 §9.4: Stripe redirect success/cancel handling.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, type Page, test } from "./base-test";

import {
	PACK_IDS,
	setupCheckoutErrorMocks,
	setupUsageMocks,
	setupUsageMocksWithBalance,
} from "../utils/usage-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors
// ---------------------------------------------------------------------------

const ADD_FUNDS = "Add Funds";
const TOGGLE_CHAT = "Toggle chat";
const MESSAGE_INPUT = "Message";
const SEND_MESSAGE = "Send message";
const INSUFFICIENT_BALANCE_TOAST =
	"Insufficient balance. Please add funds to continue.";
const LOW_BALANCE_WARNING = "low-balance-warning";

// ---------------------------------------------------------------------------
// A. Funding Pack Display (2 tests)
// ---------------------------------------------------------------------------

test.describe("Funding Pack Display", () => {
	test("renders all 3 pack cards with name, price, description, and Add Funds button", async ({
		page,
	}) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// Starter pack ($5.00)
		const starter = page.getByTestId(`pack-card-${PACK_IDS[0]}`);
		await expect(starter).toBeVisible();
		await expect(starter.getByText("Starter")).toBeVisible();
		await expect(starter.getByText("$5.00")).toBeVisible();
		await expect(starter.getByText("Good for getting started")).toBeVisible();
		await expect(
			starter.getByRole("button", { name: ADD_FUNDS }),
		).toBeVisible();

		// Popular pack ($20.00)
		const popular = page.getByTestId(`pack-card-${PACK_IDS[1]}`);
		await expect(popular).toBeVisible();
		await expect(popular.getByText("Popular", { exact: true })).toBeVisible();
		await expect(popular.getByText("$20.00")).toBeVisible();
		await expect(
			popular.getByText("Best value for regular users"),
		).toBeVisible();
		await expect(
			popular.getByRole("button", { name: ADD_FUNDS }),
		).toBeVisible();

		// Pro pack ($50.00)
		const pro = page.getByTestId(`pack-card-${PACK_IDS[2]}`);
		await expect(pro).toBeVisible();
		await expect(pro.getByText("Pro")).toBeVisible();
		await expect(pro.getByText("$50.00")).toBeVisible();
		await expect(pro.getByText("For power users")).toBeVisible();
		await expect(pro.getByRole("button", { name: ADD_FUNDS })).toBeVisible();
	});

	test("highlighted pack shows Most Popular badge", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage");

		// Popular pack (pack-002) has "Most Popular" highlight badge
		const badge = page.getByTestId(`highlight-badge-${PACK_IDS[1]}`);
		await expect(badge).toBeVisible();
		await expect(badge).toHaveText("Most Popular");

		// Starter and Pro packs should not have highlight badges
		await expect(
			page.getByTestId(`highlight-badge-${PACK_IDS[0]}`),
		).not.toBeAttached();
		await expect(
			page.getByTestId(`highlight-badge-${PACK_IDS[2]}`),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// B. Checkout Flow (4 tests)
// ---------------------------------------------------------------------------

test.describe("Checkout Flow", () => {
	test("clicking Add Funds redirects to Stripe checkout URL", async ({
		page,
	}) => {
		await setupUsageMocks(page);

		// Intercept navigation to Stripe checkout to prevent actual redirect
		await page.route("https://checkout.stripe.test/**", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "text/html",
				body: "<html></html>",
			});
		});

		await page.goto("/usage");

		// Click "Add Funds" on the Starter pack
		await page
			.getByTestId(`pack-card-${PACK_IDS[0]}`)
			.getByRole("button", { name: ADD_FUNDS })
			.click();

		// Verify page navigated to the mock Stripe checkout URL
		await page.waitForURL("**/checkout.stripe.test/**");
		expect(page.url()).toBe("https://checkout.stripe.test/mock-session");
	});

	test("checkout success shows toast and cleans URL", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage?status=success");

		// Success toast — .first() needed because React Strict Mode
		// double-fires the useEffect, creating duplicate toast elements
		await expect(
			page
				.getByText("Payment successful! Your balance has been updated.")
				.first(),
		).toBeVisible();

		// URL should be cleaned to /usage (query params stripped)
		await expect(page).toHaveURL(/\/usage$/);
	});

	test("checkout cancel shows toast and cleans URL", async ({ page }) => {
		await setupUsageMocks(page);
		await page.goto("/usage?status=cancelled");

		// Cancel toast — .first() for React Strict Mode (see success test)
		await expect(page.getByText("Purchase cancelled.").first()).toBeVisible();

		// URL should be cleaned to /usage
		await expect(page).toHaveURL(/\/usage$/);
	});

	test("checkout error shows error toast and re-enables button", async ({
		page,
	}) => {
		await setupCheckoutErrorMocks(page);
		await page.goto("/usage");

		// Click "Add Funds" on the Starter pack
		const button = page
			.getByTestId(`pack-card-${PACK_IDS[0]}`)
			.getByRole("button", { name: ADD_FUNDS });
		await button.click();

		// Error toast should appear
		await expect(
			page.getByText("Unable to start checkout. Please try again."),
		).toBeVisible();

		// Button should be re-enabled with original text (not "Redirecting…")
		await expect(button).toBeEnabled();
		await expect(button).toHaveText(ADD_FUNDS);
	});
});

// ---------------------------------------------------------------------------
// C. 402 Insufficient Balance (2 tests)
// ---------------------------------------------------------------------------

test.describe("402 Insufficient Balance", () => {
	// Override POST /chat/messages to return 402 (LIFO priority over base-test)
	test.beforeEach(async ({ page }) => {
		await page.route(/\/api\/v1\/chat\/.*messages/, async (route) => {
			if (route.request().method() === "POST") {
				await route.fulfill({
					status: 402,
					contentType: "application/json",
					body: JSON.stringify({
						error: {
							code: "INSUFFICIENT_BALANCE",
							message: "Insufficient balance",
						},
					}),
				});
			} else {
				await route.fallback();
			}
		});
	});

	/** Navigate to dashboard, open chat, and send a message. */
	async function sendChatMessage(page: Page): Promise<void> {
		await page.goto("/dashboard");
		await page.getByRole("button", { name: TOGGLE_CHAT }).click();
		const textarea = page.getByRole("textbox", { name: MESSAGE_INPUT });
		await textarea.fill("Hello Scout");
		await page.getByRole("button", { name: SEND_MESSAGE }).click();
	}

	test("402 from chat message shows insufficient balance toast", async ({
		page,
	}) => {
		await sendChatMessage(page);

		await expect(page.getByText(INSUFFICIENT_BALANCE_TOAST)).toBeVisible();
	});

	test("insufficient balance toast persists and does not auto-dismiss", async ({
		page,
	}) => {
		await sendChatMessage(page);

		const toast = page.getByText(INSUFFICIENT_BALANCE_TOAST);
		await expect(toast).toBeVisible();

		// Wait longer than info/warning auto-dismiss duration (5 s).
		// Error toasts use duration: Infinity, so this must survive.
		await page.waitForTimeout(6000);

		// Toast should still be visible — confirms persistence
		await expect(toast).toBeVisible({ timeout: 5_000 });
	});
});

// ---------------------------------------------------------------------------
// D. Low Balance Warning (3 tests)
// ---------------------------------------------------------------------------

test.describe("Low Balance Warning", () => {
	test("low balance shows amber warning banner", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "0.500000");
		await page.goto("/usage");

		const warning = page.getByTestId(LOW_BALANCE_WARNING);
		await expect(warning).toBeVisible();
		await expect(
			warning.getByText("Your balance is running low"),
		).toBeVisible();
		await expect(warning).toHaveClass(/text-primary/);
	});

	test("critically low balance shows red warning banner", async ({ page }) => {
		await setupUsageMocksWithBalance(page, "0.030000");
		await page.goto("/usage");

		const warning = page.getByTestId(LOW_BALANCE_WARNING);
		await expect(warning).toBeVisible();
		await expect(
			warning.getByText("Your balance is nearly empty"),
		).toBeVisible();
		await expect(warning).toHaveClass(/text-destructive/);
	});

	test("warning contains Add Funds link to #funding-packs", async ({
		page,
	}) => {
		await setupUsageMocksWithBalance(page, "0.500000");
		await page.goto("/usage");

		const warning = page.getByTestId(LOW_BALANCE_WARNING);
		const link = warning.getByRole("link", { name: ADD_FUNDS });
		await expect(link).toBeVisible();
		await expect(link).toHaveAttribute("href", "#funding-packs");
	});
});

// ---------------------------------------------------------------------------
// E. Button Loading State (1 test)
// ---------------------------------------------------------------------------

test.describe("Button Loading State", () => {
	test("clicking Add Funds shows Redirecting spinner and disables all pack buttons", async ({
		page,
	}) => {
		await setupUsageMocks(page);

		// Override checkout with a never-resolving handler to freeze loading state.
		// LIFO priority ensures this takes precedence over UsageMockController.
		await page.route(/\/api\/v1\/credits\/checkout/, () => {
			// Intentionally never fulfill — keeps the request pending
		});

		await page.goto("/usage");

		// Click "Add Funds" on the Starter pack
		await page
			.getByTestId(`pack-card-${PACK_IDS[0]}`)
			.getByRole("button", { name: ADD_FUNDS })
			.click();

		// Clicked button shows "Redirecting…" spinner and is disabled
		const clickedButton = page
			.getByTestId(`pack-card-${PACK_IDS[0]}`)
			.getByRole("button");
		await expect(clickedButton).toContainText("Redirecting");
		await expect(clickedButton).toBeDisabled();

		// All other pack buttons are also disabled but retain original text
		for (const packId of [PACK_IDS[1], PACK_IDS[2]]) {
			const btn = page.getByTestId(`pack-card-${packId}`).getByRole("button");
			await expect(btn).toBeDisabled();
			await expect(btn).toHaveText(ADD_FUNDS);
		}
	});
});
