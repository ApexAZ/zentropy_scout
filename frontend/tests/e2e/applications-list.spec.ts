/**
 * E2E tests for the dedicated applications list page (/applications).
 *
 * REQ-012 §11.1: Full application tracking table with toolbar (search,
 * filter, sort, show archived, select mode), multi-select with bulk archive,
 * and row click navigation.
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import { setupApplicationsListMocks } from "../utils/app-tracking-api-mocks";

// ---------------------------------------------------------------------------
// A. Applications List — Display (2 tests)
// ---------------------------------------------------------------------------

test.describe("Applications List — Display", () => {
	test("shows heading, table, and toolbar controls", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		// Page heading
		await expect(
			page.getByRole("heading", { name: "Applications" }),
		).toBeVisible();

		// Table visible with data
		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Toolbar controls visible
		await expect(page.getByLabel("Status filter")).toBeVisible();
		await expect(page.getByLabel("Sort by")).toBeVisible();
		await expect(page.getByTestId("select-mode-button")).toBeVisible();
		await expect(page.getByPlaceholder("Search applications...")).toBeVisible();

		// Active apps visible (5 non-archived: Applied, Interviewing, Offer,
		// Accepted, Rejected). The Withdrawn+Archived one is excluded by default.
		await expect(page.getByText("AlphaTech")).toBeVisible();
		await expect(page.getByText("BetaWorks")).toBeVisible();
		await expect(page.getByText("GammaCorp")).toBeVisible();
		await expect(page.getByText("DeltaSoft")).toBeVisible();
		await expect(page.getByText("EpsilonIO")).toBeVisible();

		// Archived app should NOT be visible by default
		await expect(page.getByText("ZetaCloud")).not.toBeVisible();
	});

	test("show archived checkbox reveals archived application", async ({
		page,
	}) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Archived app not visible
		await expect(page.getByText("ZetaCloud")).not.toBeVisible();

		// Check "Show archived"
		await page.getByLabel("Show archived").check();

		// Now the archived app should appear
		await expect(page.getByText("ZetaCloud")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Applications List — Filter & Search (2 tests)
// ---------------------------------------------------------------------------

test.describe("Applications List — Filter & Search", () => {
	test("status filter narrows results", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Select "Offer" from status filter
		await page.getByLabel("Status filter").click();
		await page.getByRole("option", { name: "Offer" }).click();

		// Only the Offer app should be visible
		await expect(page.getByText("GammaCorp")).toBeVisible();
		await expect(page.getByText("AlphaTech")).not.toBeVisible();
		await expect(page.getByText("BetaWorks")).not.toBeVisible();
	});

	test("search filters applications client-side", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Type a company name into the search box
		await page.getByPlaceholder("Search applications...").fill("BetaWorks");

		// Only the BetaWorks app should remain visible
		await expect(page.getByText("BetaWorks")).toBeVisible();
		await expect(page.getByText("AlphaTech")).not.toBeVisible();
		await expect(page.getByText("GammaCorp")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Applications List — Select Mode & Bulk Archive (3 tests)
// ---------------------------------------------------------------------------

test.describe("Applications List — Select Mode & Bulk Archive", () => {
	test("select mode shows checkboxes and action bar", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Enter select mode
		await page.getByTestId("select-mode-button").click();

		// Selection action bar should appear
		await expect(page.getByTestId("selection-action-bar")).toBeVisible();
		await expect(page.getByTestId("selected-count")).toContainText(
			"0 selected",
		);
		await expect(page.getByTestId("bulk-archive-button")).toBeDisabled();
		await expect(page.getByTestId("cancel-select-button")).toBeVisible();

		// Checkboxes should be visible in the table
		await expect(page.getByRole("checkbox").first()).toBeVisible();
	});

	test("bulk archive sends POST and exits select mode", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Enter select mode
		await page.getByTestId("select-mode-button").click();
		await expect(page.getByTestId("selection-action-bar")).toBeVisible();

		// Select the first app checkbox (skip "select all" header checkbox)
		const checkboxes = page.getByRole("checkbox");
		await checkboxes.nth(1).check();

		// Selected count should update
		await expect(page.getByTestId("selected-count")).toContainText(
			"1 selected",
		);

		// Set up POST listener for bulk-archive
		const postPromise = page.waitForResponse(
			(res) =>
				res.url().includes("/applications/bulk-archive") &&
				res.request().method() === "POST",
		);

		// Click Bulk Archive
		await page.getByTestId("bulk-archive-button").click();

		// Verify POST sent
		const response = await postPromise;
		expect(response.status()).toBe(200);

		// Should exit select mode (action bar gone, normal toolbar back)
		await expect(page.getByTestId("selection-action-bar")).not.toBeVisible();
		await expect(page.getByTestId("select-mode-button")).toBeVisible();
	});

	test("cancel button exits select mode", async ({ page }) => {
		await setupApplicationsListMocks(page);
		await page.goto("/applications");

		await expect(page.getByTestId("applications-list")).toBeVisible();

		// Enter select mode
		await page.getByTestId("select-mode-button").click();
		await expect(page.getByTestId("selection-action-bar")).toBeVisible();

		// Cancel
		await page.getByTestId("cancel-select-button").click();

		// Back to normal toolbar
		await expect(page.getByTestId("selection-action-bar")).not.toBeVisible();
		await expect(page.getByTestId("select-mode-button")).toBeVisible();
	});
});
