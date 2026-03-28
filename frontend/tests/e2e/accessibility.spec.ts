/**
 * E2E accessibility tests.
 *
 * REQ-012 §13.8: Global accessibility requirements — WCAG 2.1 AA compliance.
 *
 * A. Reduced Motion — verifies prefers-reduced-motion CSS override.
 * B. WCAG 2.1 AA — Public Pages — axe-core audits for /, /login, /register.
 */

import { expect, test } from "./base-test";

import { runAxeAudit } from "../utils/axe-helper";
import { setupUnauthMocks } from "../utils/auth-api-mocks";
import { setupOnboardedUserMocks } from "../utils/onboarding-api-mocks";

// ---------------------------------------------------------------------------
// A. Reduced Motion (1 test)
// ---------------------------------------------------------------------------

test.describe("Reduced Motion", () => {
	test("suppresses animations when prefers-reduced-motion is reduce", async ({
		page,
	}) => {
		await page.emulateMedia({ reducedMotion: "reduce" });
		await setupOnboardedUserMocks(page);
		await page.goto("/dashboard");

		// Wait for the page to be fully loaded
		await page.waitForLoadState("networkidle");

		// Verify the media query is active
		const mediaQueryMatches = await page.evaluate(
			() => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
		);
		expect(mediaQueryMatches).toBe(true);

		// Verify CSS rule applies to page elements: set a long transition on
		// body and check the computed value is overridden to near-zero.
		const duration = await page.evaluate(() => {
			document.body.style.transitionProperty = "opacity";
			document.body.style.transitionDuration = "5s";
			// Force style recalc
			void getComputedStyle(document.body).transitionDuration;
			return getComputedStyle(document.body).transitionDuration;
		});

		// 0.01ms = 0.00001s; parseFloat("0.00001s") = 0.00001
		// The !important rule overrides inline styles to near-zero.
		expect(parseFloat(duration)).toBeLessThan(0.01);
	});
});

// ---------------------------------------------------------------------------
// B. WCAG 2.1 AA — Public Pages (3 tests)
// ---------------------------------------------------------------------------

test.describe("WCAG 2.1 AA — Public Pages", () => {
	test.beforeEach(async ({ page }) => {
		await page.context().clearCookies();

		// Override base-test /auth/me mock to return 401 so AuthProvider
		// sets status="unauthenticated" — same pattern as landing.spec.ts.
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		});
	});

	test("landing page (/) has no WCAG 2.1 AA violations", async ({ page }) => {
		await page.goto("/", { waitUntil: "networkidle" });

		const results = await runAxeAudit(page);
		expect(results.violations).toEqual([]);
	});

	test("login page (/login) has no WCAG 2.1 AA violations", async ({
		page,
	}) => {
		await setupUnauthMocks(page);
		await page.goto("/login", { waitUntil: "networkidle" });

		const results = await runAxeAudit(page);
		expect(results.violations).toEqual([]);
	});

	test("register page (/register) has no WCAG 2.1 AA violations", async ({
		page,
	}) => {
		await setupUnauthMocks(page);
		await page.goto("/register", { waitUntil: "networkidle" });

		const results = await runAxeAudit(page);
		expect(results.violations).toEqual([]);
	});
});
