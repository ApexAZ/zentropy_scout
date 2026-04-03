/**
 * E2E tests for the landing page and auth-based routing.
 *
 * REQ-024 §6.2: Landing page rendering, CTA navigation, middleware
 * auth redirects, and settings legal section.
 *
 * All tests import from base-test (shared API mocks + auth cookie).
 * Unauthenticated tests clear the cookie in beforeEach — same pattern
 * as auth-login-register.spec.ts. The global storageState in
 * playwright.config.ts sets the cookie for every context, so
 * clearCookies() is required even without base-test's addCookies().
 */

import { expect, test } from "./base-test";

// ---------------------------------------------------------------------------
// Constants — test IDs and selectors
// ---------------------------------------------------------------------------

const TID_LANDING_PAGE = "landing-page";
const TID_HERO_CTA = "hero-cta";
const TID_LANDING_FOOTER = "landing-footer";
const TID_SETTINGS_LEGAL = "settings-legal";

// ---------------------------------------------------------------------------
// A. Unauthenticated Tests (cookie cleared before each test)
// ---------------------------------------------------------------------------

test.describe("Landing Page — Unauthenticated", () => {
	test.beforeEach(async ({ page }) => {
		await page.context().clearCookies();

		// Override the base-test /auth/me mock to return 401 so
		// AuthProvider sets status="unauthenticated". Without this,
		// the mock returns 200 (authenticated) even with cleared cookies,
		// causing client-side redirects on /register and /login pages.
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		});
	});

	test("unauthenticated user sees landing page at /", async ({ page }) => {
		await page.goto("/");

		await expect(page.getByTestId(TID_LANDING_PAGE)).toBeVisible();
		await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
	});

	test("CTA button navigates to register page", async ({ page }) => {
		await page.goto("/");

		await expect(page.getByTestId(TID_HERO_CTA)).toBeVisible();
		await page.getByTestId(TID_HERO_CTA).click();

		await expect(page).toHaveURL(/\/register/, { timeout: 10_000 });
	});

	test("footer Sign In link navigates to login page", async ({ page }) => {
		await page.goto("/");

		const signInLink = page
			.getByTestId(TID_LANDING_FOOTER)
			.getByRole("link", { name: "Sign In" });
		await expect(signInLink).toBeVisible();
		await signInLink.click();

		await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
	});

	test("unauthenticated user redirected from /dashboard to /login", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
	});

	test("landing page does not show app shell", async ({ page }) => {
		await page.goto("/");

		await expect(page.getByTestId(TID_LANDING_PAGE)).toBeVisible();

		// App shell elements should NOT be present on the landing page
		await expect(page.getByLabel("Main navigation")).not.toBeVisible();
		await expect(page.getByLabel("Toggle chat")).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// B. Authenticated Tests (auth cookie + API mocks via base-test)
// ---------------------------------------------------------------------------

test.describe("Landing Page — Authenticated", () => {
	test("authenticated user redirected from / to /dashboard", async ({
		page,
	}) => {
		await page.goto("/");

		await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });
	});

	test("dashboard renders at /dashboard", async ({ page }) => {
		await page.goto("/dashboard");

		await expect(page).toHaveTitle("Zentropy Scout");
		// Dashboard content is inside the app shell with main navigation
		await expect(page.getByLabel("Main navigation")).toBeVisible();
	});

	test("settings page has Legal section", async ({ page }) => {
		await page.goto("/settings");

		const legalCard = page.getByTestId(TID_SETTINGS_LEGAL);
		await expect(legalCard).toBeVisible();
		await expect(
			legalCard.getByRole("link", { name: "Terms of Service" }),
		).toBeVisible();
		await expect(
			legalCard.getByRole("link", { name: "Privacy Policy" }),
		).toBeVisible();
	});
});
