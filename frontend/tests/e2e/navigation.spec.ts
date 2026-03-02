/**
 * E2E tests for navigation, badge counts, error states, and toast notifications.
 *
 * REQ-012 §3.2: Top nav links to major sections with badge indicators.
 * REQ-012 §13.5: Toast duration — success 3 s auto-dismiss, error persistent.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, type Page, type Route, test } from "@playwright/test";

import { changeFlagsList } from "../fixtures/persona-update-mock-data";
import { balanceResponse } from "../fixtures/usage-mock-data";
import { setupAdminMocks } from "../utils/admin-api-mocks";
import { setupDashboardMocks } from "../utils/job-discovery-api-mocks";
import { setupSettingsMocks } from "../utils/settings-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors & helpers
// ---------------------------------------------------------------------------

const FAILED_STATE = '[data-slot="failed-state"]';
const JOB_SOURCES_SECTION = "job-sources-section";

const SERVER_ERROR_BODY = JSON.stringify({
	error: { code: "INTERNAL_ERROR", message: "Server error" },
});

/** Override PATCH on user-source-preferences to return 500. */
async function overridePatchToFail(page: Page): Promise<void> {
	await page.route(/\/api\/v1\/user-source-preferences\//, async (route) => {
		if (route.request().method() === "PATCH") {
			await route.fulfill({
				status: 500,
				contentType: "application/json",
				body: SERVER_ERROR_BODY,
			});
		} else {
			await route.fallback();
		}
	});
}

// ---------------------------------------------------------------------------
// A. Nav Link Rendering (1 test)
// ---------------------------------------------------------------------------

test.describe("Nav Link Rendering", () => {
	test("displays all primary nav links and settings link", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		const nav = page.getByRole("navigation", { name: "Main navigation" });
		await expect(nav).toBeVisible();

		// Primary nav links
		await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
		await expect(page.getByRole("link", { name: "Persona" })).toBeVisible();
		await expect(page.getByRole("link", { name: "Resumes" })).toBeVisible();
		await expect(
			page.getByRole("link", { name: "Applications" }),
		).toBeVisible();

		// Settings (right-aligned, hidden on mobile)
		await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();

		// Chat toggle button
		await expect(
			page.getByRole("button", { name: "Toggle chat" }),
		).toBeVisible();
	});

	test("displays balance indicator when balance API responds", async ({
		page,
	}) => {
		await setupDashboardMocks(page);

		// Add balance route (not included in dashboard mocks)
		await page.route(/\/api\/v1\/usage\/balance/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(balanceResponse("5.000000")),
			});
		});

		await page.goto("/");

		const indicator = page.getByTestId("balance-indicator");
		await expect(indicator).toBeVisible();
		await expect(indicator).toHaveText("$5.00");
	});

	test("displays Admin link when user is admin", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/");

		await expect(page.getByRole("link", { name: "Admin" })).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Active Link Highlight (1 test)
// ---------------------------------------------------------------------------

test.describe("Active Link Highlight", () => {
	test("marks the current page link with aria-current", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Dashboard link should be active on "/"
		const dashboardLink = page.getByRole("link", { name: "Dashboard" });
		await expect(dashboardLink).toHaveAttribute("aria-current", "page");

		// Other links should not be marked active
		const personaLink = page.getByRole("link", { name: "Persona" });
		await expect(personaLink).not.toHaveAttribute("aria-current", "page");
	});
});

// ---------------------------------------------------------------------------
// C. Badge Counts (2 tests)
// ---------------------------------------------------------------------------

