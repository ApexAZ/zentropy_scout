/**
 * Stateful Playwright route mock controller for auth E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts (e.g., after verify-password
 * success, /auth/me returns authenticated).
 *
 * All API routes use regex to avoid Playwright glob matching edge cases.
 */

import type { Page, Route } from "@playwright/test";

import {
	authMeResponse,
	changePasswordResponse,
	errorResponse,
	invalidateSessionsResponse,
	logoutResponse,
	magicLinkResponse,
	onboardedPersonaList,
	profilePatchResponse,
	registerResponse,
	verifyPasswordResponse,
} from "../fixtures/auth-mock-data";

// Re-export IDs so spec files can import from a single source
export { AUTH_USER_ID, PERSONA_ID } from "../fixtures/auth-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthMockState {
	/** Whether /auth/me returns authenticated session or 401. */
	authenticated: boolean;
	/** Whether the user has a password (affects account settings UI). */
	hasPassword: boolean;
	/** Override for verify-password status (for error tests). */
	verifyPasswordStatus: number | null;
	/** Override for register status (for error tests). */
	registerStatus: number | null;
	/** Override for change-password status (for error tests). */
	changePasswordStatus: number | null;
	/** Name returned by /auth/me (mutable via profile patch). */
	name: string;
}

export interface AuthMockOptions {
	authenticated?: boolean;
	hasPassword?: boolean;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class AuthMockController {
	state: AuthMockState;

	constructor(options?: AuthMockOptions) {
		this.state = {
			authenticated: options?.authenticated ?? false,
			hasPassword: options?.hasPassword ?? true,
			verifyPasswordStatus: null,
			registerStatus: null,
			changePasswordStatus: null,
			name: "Test User",
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Auth endpoints
		await page.route(/\/api\/v1\/auth\//, async (route) =>
			this.handleAuthRoute(route),
		);

		// Personas (for persona status guard on settings page)
		await page.route(/\/api\/v1\/personas/, async (route) =>
			this.handlePersonasRoute(route),
		);

		// Persona change flags (for main layout badge)
		await page.route(/\/api\/v1\/persona-change-flags/, async (route) =>
			this.json(route, {
				data: [],
				meta: { total: 0, page: 1, per_page: 100, total_pages: 0 },
			}),
		);
	}

	// -----------------------------------------------------------------------
	// Auth router
	// -----------------------------------------------------------------------

	private async handleAuthRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const path = new URL(url).pathname;

		// GET /auth/me
		if (path.endsWith("/auth/me") && method === "GET") {
			if (this.state.authenticated) {
				return this.json(
					route,
					authMeResponse({
						hasPassword: this.state.hasPassword,
						name: this.state.name,
					}),
				);
			}
			return this.json(
				route,
				errorResponse("UNAUTHORIZED", "Not authenticated"),
				401,
			);
		}

		// POST /auth/verify-password
		if (path.endsWith("/auth/verify-password") && method === "POST") {
			if (this.state.verifyPasswordStatus) {
				return this.json(
					route,
					errorResponse("AUTH_FAILED", "Invalid email or password."),
					this.state.verifyPasswordStatus,
				);
			}
			this.state.authenticated = true;
			return this.json(route, verifyPasswordResponse());
		}

		// POST /auth/register
		if (path.endsWith("/auth/register") && method === "POST") {
			if (this.state.registerStatus) {
				return this.json(
					route,
					errorResponse("CONFLICT", "Email already registered."),
					this.state.registerStatus,
				);
			}
			return this.json(route, registerResponse(), 201);
		}

		// POST /auth/magic-link
		if (path.endsWith("/auth/magic-link") && method === "POST") {
			return this.json(route, magicLinkResponse());
		}

		// POST /auth/logout
		if (path.endsWith("/auth/logout") && method === "POST") {
			this.state.authenticated = false;
			return this.json(route, logoutResponse());
		}

		// POST /auth/change-password
		if (path.endsWith("/auth/change-password") && method === "POST") {
			if (this.state.changePasswordStatus) {
				return this.json(
					route,
					errorResponse("AUTH_FAILED", "Current password is incorrect"),
					this.state.changePasswordStatus,
				);
			}
			return this.json(route, changePasswordResponse());
		}

		// PATCH /auth/profile
		if (path.endsWith("/auth/profile") && method === "PATCH") {
			const body = route.request().postDataJSON() as { name?: string };
			if (body.name) {
				this.state.name = body.name;
			}
			return this.json(route, profilePatchResponse(this.state.name));
		}

		// POST /auth/invalidate-sessions
		if (path.endsWith("/auth/invalidate-sessions") && method === "POST") {
			return this.json(route, invalidateSessionsResponse());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Personas router (for settings page guard)
	// -----------------------------------------------------------------------

	private async handlePersonasRoute(route: Route): Promise<void> {
		return this.json(route, onboardedPersonaList());
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
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/** Set up mocks for unauthenticated pages (login, register). */
export async function setupUnauthMocks(
	page: Page,
): Promise<AuthMockController> {
	const controller = new AuthMockController({ authenticated: false });
	await controller.setupRoutes(page);
	return controller;
}

/** Set up mocks for authenticated pages (settings, dashboard). */
export async function setupAuthenticatedMocks(
	page: Page,
	options?: AuthMockOptions,
): Promise<AuthMockController> {
	const controller = new AuthMockController({
		authenticated: true,
		...options,
	});
	await controller.setupRoutes(page);
	return controller;
}
