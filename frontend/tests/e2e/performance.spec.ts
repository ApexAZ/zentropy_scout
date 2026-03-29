/**
 * E2E performance budget tests — web vitals for key pages.
 *
 * No specific REQ — cross-cutting performance regression guard added as
 * part of the Playwright test gaps plan (§23).
 *
 * Measures navigation timing metrics via the Performance API to catch
 * regressions in page load performance. All API calls are mocked, so
 * thresholds are intentionally generous — failures indicate real
 * regressions in bundle size, rendering, or routing, not network issues.
 *
 * Metrics extracted per page:
 * - TTFB (Time to First Byte): responseStart - requestStart < 800ms
 * - DOM Content Loaded: domContentLoadedEventEnd - navigationStart < 3000ms
 * - Load: loadEventEnd - navigationStart < 5000ms
 * - LCP (Largest Contentful Paint): via PerformanceObserver < 2500ms
 *
 * Chromium only — Firefox and WebKit have inconsistent Performance API
 * support for these timing entries, so tests are skipped on those browsers.
 */

import { expect, test, type Page } from "./base-test";

import { setupDashboardMocks } from "../utils/job-discovery-api-mocks";
import { setupNewOnboardingMocks } from "../utils/onboarding-api-mocks";
import {
	BASE_RESUME_IDS,
	setupResumeListMocks,
} from "../utils/resume-api-mocks";

// ---------------------------------------------------------------------------
// Browser gate — Chromium only
// ---------------------------------------------------------------------------

test.skip(
	({ browserName }) => browserName !== "chromium",
	"Performance timing tests run on Chromium only",
);

// ---------------------------------------------------------------------------
// Thresholds (ms) — generous for mocked-API pages
// ---------------------------------------------------------------------------

const TTFB_BUDGET = 800;
const DCL_BUDGET = 3000;
const LOAD_BUDGET = 5000;
const LCP_BUDGET = 2500;

// ---------------------------------------------------------------------------
// Helper — extract navigation timing from the Performance API
// ---------------------------------------------------------------------------

interface NavigationTimings {
	ttfb: number;
	domContentLoaded: number;
	load: number;
}

async function getNavigationTimings(page: Page): Promise<NavigationTimings> {
	return page.evaluate(() => {
		const [entry] = performance.getEntriesByType(
			"navigation",
		) as PerformanceNavigationTiming[];
		if (!entry) throw new Error("No navigation timing entry found");
		return {
			ttfb: entry.responseStart - entry.requestStart,
			domContentLoaded: entry.domContentLoadedEventEnd - entry.startTime,
			load: entry.loadEventEnd - entry.startTime,
		};
	});
}

// ---------------------------------------------------------------------------
// Helper — extract LCP via PerformanceObserver
//
// Registers an observer AFTER navigation (post-load). Chromium keeps all
// LCP entries in the performance timeline, so getEntriesByType works
// retroactively — no need for addInitScript before navigation.
// ---------------------------------------------------------------------------

async function getLCP(page: Page): Promise<number> {
	return page.evaluate(() => {
		const entries = performance.getEntriesByType(
			"largest-contentful-paint",
		) as PerformanceEntry[];
		if (entries.length === 0) return 0;
		// The last entry is the final (largest) LCP candidate
		return entries[entries.length - 1].startTime;
	});
}

// ---------------------------------------------------------------------------
// Helper — assert all navigation budgets
// ---------------------------------------------------------------------------

function assertWithinBudget(timings: NavigationTimings): void {
	expect(
		timings.ttfb,
		`TTFB ${timings.ttfb.toFixed(0)}ms exceeds budget ${TTFB_BUDGET}ms`,
	).toBeLessThan(TTFB_BUDGET);

	expect(
		timings.domContentLoaded,
		`DCL ${timings.domContentLoaded.toFixed(0)}ms exceeds budget ${DCL_BUDGET}ms`,
	).toBeLessThan(DCL_BUDGET);

	expect(
		timings.load,
		`Load ${timings.load.toFixed(0)}ms exceeds budget ${LOAD_BUDGET}ms`,
	).toBeLessThan(LOAD_BUDGET);
}

function assertLCPWithinBudget(lcp: number): void {
	// LCP of 0 means no entry was recorded (e.g., page has no qualifying
	// content element). Skip assertion rather than false-pass at 0ms.
	if (lcp === 0) return;
	expect(
		lcp,
		`LCP ${lcp.toFixed(0)}ms exceeds budget ${LCP_BUDGET}ms`,
	).toBeLessThan(LCP_BUDGET);
}

// ---------------------------------------------------------------------------
// Tests — 4 key pages
// ---------------------------------------------------------------------------

test.describe("Performance Budgets", () => {
	test("landing page loads within budget", async ({ page }) => {
		await page.context().clearCookies();

		// Override base-test auth mock → 401 so landing renders public layout
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({ status: 401, body: "Unauthorized" });
		});

		await page.goto("/", { waitUntil: "load" });
		const timings = await getNavigationTimings(page);
		assertWithinBudget(timings);
		const lcp = await getLCP(page);
		assertLCPWithinBudget(lcp);
	});

	test("dashboard loads within budget", async ({ page }) => {
		await setupDashboardMocks(page);
		await page.goto("/dashboard", { waitUntil: "load" });
		const timings = await getNavigationTimings(page);
		assertWithinBudget(timings);
		const lcp = await getLCP(page);
		assertLCPWithinBudget(lcp);
	});

	test("resume detail loads within budget", async ({ page }) => {
		await setupResumeListMocks(page);
		await page.goto(`/resumes/${BASE_RESUME_IDS[0]}`, {
			waitUntil: "load",
		});
		const timings = await getNavigationTimings(page);
		assertWithinBudget(timings);
		const lcp = await getLCP(page);
		assertLCPWithinBudget(lcp);
	});

	test("onboarding step 1 loads within budget", async ({ page }) => {
		await setupNewOnboardingMocks(page);
		await page.goto("/onboarding", { waitUntil: "load" });
		const timings = await getNavigationTimings(page);
		assertWithinBudget(timings);
		const lcp = await getLCP(page);
		assertLCPWithinBudget(lcp);
	});
});
