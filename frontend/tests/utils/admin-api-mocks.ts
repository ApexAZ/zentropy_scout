/**
 * Stateful Playwright route mock controller for admin E2E tests.
 *
 * Intercepts all /api/v1/admin/* endpoints plus auth and shared routes
 * required by the admin page (persona status guard, balance, events).
 *
 * REQ-022 §15.4: Frontend test infrastructure for admin page E2E tests.
 */

import type { Page, Route } from "@playwright/test";

import {
	authMeResponse,
	errorResponse,
	onboardedPersonaList,
} from "../fixtures/auth-mock-data";
import { balanceResponse } from "../fixtures/usage-mock-data";
import {
	cacheRefreshResponse,
	modelCreatedResponse,
	modelsListResponse,
	modelUpdatedResponse,
	packsListResponse,
	pricingCreatedResponse,
	pricingListResponse,
	routingListResponse,
	systemConfigListResponse,
	systemConfigUpsertedResponse,
	usersListResponse,
	userToggledResponse,
} from "../fixtures/admin-mock-data";

// Re-export IDs for spec files
export { ADMIN_MODEL_IDS, ADMIN_USER_IDS } from "../fixtures/admin-mock-data";

// ---------------------------------------------------------------------------
// Admin JWT cookie
// ---------------------------------------------------------------------------

/**
 * Mock admin JWT with `adm: true` claim.
 *
 * The proxy decodes the JWT payload via base64 (no verification) to check
 * the `adm` claim. This token has:
 *   Header:  {"alg":"HS256","typ":"JWT"}
 *   Payload: {"adm":true}
 *   Signature: mock-sig (ignored by proxy)
 */
export const ADMIN_JWT =
	"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG0iOnRydWV9.mock-sig";

