/**
 * Visual regression tests — baseline screenshots for key pages.
 *
 * Captures toHaveScreenshot() baselines at a fixed 1280x720 viewport.
 * Baselines are generated inside Docker for OS-consistent rendering
 * (see docker/docker-compose.playwright.yml).
 *
 * Generate/update baselines:  cd frontend && npm run test:e2e:visual:update
 * Run comparison tests:       cd frontend && npm run test:e2e:visual
 *
 * Baselines live in tests/__screenshots__/{projectName}/... and MUST be
 * committed to git. Regenerate after any UI change that affects screenshots.
 */

import { expect, test } from "./base-test";

// ---------------------------------------------------------------------------
// Constants — test IDs
// ---------------------------------------------------------------------------

const TID_LANDING_PAGE = "landing-page";
const TID_LOGIN_SUBMIT = "login-submit";
const TID_REGISTER_SUBMIT = "register-submit";

// ---------------------------------------------------------------------------
// Viewport — all visual regression tests use a fixed desktop viewport
// ---------------------------------------------------------------------------

test.use({ viewport: { width: 1280, height: 720 } });

// ---------------------------------------------------------------------------
// Public Pages (unauthenticated)
// ---------------------------------------------------------------------------

test.describe("Visual Regression — Public Pages", () => {
	test.beforeEach(async ({ page }) => {
		await page.context().clearCookies();

		// Override base-test /auth/me mock → 401 so AuthProvider
		// sets status="unauthenticated" and pages render public layout.
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		});
	});

	test("landing page", async ({ page }) => {
		await page.goto("/", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_LANDING_PAGE)).toBeVisible();
		await expect(page).toHaveScreenshot("landing-desktop.png");
	});

	test("login page", async ({ page }) => {
		await page.goto("/login", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_LOGIN_SUBMIT)).toBeVisible();
		await expect(page).toHaveScreenshot("login-desktop.png");
	});

	test("register page", async ({ page }) => {
		await page.goto("/register", { waitUntil: "networkidle" });
		await expect(page.getByTestId(TID_REGISTER_SUBMIT)).toBeVisible();
		await expect(page).toHaveScreenshot("register-desktop.png");
	});
});
