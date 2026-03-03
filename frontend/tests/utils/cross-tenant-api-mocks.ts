/**
 * Stateful Playwright route mock controller for cross-tenant isolation
 * E2E tests.
 *
 * Sets up an authenticated, onboarded user whose detail API calls return
 * 404 — simulating cross-tenant resource access (another user's data).
 * Uses page.route() to intercept API calls.
 *
 * REQ-014 §5.1: Backend returns 404 (not 403) for cross-tenant access.
 * These tests verify the frontend renders the correct error states.
 *
 * No fixture file needed — cross-tenant tests use thin 404/empty responses.
 */

import type { Page, Route } from "@playwright/test";

// Re-export so spec files import from a single source
export { AUTH_USER_ID } from "../fixtures/auth-mock-data";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** UUID that doesn't belong to the authenticated user. */
export const CROSS_TENANT_ID = "00000000-0000-4000-b000-000000000099";

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// No-op controller — shared mocks (auth, personas, change-flags, chat, SSE)
// are now provided by the base-test fixture (tests/e2e/base-test.ts).
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * No-op — shared mocks are now provided by the base-test fixture.
 *
 * Kept for backward compatibility with spec files that call it. Callers
 * add per-test 404 overrides via mock404ForRoute() after calling this.
 */
export async function setupCrossTenantBaseMocks(_page: Page): Promise<void> {
	// Base-test fixture handles auth/me, personas, change-flags, chat, SSE.
}

/**
 * Override a detail endpoint to return 404.
 *
 * Register AFTER setupCrossTenantBaseMocks — later routes take priority
 * in Playwright when matched.
 */
export async function mock404ForRoute(
	page: Page,
	urlPattern: RegExp,
): Promise<void> {
	await page.route(urlPattern, async (route: Route) => {
		await route.fulfill({
			status: 404,
			contentType: "application/json",
			body: JSON.stringify({
				error: { code: "NOT_FOUND", message: "Resource not found." },
			}),
		});
	});
}

/**
 * Override a list endpoint to return an empty array.
 *
 * Simulates a user seeing only their own (empty) data — no cross-tenant
 * data leaks into list views.
 */
export async function mockEmptyList(
	page: Page,
	urlPattern: RegExp,
): Promise<void> {
	await page.route(urlPattern, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				data: [],
				meta: { total: 0, page: 1, per_page: 100, total_pages: 1 },
			}),
		});
	});
}