const ADMIN_COOKIE = {
	name: "zentropy.session-token",
	value: ADMIN_JWT,
	domain: "localhost",
	path: "/",
	expires: -1,
	httpOnly: false,
	secure: false,
	sameSite: "Lax" as const,
};

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class AdminMockController {
	async setupRoutes(page: Page): Promise<void> {
		// Set admin JWT cookie (overrides the default mock-e2e-session)
		await page.context().addCookies([ADMIN_COOKIE]);

		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Admin endpoints
		await page.route(/\/api\/v1\/admin\//, async (route) =>
			this.handleAdminRoute(route),
		);

		// Auth, personas, persona-change-flags, balance, chat
		await page.route(
			/\/api\/v1\/(auth|personas|persona-change-flags|usage|chat)/,
			async (route) => this.handleSharedRoute(route),
		);
	}

	// -----------------------------------------------------------------------
	// Admin endpoint router
	// -----------------------------------------------------------------------

	private async handleAdminRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const path = new URL(url).pathname;

		// --- Models ---
		if (path.match(/\/admin\/models$/)) {
			if (method === "GET") return this.json(route, modelsListResponse());
			if (method === "POST")
				return this.json(route, modelCreatedResponse(), 201);
		}
		if (path.match(/\/admin\/models\/[^/]+$/)) {
			if (method === "PATCH") return this.json(route, modelUpdatedResponse());
			if (method === "DELETE") return this.empty(route, 204);
		}

		// --- Pricing ---
		if (path.match(/\/admin\/pricing$/)) {
			if (method === "GET") return this.json(route, pricingListResponse());
			if (method === "POST")
				return this.json(route, pricingCreatedResponse(), 201);
		}
		if (path.match(/\/admin\/pricing\/[^/]+$/)) {
			if (method === "PATCH") return this.json(route, pricingCreatedResponse());
			if (method === "DELETE") return this.empty(route, 204);
		}

		// --- Routing ---
		if (path.match(/\/admin\/routing$/)) {
			if (method === "GET") return this.json(route, routingListResponse());
			if (method === "POST")
				return this.json(route, routingListResponse(), 201);
		}
		if (path.match(/\/admin\/routing\/[^/]+$/)) {
			if (method === "PATCH") return this.json(route, routingListResponse());
			if (method === "DELETE") return this.empty(route, 204);
		}

		// --- Credit Packs ---
		if (path.match(/\/admin\/credit-packs$/)) {
			if (method === "GET") return this.json(route, packsListResponse());
			if (method === "POST") return this.json(route, packsListResponse(), 201);
		}
		if (path.match(/\/admin\/credit-packs\/[^/]+$/)) {
			if (method === "PATCH") return this.json(route, packsListResponse());
			if (method === "DELETE") return this.empty(route, 204);
		}

		// --- System Config ---
		if (path.match(/\/admin\/config$/)) {
			if (method === "GET") return this.json(route, systemConfigListResponse());
		}
		if (path.match(/\/admin\/config\/[^/]+$/)) {
			const key = path.split("/").pop() ?? "";
			if (method === "PUT")
				return this.json(
					route,
					systemConfigUpsertedResponse(decodeURIComponent(key), "updated"),
				);
			if (method === "DELETE") return this.empty(route, 204);
		}

		// --- Users ---
		if (path.match(/\/admin\/users$/)) {
			if (method === "GET") return this.json(route, usersListResponse());
		}
		if (path.match(/\/admin\/users\/[^/]+$/)) {
			if (method === "PATCH")
				return this.json(route, userToggledResponse({ is_admin: true }));
		}

		// --- Cache ---
		if (path.match(/\/admin\/cache\/refresh$/)) {
			if (method === "POST") return this.json(route, cacheRefreshResponse());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Shared endpoint router (auth, personas, balance, etc.)
	// -----------------------------------------------------------------------

	private async handleSharedRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const path = new URL(url).pathname;

		// GET /auth/me — admin user
		if (path.endsWith("/auth/me") && method === "GET") {
			return this.json(route, authMeResponse({ isAdmin: true }));
		}

		// Personas (persona status guard)
		if (path.endsWith("/personas") && method === "GET") {
			return this.json(route, onboardedPersonaList());
		}

		// Persona change flags — empty
		if (path.endsWith("/persona-change-flags") && method === "GET") {
			return this.json(route, this.emptyList());
		}

		// Usage balance (for nav bar indicator)
		if (path.endsWith("/usage/balance") && method === "GET") {
			return this.json(route, balanceResponse("50.000000"));
		}

		// Chat messages — empty
		if (path.includes("/chat") && method === "GET") {
			return this.json(route, this.emptyList());
		}

		// Auth endpoints (verify-password, logout, etc.) — fallback
		if (path.includes("/auth/")) {
			return this.json(route, errorResponse("NOT_IMPLEMENTED", "Mock"), 501);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private emptyList() {
		return {
			data: [],
			meta: { total: 0, page: 1, per_page: 100, total_pages: 0 },
		};
	}

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}

	private async empty(route: Route, status: number): Promise<void> {
		await route.fulfill({ status, body: "" });
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/** Set up mocks for admin pages (admin JWT cookie + all admin API mocks). */
export async function setupAdminMocks(
	page: Page,
): Promise<AdminMockController> {
	const controller = new AdminMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for non-admin pages (no admin JWT, /auth/me returns is_admin=false).
 *
 * Used by tests that verify non-admin users are redirected or don't see
 * admin UI elements. Provides minimal shared endpoint mocking.
 */
export async function setupNonAdminMocks(page: Page): Promise<void> {
	// Abort SSE to prevent hanging
	await page.route("**/api/v1/events/**", (route) => route.abort());
	await page.route("**/api/v1/events", (route) => route.abort());

	// /auth/me — non-admin user
	await page.route(/\/api\/v1\/auth\/me/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify(authMeResponse({ isAdmin: false })),
		});
	});

	// Generic fallback for all other endpoints
	await page.route(/\/api\/v1\//, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				data: [],
				meta: { total: 0, page: 1, per_page: 100, total_pages: 0 },
			}),
		});
	});
}
