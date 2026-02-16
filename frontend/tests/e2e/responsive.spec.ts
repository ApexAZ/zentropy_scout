/**
 * E2E tests for responsive viewport behavior.
 *
 * REQ-012 §4.5: Mobile-first responsive strategy with three breakpoints:
 * - Mobile (<768px): Nav hidden, chat as full-screen overlay with Back button
 * - Tablet (768–1024px): Nav visible, chat as constrained sheet overlay
 * - Desktop (>1024px): Nav visible, chat as persistent inline sidebar
 *
 * All API calls are mocked via Playwright's page.route() — no real backend.
 */

import { expect, test } from "@playwright/test";

import { setupDashboardMocks } from "../utils/job-discovery-api-mocks";
import { setupBasicInfoEditorMocks } from "../utils/persona-update-api-mocks";

// ---------------------------------------------------------------------------
// Shared selectors & text
// ---------------------------------------------------------------------------

const TOGGLE_CHAT = "Toggle chat";
const NAV_APPLICATIONS = "Applications";
const NAV_RESUMES = "Resumes";
const CHAT_SHEET = '[data-slot="sheet-content"][aria-label="Chat panel"]';
const BASIC_INFO_FORM = "basic-info-editor-form";
/** Targets the outer 2-col grid (gap-6), not inner form-item grids (gap-2). */
const FORM_GRID = ".grid.gap-6";

// ---------------------------------------------------------------------------
// A. Mobile viewport (375 × 667)
// ---------------------------------------------------------------------------

test.describe("Mobile viewport (375×667)", () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 375, height: 667 });
	});

	test("hides primary navigation links", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		// Nav links should be hidden on mobile (hidden md:flex)
		await expect(
			page.getByRole("link", { name: NAV_APPLICATIONS }),
		).not.toBeVisible();
		await expect(
			page.getByRole("link", { name: NAV_RESUMES }),
		).not.toBeVisible();

		// Chat toggle should always be visible
		await expect(page.getByRole("button", { name: TOGGLE_CHAT })).toBeVisible();
	});

	test("opens chat as full-screen overlay with Back button", async ({
		page,
	}) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Chat should open as a Sheet (dialog) on mobile
		const chatDialog = page.locator(CHAT_SHEET);
		await expect(chatDialog).toBeVisible();

		// Mobile-only Back button should be visible
		await expect(
			chatDialog.getByRole("button", { name: "Back" }),
		).toBeVisible();
	});

	test("stacks persona form in single column", async ({ page }) => {
		await setupBasicInfoEditorMocks(page);
		await page.goto("/persona/basic-info");

		await expect(page.getByTestId(BASIC_INFO_FORM)).toBeVisible();

		const columns = await page
			.getByTestId(BASIC_INFO_FORM)
			.locator(FORM_GRID)
			.evaluate((el) => getComputedStyle(el).gridTemplateColumns);

		// Single column = one value (no spaces), e.g. "343px"
		expect(columns.trim().split(/\s+/)).toHaveLength(1);
	});
});

// ---------------------------------------------------------------------------
// B. Tablet viewport (768 × 1024)
// ---------------------------------------------------------------------------

test.describe("Tablet viewport (768×1024)", () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 768, height: 1024 });
	});

	test("shows primary navigation links", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await expect(
			page.getByRole("link", { name: NAV_APPLICATIONS }),
		).toBeVisible();
		await expect(page.getByRole("link", { name: NAV_RESUMES })).toBeVisible();
	});

	test("opens chat as constrained sheet overlay", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Chat should open as a Sheet (dialog) on tablet
		const chatDialog = page.locator(CHAT_SHEET);
		await expect(chatDialog).toBeVisible();

		// Back button is mobile-only — should NOT be present on tablet
		await expect(
			chatDialog.getByRole("button", { name: "Back" }),
		).not.toBeAttached();
	});
});

// ---------------------------------------------------------------------------
// C. Desktop viewport (1280 × 720)
// ---------------------------------------------------------------------------

test.describe("Desktop viewport (1280×720)", () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
	});

	test("shows primary navigation links", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await expect(
			page.getByRole("link", { name: NAV_APPLICATIONS }),
		).toBeVisible();
		await expect(page.getByRole("link", { name: NAV_RESUMES })).toBeVisible();
	});

	test("opens chat as persistent inline sidebar", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/");

		await page.getByRole("button", { name: TOGGLE_CHAT }).click();

		// Desktop renders an <aside> element, not a dialog Sheet
		const chatAside = page.locator('aside[aria-label="Chat panel"]');
		await expect(chatAside).toBeVisible();

		// Should NOT render as a Sheet (dialog) on desktop
		await expect(page.locator(CHAT_SHEET)).not.toBeAttached();
	});

	test("displays persona form in multi-column grid", async ({ page }) => {
		await setupBasicInfoEditorMocks(page);
		await page.goto("/persona/basic-info");

		await expect(page.getByTestId(BASIC_INFO_FORM)).toBeVisible();

		const columns = await page
			.getByTestId(BASIC_INFO_FORM)
			.locator(FORM_GRID)
			.evaluate((el) => getComputedStyle(el).gridTemplateColumns);

		// Multi-column = space-separated values (2+ columns), e.g. "608px 608px"
		expect(columns.trim().split(/\s+/).length).toBeGreaterThanOrEqual(2);
	});
});
