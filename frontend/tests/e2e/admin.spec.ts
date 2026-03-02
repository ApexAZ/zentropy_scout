/**
 * E2E tests for the admin configuration page, nav link, and auth gate.
 *
 * REQ-022 §11: Admin frontend — 6 tabs (Models, Pricing, Routing, Packs,
 * System, Users), nav bar admin link, middleware route guard.
 * REQ-022 §15.4: Frontend test scenarios.
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import { setupAdminMocks, setupNonAdminMocks } from "../utils/admin-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors
// ---------------------------------------------------------------------------

const ADMIN_CONFIG_PAGE = "admin-config-page";
const MODELS_TAB = "models-tab";
const PRICING_TAB = "pricing-tab";
const ROUTING_TAB = "routing-tab";
const PACKS_TAB = "packs-tab";
const SYSTEM_TAB = "system-tab";
const USERS_TAB = "users-tab";

// ---------------------------------------------------------------------------
// A. Admin Auth Gate (2 tests)
// ---------------------------------------------------------------------------

test.describe("Admin Auth Gate", () => {
	test("redirects non-admin to home when visiting /admin/config", async ({
		page,
	}) => {
		// The default cookie from playwright.config.ts is "mock-e2e-session"
		// which is NOT a valid JWT. The proxy decodes it, gets null payload,
		// and redirects to "/".
		await setupNonAdminMocks(page);

		await page.goto("/admin/config");

		// Should be redirected to home (proxy gate)
		await expect(page).toHaveURL("/");
	});

	test("admin page loads when user has admin JWT", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(ADMIN_CONFIG_PAGE)).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Admin Configuration" }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Admin Page Tab Navigation (2 tests)
// ---------------------------------------------------------------------------

test.describe("Admin Page — Tab Navigation", () => {
	test("displays all 6 tabs", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByRole("tab", { name: "Models" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Pricing" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Routing" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Packs" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "System" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Users" })).toBeVisible();
	});

	test("clicking a tab switches content", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		// Default tab is Models
		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Switch to Users tab
		await page.getByRole("tab", { name: "Users" }).click();
		await expect(page.getByTestId(USERS_TAB)).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// C. Models Tab (5 tests)
// ---------------------------------------------------------------------------

test.describe("Admin — Models Tab", () => {
	test("renders model table with data", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Table should show model data
		await expect(
			page.getByRole("cell", { name: "claude-3-5-sonnet-20241022" }),
		).toBeVisible();
		await expect(
			page.getByRole("cell", { name: "Claude 3.5 Sonnet" }),
		).toBeVisible();
		await expect(
			page.getByRole("cell", { name: "claude-3-5-haiku-20241022" }),
		).toBeVisible();
	});

	test("opens add model dialog", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Click "Add Model" button
		await page.getByRole("button", { name: "Add Model" }).click();

		// Dialog should open
		await expect(
			page.getByRole("heading", { name: "Add Model" }),
		).toBeVisible();

		// Create button should be disabled (no fields filled)
		await expect(page.getByRole("button", { name: "Create" })).toBeDisabled();
	});

	test("submits add model form and shows success toast", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Open Add Model dialog
		await page.getByRole("button", { name: "Add Model" }).click();
		await expect(
			page.getByRole("heading", { name: "Add Model" }),
		).toBeVisible();

		// Fill in all required fields (scope to dialog to avoid ambiguity)
		const dialog = page.getByRole("dialog", { name: "Add Model" });
		await dialog.getByLabel("Provider").click();
		await page.getByRole("option", { name: "claude" }).click();
		await dialog
			.getByRole("textbox", { name: "Model" })
			.fill("claude-4-opus-20260301");
		await dialog.getByLabel("Display Name").fill("Claude 4 Opus");
		await dialog.getByLabel("Model Type").click();
		await page.getByRole("option", { name: "llm" }).click();

		// Create button should now be enabled
		const createBtn = page.getByRole("button", { name: "Create" });
		await expect(createBtn).toBeEnabled();
		await createBtn.click();

		// Should show success toast
		await expect(page.getByText(/created/i)).toBeVisible({
			timeout: 5_000,
		});
	});

	test("delete model shows confirmation dialog", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Click the first delete button
		const deleteButtons = page.getByRole("button", { name: "Delete" });
		await deleteButtons.first().click();

		// Confirmation dialog should appear
		await expect(
			page.getByRole("heading", { name: "Delete Model?" }),
		).toBeVisible();

		// Confirm and verify toast
		await page.getByRole("button", { name: "Confirm" }).click();
		await expect(page.getByText(/deleted/i)).toBeVisible({
			timeout: 5_000,
		});
	});

	test("active toggle calls API and shows toast", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await expect(page.getByTestId(MODELS_TAB)).toBeVisible();

		// Click the first active toggle button (Power icon)
		const toggleButtons = page.getByRole("button", {
			name: /toggle active/i,
		});
		await toggleButtons.first().click();

		// Should show success toast
		await expect(page.getByText(/updated/i)).toBeVisible({
			timeout: 5_000,
		});
	});
});

// ---------------------------------------------------------------------------
// D. Pricing Tab (3 tests)
// ---------------------------------------------------------------------------

test.describe("Admin — Pricing Tab", () => {
	test("renders pricing table with current badge", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		// Switch to Pricing tab
		await page.getByRole("tab", { name: "Pricing" }).click();
		await expect(page.getByTestId(PRICING_TAB)).toBeVisible();

		// Table should show pricing data
		await expect(
			page.getByRole("cell", { name: "claude-3-5-sonnet-20241022" }).first(),
		).toBeVisible();

		// "Current" badge should be visible
		await expect(page.getByText("Current").first()).toBeVisible();
	});

	test("opens add pricing dialog with cost preview", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Pricing" }).click();
		await expect(page.getByTestId(PRICING_TAB)).toBeVisible();

		// Click "Add Pricing" button
		await page.getByRole("button", { name: /add pricing/i }).click();

		// Dialog should open
		await expect(
			page.getByRole("heading", { name: "Add Pricing" }),
		).toBeVisible();

		// Fill in cost fields to trigger cost preview
		await page.getByLabel(/input cost/i).fill("0.003");
		await page.getByLabel(/output cost/i).fill("0.015");
		await page.getByLabel(/margin/i).fill("1.30");

		// Cost preview should appear
		await expect(page.getByTestId("cost-preview")).toBeVisible();
		await expect(page.getByText("Raw cost:")).toBeVisible();
		await expect(page.getByText("Billed cost:")).toBeVisible();
	});

	test("cost preview updates when margin changes", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Pricing" }).click();
		await page.getByRole("button", { name: /add pricing/i }).click();

		// Fill cost fields
		await page.getByLabel(/input cost/i).fill("0.003");
		await page.getByLabel(/output cost/i).fill("0.015");
		await page.getByLabel(/margin/i).fill("1.00");

		// Capture initial billed cost text
		const preview = page.getByTestId("cost-preview");
		await expect(preview).toBeVisible();
		const initialText = await preview.textContent();

		// Change margin to 3.00
		await page.getByLabel(/margin/i).fill("");
		await page.getByLabel(/margin/i).fill("3.00");

		// Preview should update (different billed cost)
		await expect(preview).not.toHaveText(initialText ?? "");
	});
});

// ---------------------------------------------------------------------------
// E. Routing Tab (1 test)
// ---------------------------------------------------------------------------

test.describe("Admin — Routing Tab", () => {
	test("renders routing table with model display names", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Routing" }).click();
		await expect(page.getByTestId(ROUTING_TAB)).toBeVisible();

		// Table should show routing data
		await expect(page.getByRole("cell", { name: "extraction" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "_default" })).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// F. Packs Tab (1 test)
// ---------------------------------------------------------------------------

test.describe("Admin — Packs Tab", () => {
	test("renders credit pack table", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Packs" }).click();
		await expect(page.getByTestId(PACKS_TAB)).toBeVisible();

		// Table should show pack data
		await expect(page.getByRole("cell", { name: "Starter" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "Pro" })).toBeVisible();
		await expect(page.getByText("$5.00")).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// G. System Tab (1 test)
// ---------------------------------------------------------------------------

test.describe("Admin — System Tab", () => {
	test("renders system config table", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "System" }).click();
		await expect(page.getByTestId(SYSTEM_TAB)).toBeVisible();

		// Table should show config entries
		await expect(
			page.getByRole("cell", { name: "signup_grant_credits" }),
		).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// H. Users Tab (4 tests)
// ---------------------------------------------------------------------------

test.describe("Admin — Users Tab", () => {
	test("renders user table with admin and non-admin users", async ({
		page,
	}) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Users" }).click();
		await expect(page.getByTestId(USERS_TAB)).toBeVisible();

		// Table should show user data
		await expect(
			page.getByRole("cell", { name: "admin@example.com" }),
		).toBeVisible();
		await expect(
			page.getByRole("cell", { name: "regular@example.com" }),
		).toBeVisible();
	});

	test("shows env-protected badge for protected admins", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Users" }).click();
		await expect(page.getByTestId(USERS_TAB)).toBeVisible();

		// Protected badge should be visible
		await expect(page.getByText("Protected")).toBeVisible();
	});

	test("disables Remove Admin button for env-protected admins", async ({
		page,
	}) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Users" }).click();
		await expect(page.getByTestId(USERS_TAB)).toBeVisible();

		// The "Remove Admin" button for the env-protected admin should be disabled
		const removeButton = page.getByRole("button", { name: "Remove admin" });
		await expect(removeButton).toBeDisabled();
	});

	test("Make Admin button promotes non-admin user and shows toast", async ({
		page,
	}) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		await page.getByRole("tab", { name: "Users" }).click();
		await expect(page.getByTestId(USERS_TAB)).toBeVisible();

		// Click "Make Admin" button for the non-admin user
		const makeAdminBtn = page.getByRole("button", { name: "Make admin" });
		await expect(makeAdminBtn).toBeEnabled();
		await makeAdminBtn.click();

		// Should show success toast
		await expect(page.getByText(/updated/i)).toBeVisible({
			timeout: 5_000,
		});
	});
});

// ---------------------------------------------------------------------------
// I. Nav — Admin Link (2 tests)
// ---------------------------------------------------------------------------

test.describe("Nav — Admin Link", () => {
	test("shows Admin link for admin users", async ({ page }) => {
		await setupAdminMocks(page);
		await page.goto("/admin/config");

		// Admin link should be visible in nav
		const adminLink = page.getByRole("link", { name: "Admin" });
		await expect(adminLink).toBeVisible();

		// Should have active state on /admin/config
		await expect(adminLink).toHaveAttribute("aria-current", "page");
	});

	test("hides Admin link for non-admin users", async ({ page }) => {
		await setupNonAdminMocks(page);

		await page.goto("/");

		// Admin link should NOT be visible
		await expect(page.getByRole("link", { name: "Admin" })).not.toBeAttached();
	});
});