test.describe("Badge Counts", () => {
	test("shows persona badge when pending flags exist", async ({ page }) => {
		await setupDashboardMocks(page);

		// Override change-flags route to return 3 pending flags
		const flags = changeFlagsList();
		await page.route(/\/api\/v1\/persona-change-flags/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(flags),
			});
		});

		await page.goto("/");

		// Badge should be visible with count "3"
		const badge = page.getByTestId("pending-flags-badge");
		await expect(badge).toBeVisible();
		await expect(badge).toHaveText("3");
	});

	test("hides persona badge when no pending flags exist", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Dashboard mocks return empty change flags list → no badge
		await expect(page.getByTestId("pending-flags-badge")).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// D. Error States (2 tests)
// ---------------------------------------------------------------------------

test.describe("Error States", () => {
	test("shows error alert with retry button when API returns server error", async ({
		page,
	}) => {
		await setupSettingsMocks(page);

		// Override job-sources to return 500 (registered after setup → takes priority)
		await page.route(/\/api\/v1\/job-sources$/, async (route) => {
			if (route.request().method() === "GET") {
				await route.fulfill({
					status: 500,
					contentType: "application/json",
					body: SERVER_ERROR_BODY,
				});
			}
		});

		await page.goto("/settings");

		const failedState = page.locator(FAILED_STATE);
		await expect(failedState).toBeVisible();
		await expect(failedState).toHaveAttribute("role", "alert");
		await expect(failedState).toContainText("Failed to load.");

		// Retry button should be present
		await expect(
			failedState.getByRole("button", { name: "Retry" }),
		).toBeVisible();
	});

	test("retry button recovers from server error and loads content", async ({
		page,
	}) => {
		await setupSettingsMocks(page);

		// Always-fail handler for job-sources GET. Registered AFTER setup, so
		// it takes priority over the controller's success handler (LIFO order).
		const jobSourcesPattern = /\/api\/v1\/job-sources$/;
		const failHandler = async (route: Route) => {
			if (route.request().method() === "GET") {
				await route.fulfill({
					status: 500,
					contentType: "application/json",
					body: SERVER_ERROR_BODY,
				});
			} else {
				await route.fallback();
			}
		};
		await page.route(jobSourcesPattern, failHandler);

		await page.goto("/settings");

		// React Query retries once (retry: 1) with ~1 s delay. Under parallel
		// workers, Next.js dev compilation adds latency, so use a generous
		// timeout to avoid flakiness.
		const failedState = page.locator(FAILED_STATE);
		await expect(failedState).toBeVisible({ timeout: 15_000 });

		// Remove the failing handler — subsequent requests fall through to the
		// setupSettingsMocks controller which returns success.
		await page.unroute(jobSourcesPattern, failHandler);

		// Click Retry
		await failedState.getByRole("button", { name: "Retry" }).click();

		// Error alert should disappear and job sources section should load
		await expect(failedState).not.toBeAttached();
		await expect(page.getByTestId(JOB_SOURCES_SECTION)).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// E. Toast Notifications (2 tests)
// ---------------------------------------------------------------------------

test.describe("Toast Notifications", () => {
	test("shows error toast when mutation fails", async ({ page }) => {
		await setupSettingsMocks(page);
		await overridePatchToFail(page);

		await page.goto("/settings");
		await expect(page.getByTestId(JOB_SOURCES_SECTION)).toBeVisible();

		// Click Adzuna toggle (will fail)
		await page.getByRole("switch", { name: "Toggle Adzuna" }).click();

		// Error toast should appear
		await expect(
			page.getByText("Failed to update source preference."),
		).toBeVisible();
	});

	test("error toast persists past the success auto-dismiss window", async ({
		page,
	}) => {
		await setupSettingsMocks(page);
		await overridePatchToFail(page);

		await page.goto("/settings");
		await expect(page.getByTestId(JOB_SOURCES_SECTION)).toBeVisible();

		// Trigger error toast
		await page.getByRole("switch", { name: "Toggle Adzuna" }).click();

		const errorToast = page.getByText("Failed to update source preference.");
		await expect(errorToast).toBeVisible();

		// Error toasts use duration: Infinity (REQ-012 §13.5).
		// Wait past the 3 s success auto-dismiss window to verify persistence.
		await page.waitForTimeout(4000);
		// Under parallel workers, Next.js HMR may cause brief re-renders.
		// Allow extra time for the toast to re-stabilize in the DOM.
		await expect(errorToast).toBeVisible({ timeout: 5_000 });
	});
});
