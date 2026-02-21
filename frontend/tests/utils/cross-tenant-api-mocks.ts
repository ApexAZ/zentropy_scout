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

import {
	authMeResponse,
	onboardedPersonaList,
} from "../fixtures/auth-mock-data";

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

export class CrossTenantMockController {
	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Auth — authenticated user
		await page.route(/\/api\/v1\/auth\/me/, async (route) =>
			this.json(route, authMeResponse()),
		);

		// Personas — onboarded (required for OnboardingGate)
		await page.route(/\/api\/v1\/personas/, async (route) =>
			this.json(route, onboardedPersonaList()),
		);

		// Persona change flags — empty (for main layout badge)
		await page.route(/\/api\/v1\/persona-change-flags/, async (route) =>
			this.json(route, this.emptyList()),
		);

		// Chat messages — empty
		await page.route(/\/api\/v1\/chat/, async (route) =>
			this.json(route, this.emptyList()),
		);
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}

	private emptyList() {
		return {
			data: [],
			meta: { total: 0, page: 1, per_page: 100, total_pages: 1 },
		};
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * Set up routes for an authenticated, onboarded user.
 *
 * Base routes (auth/me, personas, events, change-flags) are always mocked.
 * Callers add per-test 404 overrides via mock404ForRoute() after calling this.
 */
export async function setupCrossTenantBaseMocks(
	page: Page,
): Promise<CrossTenantMockController> {
	const controller = new CrossTenantMockController();
	await controller.setupRoutes(page);
	return controller;
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
