/**
 * Shared Playwright base test with common API mocks.
 *
 * Extends the default Playwright `test` with auto-mocked shared endpoints
 * that every E2E test needs: auth session, SSE, personas, nav indicators.
 *
 * Route priority: Playwright uses LIFO — later-registered routes are checked
 * first. The registration order below is intentional:
 *
 *   1. Catch-all fallback (registered first → lowest priority)
 *   2. Shared endpoint mocks (auth, personas, balance, chat)
 *   3. Mock controllers from individual spec files (registered last → highest)
 *
 * This ensures that any un-mocked /api/v1/ request returns a safe empty list
 * instead of hitting the real backend (which returns 401 and triggers a
 * redirect to /login).
 *
 * Import `{ test, expect }` from this file instead of `@playwright/test`.
 */

import { test as base } from "@playwright/test";

import {
	authMeResponse,
	onboardedPersonaList,
} from "../fixtures/auth-mock-data";
import { balanceResponse } from "../fixtures/usage-mock-data";

// ---------------------------------------------------------------------------
// Empty list shape reused by multiple shared mocks.
// ---------------------------------------------------------------------------

const EMPTY_LIST = {
	data: [],
	meta: { total: 0, page: 1, per_page: 100, total_pages: 0 },
};

// ---------------------------------------------------------------------------
// Base test with shared route mocks.
// ---------------------------------------------------------------------------

export const test = base.extend({
	page: async ({ page }, use) => {
		// Auth cookie — proxy requires this to access /dashboard
		// and other authenticated routes. Presence-only check, any
		// non-empty value works (no JWT validation in proxy).
		await page.context().addCookies([
			{
				name: "zentropy.session-token",
				value: "test-session-token",
				domain: "localhost",
				path: "/",
			},
		]);

		// SSE events — abort to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Catch-all fallback for any un-mocked /api/v1/ endpoint.
		// Registered FIRST so it has LOWEST priority (LIFO). Specific
		// routes below and mock controllers in spec files override this.
		// Prevents real backend requests (which return 401 with fake JWT
		// and trigger handleUnauthorized → redirect to /login).
		await page.route(/\/api\/v1\//, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(EMPTY_LIST),
			});
		});

		// AuthProvider session check (GET /auth/me)
		await page.route(/\/api\/v1\/auth\/me/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(authMeResponse()),
			});
		});

		// OnboardingGate persona check (GET /personas)
		await page.route(/\/api\/v1\/personas/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(onboardedPersonaList()),
			});
		});

		// MainLayout nav badge (GET /persona-change-flags)
		await page.route(/\/api\/v1\/persona-change-flags/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(EMPTY_LIST),
			});
		});

		// Nav bar balance indicator (GET /usage/balance)
		await page.route(/\/api\/v1\/usage\/balance/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(balanceResponse("50.000000")),
			});
		});

		// ChatSidebar messages (GET /chat/*)
		await page.route(/\/api\/v1\/chat/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(EMPTY_LIST),
			});
		});

		// JobSearchSection search profile (GET/PATCH /search-profiles/*)
		// Returns a minimal valid SearchProfile so settings page renders.
		await page.route(/\/api\/v1\/search-profiles/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					data: {
						id: "sp-base",
						persona_id: "base-persona",
						fit_searches: [],
						stretch_searches: [],
						persona_fingerprint: "fp-base",
						is_stale: false,
						generated_at: null,
						approved_at: null,
						created_at: "2026-01-01T00:00:00Z",
						updated_at: "2026-01-01T00:00:00Z",
					},
				}),
			});
		});

		// eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright fixture, not a React hook
		await use(page);
	},
});

export { expect } from "@playwright/test";
export type { Page, Route } from "@playwright/test";
